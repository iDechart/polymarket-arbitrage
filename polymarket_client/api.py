import time
import hmac
import hashlib
import requests
from urllib.parse import urljoin

class PolymarketAPI:
    def __init__(self, api_key, api_secret, passphrase, wallet_address, host="https://clob.polymarket.com"):
        self.host = host
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.wallet_address = wallet_address.lower()

    def _generate_signature(self, timestamp, method, request_path, body=""):
        """Генерация HMAC SHA256 подписи по стандарту Polymarket CLOB"""
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        secret = self.api_secret.encode('utf-8')
        return hmac.new(secret, message.encode('utf-8'), hashlib.sha256).hexdigest()

    def _get_headers(self, method, request_path, body=""):
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, method, request_path, body)
        return {
            "POLY-API-KEY": self.api_key,
            "POLY-SIG": signature,
            "POLY-TIMESTAMP": timestamp,
            "POLY-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }

    def get_positions(self):
        """Исправлено: замена устаревшего /positions на /sampling-simplified-portfolio"""
        # В документации параметры запроса входят в строку для подписи
        path = f"/sampling-simplified-portfolio?address={self.wallet_address}"
        url = urljoin(self.host, path)
        
        headers = self._get_headers("GET", path)
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                # Преобразуем ответ в формат, который ожидает остальной код бота
                data = response.json()
                return data.get("assets", []) 
            return []
        except Exception as e:
            print(f"Polymarket API Error (Positions): {e}")
            return []

    def get_order_book(self, token_id):
        """Публичный метод, не требует подписи"""
        url = f"{self.host}/book?token_id={token_id}"
        try:
            response = requests.get(url, timeout=5)
            return response.json() if response.status_code == 200 else None
        except:
            return None
