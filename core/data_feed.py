import logging

class DataFeed:
    def __init__(self, poly_client, kalshi_client, config):
        self.poly = poly_client
        self.kalshi = kalshi_client
        self.config = config
        self.portfolio = {"poly": [], "kalshi": []}

    def update_portfolios(self):
        """Обновление данных о позициях с учетом новых эндпоинтов"""
        # Polymarket
        poly_pos = self.poly.get_positions()
        if poly_pos is not None:
            # Приводим к единому формату: [{'asset_id': '...', 'size': 10}, ...]
            self.portfolio["poly"] = [
                {
                    "asset_id": p.get("asset_id") or p.get("token_id"), 
                    "size": float(p.get("size", 0))
                } 
                for p in poly_pos if float(p.get("size", 0)) != 0
            ]
            logging.info(f"Updated Polymarket portfolio: {len(self.portfolio['poly'])} active positions")
        else:
            logging.warning("Failed to update Polymarket portfolio (check API keys/Auth)")

        # Kalshi (если реализован)
        # self.portfolio["kalshi"] = self.kalshi.get_positions()
