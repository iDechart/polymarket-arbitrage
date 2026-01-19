import time
import hmac
import hashlib
import requests
from urllib.parse import urljoin

class PolymarketClient:
    def __init__(self, api_key, api_secret, passphrase, wallet_address, host="https://clob.polymarket.com"):
        self.host = host
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.wallet_address = wallet_address

    def _generate_signature(self, timestamp, method, request_path, body=""):
        """Генерация подписи согласно документации Polymarket"""
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        secret = self.api_secret.encode('utf-8')
        signature = hmac.new(secret, message.encode('utf-8'), hashlib.sha256)
        return signature.hexdigest()

    def _get_headers(self, method, request_path, body=""):
        """Формирование обязательных заголовков авторизации"""
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
        """
        Исправленный метод: вместо /positions используем актуальный портфель.
        Запрос требует указания адреса кошелька в параметрах.
        """
        path = f"/sampling-simplified-portfolio?address={self.wallet_address}"
        url = urljoin(self.host, path)
        
        try:
            headers = self._get_headers("GET", path)
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"Ошибка 404: Эндпоинт {path} не найден. Проверьте актуальность API.")
            else:
                print(f"Ошибка API: {response.status_code} - {response.text}")
            return None
        except Exception as e:
            print(f"Ошибка при получении позиций: {e}")
            return None

    def get_balance(self):
        """Проверка баланса USDC и разрешений (Allowance)"""
        path = f"/balance-allowance?address={self.wallet_address}&asset_id=0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
        url = urljoin(self.host, path)
        
        headers = self._get_headers("GET", path)
        response = requests.get(url, headers=headers)
        return response.json() if response.status_code == 200 else None
