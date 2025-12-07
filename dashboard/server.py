"""
Dashboard Server
=================

FastAPI-based web server for the trading dashboard.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class DashboardState:
    """Holds the current state for the dashboard."""
    
    def __init__(self):
        self.markets: dict = {}
        self.opportunities: list = []
        self.signals: list = []
        self.orders: list = []
        self.trades: list = []
        self.portfolio: dict = {}
        self.risk: dict = {}
        self.stats: dict = {}
        self.timing: dict = {}  # Opportunity timing stats
        self.operational: dict = {}  # Operational stats
        self.is_running: bool = False
        self.mode: str = "dry_run"
        self.last_update: datetime = datetime.utcnow()
        self.started_at: datetime = datetime.utcnow()
        
        # WebSocket connections
        self._connections: list[WebSocket] = []
    
    def to_dict(self) -> dict:
        """Convert state to dictionary for JSON serialization."""
        uptime = (datetime.utcnow() - self.started_at).total_seconds()
        return {
            "markets": self.markets,
            "opportunities": self.opportunities[-50:],  # Last 50
            "signals": self.signals[-50:],
            "orders": self.orders,
            "trades": self.trades[-100:],  # Last 100
            "portfolio": self.portfolio,
            "risk": self.risk,
            "stats": self.stats,
            "timing": self.timing,  # Opportunity timing stats
            "operational": self.operational,  # Operational stats
            "is_running": self.is_running,
            "mode": self.mode,
            "last_update": self.last_update.isoformat(),
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": uptime,
        }
    
    async def broadcast(self, data: dict) -> None:
        """Broadcast update to all connected WebSocket clients."""
        if not self._connections:
            return
        
        message = json.dumps(data)
        disconnected = []
        
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self._connections.remove(ws)
    
    def add_opportunity(self, opportunity: dict) -> None:
        """Add a new opportunity."""
        opportunity["timestamp"] = datetime.utcnow().isoformat()
        self.opportunities.append(opportunity)
        if len(self.opportunities) > 200:
            self.opportunities = self.opportunities[-100:]
    
    def add_signal(self, signal: dict) -> None:
        """Add a new signal."""
        signal["timestamp"] = datetime.utcnow().isoformat()
        self.signals.append(signal)
        if len(self.signals) > 200:
            self.signals = self.signals[-100:]
    
    def add_trade(self, trade: dict) -> None:
        """Add a new trade."""
        trade["timestamp"] = datetime.utcnow().isoformat()
        self.trades.append(trade)
        if len(self.trades) > 500:
            self.trades = self.trades[-250:]


# Global state
dashboard_state = DashboardState()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Polymarket Arbitrage Dashboard",
        description="Live monitoring dashboard for the trading bot",
        version="1.0.0",
    )
    
    # Serve static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the main dashboard page."""
        html_path = Path(__file__).parent / "templates" / "index.html"
        if html_path.exists():
            return html_path.read_text()
        return get_embedded_html()
    
    @app.get("/api/state")
    async def get_state():
        """Get current dashboard state."""
        return dashboard_state.to_dict()
    
    @app.get("/api/markets")
    async def get_markets():
        """Get current market data."""
        return {"markets": dashboard_state.markets}
    
    @app.get("/api/opportunities")
    async def get_opportunities():
        """Get recent opportunities."""
        return {"opportunities": dashboard_state.opportunities[-50:]}
    
    @app.get("/api/portfolio")
    async def get_portfolio():
        """Get portfolio state."""
        return dashboard_state.portfolio
    
    @app.get("/api/risk")
    async def get_risk():
        """Get risk metrics."""
        return dashboard_state.risk
    
    @app.get("/api/timing")
    async def get_timing():
        """Get opportunity timing statistics."""
        return dashboard_state.timing
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        dashboard_state._connections.append(websocket)
        
        try:
            # Send initial state
            await websocket.send_text(json.dumps({
                "type": "initial",
                "data": dashboard_state.to_dict()
            }))
            
            # Keep connection alive and receive any commands
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    # Handle any commands from client
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except asyncio.TimeoutError:
                    # Send heartbeat
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                    
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if websocket in dashboard_state._connections:
                dashboard_state._connections.remove(websocket)
    
    return app


