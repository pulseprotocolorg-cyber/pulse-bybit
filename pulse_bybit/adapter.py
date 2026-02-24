"""Bybit V5 adapter for PULSE Protocol.

Translates PULSE semantic messages to Bybit V5 unified API.
Same interface as BinanceAdapter — swap exchanges in one line.

Example:
    >>> adapter = BybitAdapter(api_key="...", api_secret="...")
    >>> msg = PulseMessage(
    ...     action="ACT.QUERY.DATA",
    ...     parameters={"symbol": "BTCUSDT"}
    ... )
    >>> response = adapter.send(msg)
"""

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional

import requests

from pulse.message import PulseMessage
from pulse.adapter import PulseAdapter, AdapterError, AdapterConnectionError


# Bybit V5 API endpoints
ENDPOINTS = {
    "tickers": "/v5/market/tickers",
    "kline": "/v5/market/kline",
    "orderbook": "/v5/market/orderbook",
    "server_time": "/v5/market/time",
    "place_order": "/v5/order/create",
    "cancel_order": "/v5/order/cancel",
    "order_detail": "/v5/order/realtime",
    "open_orders": "/v5/order/realtime",
    "wallet_balance": "/v5/account/wallet-balance",
}

# Map PULSE actions to Bybit operations
ACTION_MAP = {
    "ACT.QUERY.DATA": "query",
    "ACT.QUERY.STATUS": "order_status",
    "ACT.TRANSACT.REQUEST": "place_order",
    "ACT.CANCEL": "cancel_order",
    "ACT.QUERY.LIST": "open_orders",
    "ACT.QUERY.BALANCE": "wallet_balance",
}


