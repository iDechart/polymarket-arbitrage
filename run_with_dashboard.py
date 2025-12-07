#!/usr/bin/env python3
"""
Run Trading Bot with Dashboard
===============================

Starts the trading bot and web dashboard together.

Usage:
    python run_with_dashboard.py              # Dry run mode
    python run_with_dashboard.py --live       # Live mode
    python run_with_dashboard.py --port 8080  # Custom port
"""

import argparse
import asyncio
import logging
import signal
import sys
import threading
from datetime import datetime

import uvicorn

from polymarket_client import PolymarketClient
from core.data_feed import DataFeed
from core.arb_engine import ArbEngine, ArbConfig
from core.execution import ExecutionEngine, ExecutionConfig
from core.risk_manager import RiskManager, RiskConfig
from core.portfolio import Portfolio
from utils.config_loader import load_config, BotConfig
from utils.logging_utils import setup_logging
from dashboard.server import app, dashboard_state
from dashboard.integration import DashboardIntegration


logger = logging.getLogger(__name__)


class TradingBotWithDashboard:
    """Trading bot with integrated dashboard."""
    
    def __init__(self, config: BotConfig, port: int = 8888):
        self.config = config
        self.port = port
        self._running = False
        
        # Components
        self.client = None
        self.data_feed = None
        self.arb_engine = None
        self.execution_engine = None
        self.risk_manager = None
        self.portfolio = None
        self.dashboard_integration = None
        
        # Server
        self._server = None
        self._server_task = None
    
    async def start(self) -> None:
        """Start the bot and dashboard."""
        logger.info("=" * 60)
        logger.info("Polymarket Arbitrage Bot + Dashboard")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY RUN' if self.config.is_dry_run else 'LIVE'}")
        logger.info(f"Dashboard: http://localhost:{self.port}")
        logger.info("=" * 60)
        
        self._running = True
        
        # Initialize API client
        self.client = PolymarketClient(
            rest_url=self.config.api.polymarket_rest_url,
            ws_url=self.config.api.polymarket_ws_url,
            gamma_url=self.config.api.gamma_api_url,
            api_key=self.config.api.api_key,
            private_key=self.config.api.private_key,
            timeout=self.config.api.timeout_seconds,
            dry_run=self.config.is_dry_run,
        )
        await self.client.connect()
        
        # Initialize portfolio
        initial_balance = (
            self.config.mode.dry_run_initial_balance 
            if self.config.is_dry_run 
            else 0.0
        )
        self.portfolio = Portfolio(initial_balance=initial_balance)
        
        # Initialize risk manager
        self.risk_manager = RiskManager(RiskConfig(
            max_position_per_market=self.config.risk.max_position_per_market,
            max_global_exposure=self.config.risk.max_global_exposure,
            max_daily_loss=self.config.risk.max_daily_loss,
            max_drawdown_pct=self.config.risk.max_drawdown_pct,
            trade_only_high_volume=self.config.risk.trade_only_high_volume,
            min_24h_volume=self.config.risk.min_24h_volume,
            whitelist=self.config.risk.whitelist,
            blacklist=self.config.risk.blacklist,
            kill_switch_enabled=self.config.risk.kill_switch_enabled,
        ))
        
        # Initialize execution engine
        self.execution_engine = ExecutionEngine(
            client=self.client,
            risk_manager=self.risk_manager,
            portfolio=self.portfolio,
            config=ExecutionConfig(
                slippage_tolerance=self.config.trading.slippage_tolerance,
                order_timeout_seconds=self.config.trading.order_timeout_seconds,
                dry_run=self.config.is_dry_run,
            ),
        )
        await self.execution_engine.start()
        
        # Initialize arb engine
        self.arb_engine = ArbEngine(ArbConfig(
            min_edge=self.config.trading.min_edge,
            bundle_arb_enabled=self.config.trading.bundle_arb_enabled,
            min_spread=self.config.trading.min_spread,
            mm_enabled=self.config.trading.mm_enabled,
            tick_size=self.config.trading.tick_size,
            default_order_size=self.config.trading.default_order_size,
            min_order_size=self.config.trading.min_order_size,
            max_order_size=self.config.trading.max_order_size,
        ))
        
        # Initialize data feed
        market_ids = self.config.trading.markets.copy()
        self.data_feed = DataFeed(
            client=self.client,
            market_ids=market_ids,
            position_refresh_interval=5.0,
            on_update=self._on_market_update,
            config=self.config,
        )
        await self.data_feed.start()
        
        # Initialize dashboard integration
        self.dashboard_integration = DashboardIntegration(
            data_feed=self.data_feed,
            arb_engine=self.arb_engine,
            execution_engine=self.execution_engine,
            risk_manager=self.risk_manager,
            portfolio=self.portfolio,
            mode="dry_run" if self.config.is_dry_run else "live",
        )
        await self.dashboard_integration.start()
        
        # Start fill simulation for dry run
        if self.config.is_dry_run and self.config.mode.simulate_fills:
            asyncio.create_task(self._simulate_fills())
        
        # Start the web server
        await self._start_server()
        
        logger.info("Bot and dashboard started successfully!")
        logger.info(f"Open http://localhost:{self.port} in your browser")
    
    async def _start_server(self) -> None:
        """Start the uvicorn server."""
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(self._server.serve())
    
    def _on_market_update(self, market_id: str, market_state) -> None:
        """Handle market updates."""
        if not self._running:
            return
        
        # Check risk limits
        if not self.risk_manager.within_global_limits():
            return
        
        # Analyze for opportunities
        signals = self.arb_engine.analyze(market_state)
        
        for signal in signals:
            # Add to dashboard
            if signal.opportunity:
                self.dashboard_integration.add_opportunity(
                    opportunity_type=signal.opportunity.opportunity_type.value,
                    market_id=signal.market_id,
                    edge=signal.opportunity.edge,
                    suggested_size=signal.opportunity.suggested_size,
                )
            
            self.dashboard_integration.add_signal(
                action=signal.action,
                market_id=signal.market_id,
            )
            
            # Submit to execution
            asyncio.create_task(self.execution_engine.submit_signal(signal))
    
    async def _simulate_fills(self) -> None:
        """Simulate order fills in dry run mode."""
        import random
        
        while self._running:
            try:
                await asyncio.sleep(2.0)
                
                orders = self.execution_engine.get_open_orders()
                for order in orders:
                    if random.random() < self.config.mode.fill_probability:
                        trade = self.client.simulate_fill(order.order_id)
                        if trade:
                            self.execution_engine.handle_fill(trade)
                            self.dashboard_integration.add_trade(
                                side=trade.side.value,
                                price=trade.price,
                                size=trade.size,
                                market_id=trade.market_id,
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fill simulation error: {e}")
    
    async def stop(self) -> None:
        """Stop everything gracefully."""
        logger.info("Shutting down...")
        self._running = False
        
        if self.dashboard_integration:
            await self.dashboard_integration.stop()
        
        if self.data_feed:
            await self.data_feed.stop()
        
        if self.execution_engine:
            await self.execution_engine.stop()
        
        if self.client:
            await self.client.disconnect()
        
        if self._server:
            self._server.should_exit = True
        
        # Final summary
        if self.portfolio:
            summary = self.portfolio.get_summary()
            logger.info("=" * 60)
            logger.info("Final Summary")
            logger.info("=" * 60)
            logger.info(f"Total PnL: ${summary['pnl']['total_pnl']:.2f}")
            logger.info(f"Trades: {summary['total_trades']}")
            logger.info(f"Win Rate: {summary['win_rate']:.1%}")
        
        logger.info("Shutdown complete")
    
    async def run_forever(self) -> None:
        """Run until interrupted."""
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass


async def main_async(args: argparse.Namespace) -> None:
    """Async main function."""
    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    # Override mode
    if args.live:
        config.mode.trading_mode = "live"
    elif args.dry_run:
        config.mode.trading_mode = "dry_run"
    
    # Create and run bot with dashboard
    bot = TradingBotWithDashboard(config, port=args.port)
    
    # Handle shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass
    
    try:
        await bot.start()
        
        # Wait for shutdown
        await shutdown_event.wait()
        
    except KeyboardInterrupt:
        pass
    finally:
        await bot.stop()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Polymarket Arbitrage Bot with Live Dashboard"
    )
    
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Config file path"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="Dashboard port (default: 8888)"
    )
    
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run in live mode"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Run in dry-run mode (default)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(console_level=log_level)
    
    # Run
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nShutdown complete.")


if __name__ == "__main__":
    main()