def get_embedded_html() -> str:
    """Return embedded HTML for the dashboard."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Arbitrage Dashboard</title>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --border-color: #2a2a3a;
            --text-primary: #e0e0e0;
            --text-secondary: #888;
            --accent-green: #00ff88;
            --accent-red: #ff4466;
            --accent-blue: #4488ff;
            --accent-yellow: #ffaa00;
            --accent-purple: #aa66ff;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-green) 0%, var(--accent-blue) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .status {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: var(--bg-card);
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-dot.running {
            background: var(--accent-green);
            box-shadow: 0 0 10px var(--accent-green);
        }
        
        .status-dot.stopped {
            background: var(--accent-red);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .mode-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .mode-badge.dry-run {
            background: var(--accent-yellow);
            color: #000;
        }
        
        .mode-badge.live {
            background: var(--accent-red);
            color: #fff;
        }
        
        .dashboard {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            grid-template-rows: auto auto 1fr;
            gap: 1rem;
            padding: 1rem;
            max-width: 1800px;
            margin: 0 auto;
        }
        
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
        }
        
        .card-header {
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card-title {
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
        }
        
        .card-body {
            padding: 1rem;
        }
        
        /* Metric Cards */
        .metrics {
            grid-column: span 4;
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 1rem;
        }
        
        .metric-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
        }
        
        .metric-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }
        
        .metric-value {
            font-size: 1.75rem;
            font-weight: 700;
        }
        
        .metric-value.positive {
            color: var(--accent-green);
        }
        
        .metric-value.negative {
            color: var(--accent-red);
        }
        
        .metric-value.neutral {
            color: var(--accent-blue);
        }
        
        .metric-change {
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }
        
        /* Opportunities Card */
        .opportunities-card {
            grid-column: span 2;
            grid-row: span 2;
        }
        
        .opportunity-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .opportunity-item {
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
            display: grid;
            grid-template-columns: auto 1fr auto;
            gap: 0.75rem;
            align-items: center;
        }
        
        .opportunity-item:last-child {
            border-bottom: none;
        }
        
        .opportunity-type {
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .opportunity-type.bundle-long {
            background: rgba(0, 255, 136, 0.2);
            color: var(--accent-green);
        }
        
        .opportunity-type.bundle-short {
            background: rgba(255, 68, 102, 0.2);
            color: var(--accent-red);
        }
        
        .opportunity-type.mm {
            background: rgba(68, 136, 255, 0.2);
            color: var(--accent-blue);
        }
        
        .opportunity-details {
            font-size: 0.8rem;
        }
        
        .opportunity-market {
            color: var(--text-primary);
            margin-bottom: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 250px;
        }
        
        .opportunity-edge {
            color: var(--accent-green);
            font-weight: 600;
        }
        
        .opportunity-time {
            font-size: 0.7rem;
            color: var(--text-secondary);
        }
        
        /* Portfolio Card */
        .portfolio-card {
            grid-column: span 2;
        }
        
        .position-list {
            max-height: 200px;
            overflow-y: auto;
        }
        
        .position-item {
            display: grid;
            grid-template-columns: 1fr auto auto;
            gap: 1rem;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.85rem;
        }
        
        .position-item:last-child {
            border-bottom: none;
        }
        
        /* Risk Card */
        .risk-card {
            grid-column: span 2;
        }
        
        .risk-bar {
            height: 8px;
            background: var(--bg-secondary);
            border-radius: 4px;
            overflow: hidden;
            margin: 0.5rem 0;
        }
        
        .risk-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        
        .risk-bar-fill.safe {
            background: var(--accent-green);
        }
        
        .risk-bar-fill.warning {
            background: var(--accent-yellow);
        }
        
        .risk-bar-fill.danger {
            background: var(--accent-red);
        }
        
        .risk-item {
            margin-bottom: 1rem;
        }
        
        .risk-label {
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            margin-bottom: 0.25rem;
        }
        
        /* Activity Feed */
        .activity-card {
            grid-column: span 2;
            grid-row: span 2;
        }
        
        .activity-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .activity-item {
            padding: 0.5rem;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.8rem;
            display: flex;
            gap: 0.75rem;
            align-items: flex-start;
        }
        
        .activity-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            flex-shrink: 0;
        }
        
        .activity-icon.order {
            background: rgba(68, 136, 255, 0.2);
            color: var(--accent-blue);
        }
        
        .activity-icon.fill {
            background: rgba(0, 255, 136, 0.2);
            color: var(--accent-green);
        }
        
        .activity-icon.cancel {
            background: rgba(255, 68, 102, 0.2);
            color: var(--accent-red);
        }
        
        .activity-icon.signal {
            background: rgba(170, 102, 255, 0.2);
            color: var(--accent-purple);
        }
        
        .activity-content {
            flex: 1;
        }
        
        .activity-message {
            color: var(--text-primary);
        }
        
        .activity-time {
            color: var(--text-secondary);
            font-size: 0.7rem;
        }
        
        /* Operational Stats Card */
        .operational-card {
            grid-column: span 2;
        }
        
        .op-stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
        }
        
        .op-stat {
            background: var(--bg-secondary);
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }
        
        .op-stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent-blue);
        }
        
        .op-stat-value.active {
            color: var(--accent-green);
        }
        
        .op-stat-label {
            font-size: 0.7rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-top: 0.25rem;
        }
        
        .uptime-display {
            text-align: center;
            padding: 1rem;
            margin-top: 0.75rem;
            background: var(--bg-secondary);
            border-radius: 8px;
        }
        
        .uptime-value {
            font-size: 1.25rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            color: var(--accent-green);
        }
        
        /* Timing Card */
        .timing-card {
            grid-column: span 2;
        }
        
        .timing-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }
        
        .timing-stat {
            text-align: center;
            padding: 0.75rem;
            background: var(--bg-secondary);
            border-radius: 8px;
        }
        
        .timing-stat-value {
            font-size: 1.5rem;
            font-weight: 700;
        }
        
        .timing-stat-value.fast {
            color: var(--accent-green);
        }
        
        .timing-stat-value.medium {
            color: var(--accent-yellow);
        }
        
        .timing-stat-value.slow {
            color: var(--accent-red);
        }
        
        .timing-stat-label {
            font-size: 0.7rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-top: 0.25rem;
        }
        
        .timing-buckets {
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        
        .timing-bucket {
            flex: 1;
            text-align: center;
            padding: 0.5rem;
            background: var(--bg-secondary);
            border-radius: 6px;
            font-size: 0.75rem;
        }
        
        .timing-bucket-count {
            font-size: 1.25rem;
            font-weight: 600;
            display: block;
        }
        
        .timing-bucket.fast .timing-bucket-count {
            color: var(--accent-green);
        }
        
        .timing-bucket.medium .timing-bucket-count {
            color: var(--accent-blue);
        }
        
        .timing-bucket.slow .timing-bucket-count {
            color: var(--accent-yellow);
        }
        
        .timing-bucket.very-slow .timing-bucket-count {
            color: var(--accent-red);
        }
        
        .timing-recent {
            margin-top: 1rem;
            max-height: 150px;
            overflow-y: auto;
        }
        
        .timing-recent-item {
            display: flex;
            justify-content: space-between;
            padding: 0.25rem 0;
            font-size: 0.75rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        .timing-duration {
            font-weight: 600;
        }
        
        .timing-duration.fast { color: var(--accent-green); }
        .timing-duration.medium { color: var(--accent-yellow); }
        .timing-duration.slow { color: var(--accent-red); }
        
        /* Markets Card */
        .markets-card {
            grid-column: span 2;
        }
        
        .market-item {
            display: grid;
            grid-template-columns: 1fr auto auto auto;
            gap: 1rem;
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.85rem;
        }
        
        .market-name {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .market-price {
            font-weight: 600;
        }
        
        .market-spread {
            color: var(--text-secondary);
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-secondary);
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
        }
        
        .empty-icon {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        /* Connection Status */
        .connection-status {
            position: fixed;
            bottom: 1rem;
            right: 1rem;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.75rem;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
        }
        
        .connection-status.connected {
            border-color: var(--accent-green);
        }
        
        .connection-status.disconnected {
            border-color: var(--accent-red);
        }
        
        @media (max-width: 1400px) {
            .dashboard {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .metrics {
                grid-column: span 2;
                grid-template-columns: repeat(3, 1fr);
            }
            
            .opportunities-card,
            .activity-card {
                grid-column: span 2;
                grid-row: span 1;
            }
            
            .portfolio-card,
            .risk-card,
            .markets-card {
                grid-column: span 2;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">⚡ Polymarket Arbitrage</div>
        <div class="status">
            <div class="status-indicator">
                <span class="status-dot" id="statusDot"></span>
                <span id="statusText">Connecting...</span>
            </div>
            <span class="mode-badge" id="modeBadge">DRY RUN</span>
        </div>
    </header>
    
    <main class="dashboard">
        <!-- Metrics Row -->
        <section class="metrics">
            <div class="metric-card">
                <div class="metric-label">Total PnL</div>
                <div class="metric-value" id="totalPnl">$0.00</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Realized PnL</div>
                <div class="metric-value" id="realizedPnl">$0.00</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Exposure</div>
                <div class="metric-value neutral" id="exposure">$0.00</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Open Orders</div>
                <div class="metric-value neutral" id="openOrders">0</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Opportunities</div>
                <div class="metric-value neutral" id="opportunityCount">0</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value" id="winRate">0%</div>
            </div>
        </section>
        
        <!-- Opportunities -->
        <section class="card opportunities-card">
            <div class="card-header">
                <span class="card-title">Live Opportunities</span>
                <span id="oppRefresh" style="font-size: 0.7rem; color: var(--text-secondary);"></span>
            </div>
            <div class="card-body">
                <div class="opportunity-list" id="opportunityList">
                    <div class="empty-state">
                        <div class="empty-icon">📊</div>
                        <div>Waiting for opportunities...</div>
                    </div>
                </div>
            </div>
        </section>
        
        <!-- Activity Feed -->
        <section class="card activity-card">
            <div class="card-header">
                <span class="card-title">Activity Feed</span>
            </div>
            <div class="card-body">
                <div class="activity-list" id="activityList">
                    <div class="empty-state">
                        <div class="empty-icon">📝</div>
                        <div>No activity yet...</div>
                    </div>
                </div>
            </div>
        </section>
        
        <!-- Portfolio -->
        <section class="card portfolio-card">
            <div class="card-header">
                <span class="card-title">Positions</span>
            </div>
            <div class="card-body">
                <div class="position-list" id="positionList">
                    <div class="empty-state">
                        <div class="empty-icon">💼</div>
                        <div>No open positions</div>
                    </div>
                </div>
            </div>
        </section>
        
        <!-- Risk -->
        <section class="card risk-card">
            <div class="card-header">
                <span class="card-title">Risk Metrics</span>
            </div>
            <div class="card-body">
                <div class="risk-item">
                    <div class="risk-label">
                        <span>Global Exposure</span>
                        <span id="riskExposure">$0 / $5,000</span>
                    </div>
                    <div class="risk-bar">
                        <div class="risk-bar-fill safe" id="exposureBar" style="width: 0%"></div>
                    </div>
                </div>
                <div class="risk-item">
                    <div class="risk-label">
                        <span>Daily P&L</span>
                        <span id="riskDailyPnl">$0 / -$500</span>
                    </div>
                    <div class="risk-bar">
                        <div class="risk-bar-fill safe" id="dailyPnlBar" style="width: 0%"></div>
                    </div>
                </div>
                <div class="risk-item">
                    <div class="risk-label">
                        <span>Drawdown</span>
                        <span id="riskDrawdown">0% / 10%</span>
                    </div>
                    <div class="risk-bar">
                        <div class="risk-bar-fill safe" id="drawdownBar" style="width: 0%"></div>
                    </div>
                </div>
                <div id="killSwitch" style="display: none; padding: 0.75rem; background: rgba(255,68,102,0.2); border-radius: 8px; text-align: center; color: var(--accent-red); font-weight: 600;">
                    ⚠️ KILL SWITCH ACTIVE
                </div>
            </div>
        </section>
        
        <!-- Operational Stats -->
        <section class="card operational-card">
            <div class="card-header">
                <span class="card-title">🔄 Operational Stats</span>
                <span id="streamStatus" style="font-size: 0.75rem; color: var(--accent-green);">● Streaming</span>
            </div>
            <div class="card-body">
                <div class="op-stats-grid">
                    <div class="op-stat">
                        <div class="op-stat-value" id="totalMarkets">0</div>
                        <div class="op-stat-label">Total Markets</div>
                    </div>
                    <div class="op-stat">
                        <div class="op-stat-value" id="marketsWithData">0</div>
                        <div class="op-stat-label">With Order Books</div>
                    </div>
                    <div class="op-stat">
                        <div class="op-stat-value" id="marketsWithPrices">0</div>
                        <div class="op-stat-label">With Prices</div>
                    </div>
                    <div class="op-stat">
                        <div class="op-stat-value active" id="orderbookUpdates">0</div>
                        <div class="op-stat-label">Orderbook Updates</div>
                    </div>
                    <div class="op-stat">
                        <div class="op-stat-value" id="cycleTime">--</div>
                        <div class="op-stat-label">Est. Cycle Time</div>
                    </div>
                    <div class="op-stat">
                        <div class="op-stat-value" id="updatesPerMin">0</div>
                        <div class="op-stat-label">Updates/Min</div>
                    </div>
                </div>
                <div class="uptime-display">
                    <span style="color: var(--text-secondary); font-size: 0.75rem;">UPTIME: </span>
                    <span class="uptime-value" id="uptime">00:00:00</span>
                </div>
            </div>
        </section>
        
        <!-- Opportunity Timing -->
        <section class="card timing-card">
            <div class="card-header">
                <span class="card-title">⏱️ Opportunity Timing</span>
                <span id="timingCount" style="font-size: 0.75rem; color: var(--text-secondary);">0 tracked</span>
            </div>
            <div class="card-body">
                <div class="timing-stats">
                    <div class="timing-stat">
                        <div class="timing-stat-value" id="avgDuration">--</div>
                        <div class="timing-stat-label">Avg Duration</div>
                    </div>
                    <div class="timing-stat">
                        <div class="timing-stat-value" id="minDuration">--</div>
                        <div class="timing-stat-label">Min Duration</div>
                    </div>
                    <div class="timing-stat">
                        <div class="timing-stat-value" id="maxDuration">--</div>
                        <div class="timing-stat-label">Max Duration</div>
                    </div>
                    <div class="timing-stat">
                        <div class="timing-stat-value" id="activeOpps">0</div>
                        <div class="timing-stat-label">Active Now</div>
                    </div>
                </div>
                <div class="timing-buckets">
                    <div class="timing-bucket fast">
                        <span class="timing-bucket-count" id="under100ms">0</span>
                        <div>&lt;100ms</div>
                    </div>
                    <div class="timing-bucket medium">
                        <span class="timing-bucket-count" id="under500ms">0</span>
                        <div>&lt;500ms</div>
                    </div>
                    <div class="timing-bucket slow">
                        <span class="timing-bucket-count" id="under1s">0</span>
                        <div>&lt;1s</div>
                    </div>
                    <div class="timing-bucket very-slow">
                        <span class="timing-bucket-count" id="over1s">0</span>
                        <div>&gt;1s</div>
                    </div>
                </div>
                <div class="timing-recent" id="recentTimings">
                    <div style="text-align: center; color: var(--text-secondary); padding: 1rem;">
                        Waiting for opportunity data...
                    </div>
                </div>
            </div>
        </section>
        
        <!-- Markets -->
        <section class="card markets-card">
            <div class="card-header">
                <span class="card-title">Monitored Markets</span>
            </div>
            <div class="card-body">
                <div id="marketList">
                    <div class="empty-state">
                        <div class="empty-icon">📈</div>
                        <div>Loading markets...</div>
                    </div>
                </div>
            </div>
        </section>
    </main>
    
    <div class="connection-status" id="connectionStatus">
        Connecting...
    </div>
    
    <script>
        let ws = null;
        let state = {};
        let reconnectAttempts = 0;
        
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                document.getElementById('connectionStatus').textContent = '🟢 Connected';
                document.getElementById('connectionStatus').className = 'connection-status connected';
                reconnectAttempts = 0;
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                document.getElementById('connectionStatus').textContent = '🔴 Disconnected';
                document.getElementById('connectionStatus').className = 'connection-status disconnected';
                setTimeout(reconnect, Math.min(1000 * Math.pow(2, reconnectAttempts), 30000));
                reconnectAttempts++;
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                
                if (msg.type === 'initial' || msg.type === 'update') {
                    state = msg.data || msg;
                    updateDashboard();
                } else if (msg.type === 'opportunity') {
                    addOpportunity(msg.data);
                } else if (msg.type === 'activity') {
                    addActivity(msg.data);
                }
            };
        }
        
        function reconnect() {
            if (ws && ws.readyState === WebSocket.OPEN) return;
            connect();
        }
        
        function updateDashboard() {
            // Status
            const statusDot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');
            if (state.is_running) {
                statusDot.className = 'status-dot running';
                statusText.textContent = 'Running';
            } else {
                statusDot.className = 'status-dot stopped';
                statusText.textContent = 'Stopped';
            }
            
            // Mode
            const modeBadge = document.getElementById('modeBadge');
            if (state.mode === 'live') {
                modeBadge.className = 'mode-badge live';
                modeBadge.textContent = 'LIVE';
            } else {
                modeBadge.className = 'mode-badge dry-run';
                modeBadge.textContent = 'DRY RUN';
            }
            
            // Metrics
            updateMetrics();
            
            // Opportunities
            updateOpportunities();
            
            // Activity
            updateActivity();
            
            // Risk
            updateRisk();
            
            // Timing
            updateTiming();
            
            // Operational
            updateOperational();
            
            // Markets
            updateMarkets();
        }
        
        function updateMetrics() {
            const portfolio = state.portfolio || {};
            const pnl = portfolio.pnl || {};
            const stats = state.stats || {};
            
            const totalPnl = pnl.total_pnl || 0;
            const realizedPnl = pnl.realized_pnl || 0;
            const exposure = portfolio.total_exposure || 0;
            const winRate = (portfolio.win_rate || 0) * 100;
            
            document.getElementById('totalPnl').textContent = formatCurrency(totalPnl);
            document.getElementById('totalPnl').className = `metric-value ${totalPnl >= 0 ? 'positive' : 'negative'}`;
            
            document.getElementById('realizedPnl').textContent = formatCurrency(realizedPnl);
            document.getElementById('realizedPnl').className = `metric-value ${realizedPnl >= 0 ? 'positive' : 'negative'}`;
            
            document.getElementById('exposure').textContent = formatCurrency(exposure);
            document.getElementById('openOrders').textContent = (state.orders || []).length;
            document.getElementById('opportunityCount').textContent = (state.opportunities || []).length;
            document.getElementById('winRate').textContent = `${winRate.toFixed(1)}%`;
            document.getElementById('winRate').className = `metric-value ${winRate >= 50 ? 'positive' : winRate > 0 ? 'neutral' : 'negative'}`;
        }
        
        function updateOpportunities() {
            const list = document.getElementById('opportunityList');
            const opportunities = state.opportunities || [];
            
            if (opportunities.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-icon">📊</div><div>Waiting for opportunities...</div></div>';
                return;
            }
            
            const recent = opportunities.slice(-20).reverse();
            list.innerHTML = recent.map(opp => {
                const typeClass = opp.type?.includes('bundle') ? 
                    (opp.type.includes('long') ? 'bundle-long' : 'bundle-short') : 'mm';
                const typeLabel = opp.type?.replace('_', ' ').toUpperCase() || 'UNKNOWN';
                
                return `
                    <div class="opportunity-item">
                        <span class="opportunity-type ${typeClass}">${typeLabel}</span>
                        <div class="opportunity-details">
                            <div class="opportunity-market">${opp.market_id || 'Unknown'}</div>
                            <span class="opportunity-edge">Edge: ${((opp.edge || 0) * 100).toFixed(2)}%</span>
                        </div>
                        <span class="opportunity-time">${formatTime(opp.timestamp)}</span>
                    </div>
                `;
            }).join('');
            
            document.getElementById('oppRefresh').textContent = `Last: ${formatTime(state.last_update)}`;
        }
        
        function updateActivity() {
            const list = document.getElementById('activityList');
            const signals = state.signals || [];
            const trades = state.trades || [];
            
            // Combine and sort by timestamp
            const activities = [
                ...signals.map(s => ({...s, activityType: 'signal'})),
                ...trades.map(t => ({...t, activityType: 'trade'}))
            ].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).slice(0, 30);
            
            if (activities.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-icon">📝</div><div>No activity yet...</div></div>';
                return;
            }
            
            list.innerHTML = activities.map(act => {
                let icon = '📋';
                let iconClass = 'signal';
                let message = '';
                
                if (act.activityType === 'trade') {
                    icon = '✓';
                    iconClass = 'fill';
                    message = `${act.side} ${(act.size || 0).toFixed(2)} @ ${(act.price || 0).toFixed(4)}`;
                } else {
                    icon = '→';
                    iconClass = 'signal';
                    message = `${act.action || 'Signal'}: ${act.market_id || ''}`;
                }
                
                return `
                    <div class="activity-item">
                        <div class="activity-icon ${iconClass}">${icon}</div>
                        <div class="activity-content">
                            <div class="activity-message">${message}</div>
                            <div class="activity-time">${formatTime(act.timestamp)}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function updateRisk() {
            const risk = state.risk || {};
            
            const exposure = risk.global_exposure || 0;
            const maxExposure = risk.max_global_exposure || 5000;
            const exposurePct = (exposure / maxExposure) * 100;
            
            document.getElementById('riskExposure').textContent = `$${exposure.toFixed(0)} / $${maxExposure.toLocaleString()}`;
            document.getElementById('exposureBar').style.width = `${Math.min(exposurePct, 100)}%`;
            document.getElementById('exposureBar').className = `risk-bar-fill ${exposurePct < 60 ? 'safe' : exposurePct < 80 ? 'warning' : 'danger'}`;
            
            const dailyPnl = risk.daily_pnl || 0;
            const maxLoss = risk.max_daily_loss || 500;
            const dailyPnlPct = Math.abs(Math.min(dailyPnl, 0)) / maxLoss * 100;
            
            document.getElementById('riskDailyPnl').textContent = `$${dailyPnl.toFixed(2)} / -$${maxLoss}`;
            document.getElementById('dailyPnlBar').style.width = `${Math.min(dailyPnlPct, 100)}%`;
            document.getElementById('dailyPnlBar').className = `risk-bar-fill ${dailyPnlPct < 50 ? 'safe' : dailyPnlPct < 80 ? 'warning' : 'danger'}`;
            
            const drawdown = (risk.current_drawdown_pct || 0);
            const maxDrawdown = (risk.max_drawdown_pct || 10);
            const drawdownPct = (drawdown / maxDrawdown) * 100;
            
            document.getElementById('riskDrawdown').textContent = `${drawdown.toFixed(1)}% / ${maxDrawdown}%`;
            document.getElementById('drawdownBar').style.width = `${Math.min(drawdownPct, 100)}%`;
            document.getElementById('drawdownBar').className = `risk-bar-fill ${drawdownPct < 50 ? 'safe' : drawdownPct < 80 ? 'warning' : 'danger'}`;
            
            document.getElementById('killSwitch').style.display = risk.kill_switch_triggered ? 'block' : 'none';
        }
        
        function updateTiming() {
            const timing = state.timing || {};
            
            // Update count
            document.getElementById('timingCount').textContent = `${timing.total_tracked || 0} tracked`;
            
            // Update main stats
            const avgDuration = timing.avg_duration_ms;
            if (avgDuration !== undefined && avgDuration !== null) {
                document.getElementById('avgDuration').textContent = formatDuration(avgDuration);
                document.getElementById('avgDuration').className = `timing-stat-value ${getDurationClass(avgDuration)}`;
            }
            
            const minDuration = timing.min_duration_ms;
            if (minDuration !== undefined && minDuration !== null) {
                document.getElementById('minDuration').textContent = formatDuration(minDuration);
                document.getElementById('minDuration').className = `timing-stat-value ${getDurationClass(minDuration)}`;
            }
            
            const maxDuration = timing.max_duration_ms;
            if (maxDuration !== undefined && maxDuration !== null) {
                document.getElementById('maxDuration').textContent = formatDuration(maxDuration);
                document.getElementById('maxDuration').className = `timing-stat-value ${getDurationClass(maxDuration)}`;
            }
            
            document.getElementById('activeOpps').textContent = timing.active_opportunities || 0;
            
            // Update buckets
            document.getElementById('under100ms').textContent = timing.under_100ms || 0;
            document.getElementById('under500ms').textContent = timing.under_500ms || 0;
            document.getElementById('under1s').textContent = timing.under_1s || 0;
            document.getElementById('over1s').textContent = timing.over_1s || 0;
            
            // Update recent timings
            const recentList = document.getElementById('recentTimings');
            const recent = timing.recent_durations || [];
            
            if (recent.length === 0) {
                recentList.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 1rem;">Waiting for opportunity data...</div>';
                return;
            }
            
            recentList.innerHTML = recent.slice().reverse().map(item => {
                const durationClass = getDurationClass(item.duration_ms);
                const typeLabel = item.type?.replace('_', ' ') || 'unknown';
                const executedBadge = item.executed ? '<span style="color: var(--accent-green);">✓</span>' : '';
                
                return `
                    <div class="timing-recent-item">
                        <span>${typeLabel} ${executedBadge}</span>
                        <span class="timing-duration ${durationClass}">${formatDuration(item.duration_ms)}</span>
                    </div>
                `;
            }).join('');
        }
        
        function formatDuration(ms) {
            if (ms === undefined || ms === null) return '--';
            if (ms < 1000) return `${Math.round(ms)}ms`;
            return `${(ms / 1000).toFixed(1)}s`;
        }
        
        function getDurationClass(ms) {
            if (ms < 200) return 'fast';
            if (ms < 1000) return 'medium';
            return 'slow';
        }
        
        let lastUpdateCount = 0;
        let lastUpdateTime = Date.now();
        
        function updateOperational() {
            const op = state.operational || {};
            
            // Update stats
            document.getElementById('totalMarkets').textContent = op.total_markets || 0;
            document.getElementById('marketsWithData').textContent = op.markets_with_orderbooks || 0;
            document.getElementById('marketsWithPrices').textContent = op.markets_with_prices || 0;
            document.getElementById('orderbookUpdates').textContent = formatNumber(op.orderbook_updates || 0);
            
            // Calculate updates per minute
            const now = Date.now();
            const timeDiff = (now - lastUpdateTime) / 1000; // seconds
            const updateDiff = (op.orderbook_updates || 0) - lastUpdateCount;
            
            if (timeDiff > 0 && lastUpdateCount > 0) {
                const updatesPerMin = Math.round((updateDiff / timeDiff) * 60);
                document.getElementById('updatesPerMin').textContent = updatesPerMin;
            }
            
            lastUpdateCount = op.orderbook_updates || 0;
            lastUpdateTime = now;
            
            // Estimate cycle time (time to check all markets)
            const totalMarkets = op.total_markets || 1;
            const updatesPerSec = (op.orderbook_updates || 0) / Math.max(state.uptime_seconds || 1, 1);
            if (updatesPerSec > 0) {
                const cycleSeconds = totalMarkets / updatesPerSec;
                document.getElementById('cycleTime').textContent = formatCycleTime(cycleSeconds);
            }
            
            // Stream status
            const statusEl = document.getElementById('streamStatus');
            if (op.is_streaming) {
                statusEl.textContent = '● Streaming';
                statusEl.style.color = 'var(--accent-green)';
            } else {
                statusEl.textContent = '○ Stopped';
                statusEl.style.color = 'var(--accent-red)';
            }
            
            // Uptime
            if (state.uptime_seconds) {
                document.getElementById('uptime').textContent = formatUptime(state.uptime_seconds);
            }
        }
        
        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toString();
        }
        
        function formatCycleTime(seconds) {
            if (seconds < 60) return Math.round(seconds) + 's';
            if (seconds < 3600) return Math.round(seconds / 60) + 'm';
            return (seconds / 3600).toFixed(1) + 'h';
        }
        
        function formatUptime(seconds) {
            const hrs = Math.floor(seconds / 3600);
            const mins = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        
        function updateMarkets() {
            const list = document.getElementById('marketList');
            const markets = state.markets || {};
            const marketIds = Object.keys(markets);
            
            if (marketIds.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-icon">📈</div><div>No markets loaded</div></div>';
                return;
            }
            
            list.innerHTML = marketIds.slice(0, 10).map(id => {
                const m = markets[id];
                const bid = m.best_bid_yes || 0;
                const ask = m.best_ask_yes || 0;
                const spread = ask - bid;
                
                return `
                    <div class="market-item">
                        <span class="market-name">${m.question || id}</span>
                        <span class="market-price">${bid.toFixed(2)}/${ask.toFixed(2)}</span>
                        <span class="market-spread">${(spread * 100).toFixed(1)}c</span>
                    </div>
                `;
            }).join('');
        }
        
        function formatCurrency(value) {
            const sign = value >= 0 ? '' : '-';
            return `${sign}$${Math.abs(value).toFixed(2)}`;
        }
        
        function formatTime(timestamp) {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            return date.toLocaleTimeString();
        }
        
        function addOpportunity(opp) {
            if (!state.opportunities) state.opportunities = [];
            state.opportunities.push(opp);
            updateOpportunities();
        }
        
        function addActivity(activity) {
            if (!state.signals) state.signals = [];
            state.signals.push(activity);
            updateActivity();
        }
        
        // Ping to keep connection alive
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'ping'}));
            }
        }, 25000);
        
        // Fetch initial state via REST as backup
        async function fetchState() {
            try {
                const response = await fetch('/api/state');
                state = await response.json();
                updateDashboard();
            } catch (e) {
                console.error('Failed to fetch state:', e);
            }
        }
        
        // Initial load
        connect();
        fetchState();
        
        // Periodic refresh as backup
        setInterval(fetchState, 5000);
    </script>
</body>
</html>'''


# Create the app
app = create_app()