class BybitAdapter(PulseAdapter):
    """PULSE adapter for Bybit exchange (V5 API).

    Translates PULSE semantic actions to Bybit V5 unified API.
    Same interface as BinanceAdapter — switch exchanges in one line.

    Supported PULSE actions:
        - ACT.QUERY.DATA — get ticker price, klines, order book
        - ACT.QUERY.STATUS — check order status
        - ACT.QUERY.LIST — list open orders
        - ACT.QUERY.BALANCE — get wallet balance
        - ACT.TRANSACT.REQUEST — place an order (BUY/SELL)
        - ACT.CANCEL — cancel an order

    Example:
        >>> # Switch from Binance to Bybit — one line change
        >>> # adapter = BinanceAdapter(api_key="...", api_secret="...")
        >>> adapter = BybitAdapter(api_key="...", api_secret="...")
        >>> msg = PulseMessage(
        ...     action="ACT.QUERY.DATA",
        ...     parameters={"symbol": "BTCUSDT"}
        ... )
        >>> response = adapter.send(msg)
    """

    BASE_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        base_url = self.TESTNET_URL if testnet else self.BASE_URL
        super().__init__(
            name="bybit",
            base_url=base_url,
            config=config or {},
        )
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._session: Optional[requests.Session] = None
        self._recv_window = "20000"
        self._time_offset = 0  # Local vs server time difference in ms

    def connect(self) -> None:
        """Initialize HTTP session and verify connectivity."""
        self._session = requests.Session()

        try:
            resp = self._session.get(f"{self.base_url}{ENDPOINTS['server_time']}", timeout=10)
            resp.raise_for_status()
            server_time = resp.json().get("result", {}).get("timeSecond", None)
            if server_time:
                self._time_offset = int(server_time) * 1000 - int(time.time() * 1000)
            self.connected = True
        except requests.ConnectionError as e:
            raise AdapterConnectionError(f"Cannot reach Bybit API: {e}") from e
        except requests.HTTPError as e:
            raise AdapterConnectionError(f"Bybit API error: {e}") from e

    def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            self._session.close()
        self._session = None
        self.connected = False

    def to_native(self, message: PulseMessage) -> Dict[str, Any]:
        """Convert PULSE message to Bybit API request."""
        action = message.content["action"]
        params = message.content.get("parameters", {})
        operation = ACTION_MAP.get(action)

        if not operation:
            raise AdapterError(
                f"Unsupported action '{action}'. Supported: {list(ACTION_MAP.keys())}"
            )

        if operation == "query":
            return self._build_query_request(params)
        elif operation == "place_order":
            return self._build_order_request(params)
        elif operation == "cancel_order":
            return self._build_cancel_request(params)
        elif operation == "order_status":
            return self._build_status_request(params)
        elif operation == "open_orders":
            return self._build_open_orders_request(params)
        elif operation == "wallet_balance":
            return self._build_balance_request(params)

        raise AdapterError(f"Unknown operation: {operation}")

    def call_api(self, native_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Bybit API call."""
        if not self._session:
            self._ensure_session()

        method = native_request["method"]
        url = f"{self.base_url}{native_request['endpoint']}"
        params = native_request.get("params", {})
        signed = native_request.get("signed", False)

        try:
            if method == "GET":
                headers = self._sign_get(params) if signed else {}
                resp = self._session.get(url, params=params, headers=headers, timeout=10)
            elif method == "POST":
                headers = self._sign_post(params) if signed else {"Content-Type": "application/json"}
                resp = self._session.post(url, json=params, headers=headers, timeout=10)
            else:
                raise AdapterError(f"Unknown HTTP method: {method}")

            data = resp.json()

            # Bybit V5 uses retCode for errors
            ret_code = data.get("retCode", 0)
            if ret_code != 0:
                ret_msg = data.get("retMsg", "Unknown error")
                raise AdapterError(f"Bybit error {ret_code}: {ret_msg}")

            return data.get("result", data)

        except (requests.ConnectionError, ConnectionError) as e:
            raise AdapterConnectionError(f"Cannot reach Bybit: {e}") from e
        except (requests.Timeout, TimeoutError) as e:
            raise AdapterConnectionError(f"Bybit request timed out: {e}") from e
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(f"Bybit request failed: {e}") from e

    def from_native(self, native_response: Any) -> PulseMessage:
        """Convert Bybit response to PULSE message."""
        return PulseMessage(
            action="ACT.RESPOND",
            parameters={"result": native_response},
            validate=False,
        )

    @property
    def supported_actions(self) -> List[str]:
        return list(ACTION_MAP.keys())

    # --- Request Builders ---

    def _build_query_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build market data query."""
        symbol = params.get("symbol")
        query_type = params.get("type", "price")
        category = params.get("category", "spot")

        if query_type in ("price", "24h"):
            req_params = {"category": category}
            if symbol:
                req_params["symbol"] = symbol.upper()
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["tickers"],
                "params": req_params,
                "signed": False,
            }

        elif query_type == "klines":
            if not symbol:
                raise AdapterError("Symbol required for klines query.")
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["kline"],
                "params": {
                    "category": category,
                    "symbol": symbol.upper(),
                    "interval": params.get("interval", "60"),
                    "limit": params.get("limit", 100),
                },
                "signed": False,
            }

        elif query_type == "depth":
            if not symbol:
                raise AdapterError("Symbol required for depth query.")
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["orderbook"],
                "params": {
                    "category": category,
                    "symbol": symbol.upper(),
                    "limit": params.get("limit", 20),
                },
                "signed": False,
            }

        raise AdapterError(f"Unknown query type '{query_type}'. Use: price, 24h, klines, depth.")

    def _build_order_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order placement request."""
        required = ["symbol", "side", "quantity"]
        for field in required:
            if field not in params:
                raise AdapterError(f"Missing required field '{field}' for order placement.")

        order_params = {
            "category": params.get("category", "spot"),
            "symbol": params["symbol"].upper(),
            "side": "Buy" if params["side"].upper() == "BUY" else "Sell",
            "orderType": params.get("order_type", "Market"),
            "qty": str(params["quantity"]),
        }

        if order_params["orderType"].upper() == "LIMIT":
            if "price" not in params:
                raise AdapterError("Price required for LIMIT orders.")
            order_params["orderType"] = "Limit"
            order_params["price"] = str(params["price"])
            order_params["timeInForce"] = params.get("time_in_force", "GTC")

        return {
            "method": "POST",
            "endpoint": ENDPOINTS["place_order"],
            "params": order_params,
            "signed": True,
        }

    def _build_cancel_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order cancellation request."""
        if "symbol" not in params:
            raise AdapterError("Symbol required for order cancellation.")
        if "order_id" not in params:
            raise AdapterError("Order ID required for cancellation.")

        return {
            "method": "POST",
            "endpoint": ENDPOINTS["cancel_order"],
            "params": {
                "category": params.get("category", "spot"),
                "symbol": params["symbol"].upper(),
                "orderId": str(params["order_id"]),
            },
            "signed": True,
        }

    def _build_status_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order status query."""
        if "symbol" not in params:
            raise AdapterError("Symbol required for order status query.")
        if "order_id" not in params:
            raise AdapterError("Order ID required for status query.")

        return {
            "method": "GET",
            "endpoint": ENDPOINTS["order_detail"],
            "params": {
                "category": params.get("category", "spot"),
                "symbol": params["symbol"].upper(),
                "orderId": str(params["order_id"]),
            },
            "signed": True,
        }

    def _build_open_orders_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build open orders query."""
        req_params = {"category": params.get("category", "spot")}
        if "symbol" in params:
            req_params["symbol"] = params["symbol"].upper()

        return {
            "method": "GET",
            "endpoint": ENDPOINTS["open_orders"],
            "params": req_params,
            "signed": True,
        }

    def _build_balance_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build wallet balance query."""
        return {
            "method": "GET",
            "endpoint": ENDPOINTS["wallet_balance"],
            "params": {
                "accountType": params.get("account_type", "UNIFIED"),
            },
            "signed": True,
        }

    # --- Signing ---

    def _sign_get(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Generate authentication headers for GET requests."""
        if not self._api_key or not self._api_secret:
            raise AdapterError("API key and secret required for signed requests.")

        timestamp = str(int(time.time() * 1000) + self._time_offset)
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        sign_str = f"{timestamp}{self._api_key}{self._recv_window}{param_str}"

        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-BAPI-API-KEY": self._api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self._recv_window,
        }

    def _sign_post(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Generate authentication headers for POST requests."""
        if not self._api_key or not self._api_secret:
            raise AdapterError("API key and secret required for signed requests.")

        import json
        timestamp = str(int(time.time() * 1000) + self._time_offset)
        param_str = json.dumps(params)
        sign_str = f"{timestamp}{self._api_key}{self._recv_window}{param_str}"

        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-BAPI-API-KEY": self._api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self._recv_window,
            "Content-Type": "application/json",
        }

    def _ensure_session(self) -> None:
        if not self._session:
            self._session = requests.Session()

    def __repr__(self) -> str:
        return (
            f"BybitAdapter(testnet={self._testnet}, "
            f"connected={self.connected})"
        )
