"""Tests for Bybit adapter. All mocked — no real API calls."""

import pytest
from unittest.mock import MagicMock, patch

from pulse.message import PulseMessage
from pulse.adapter import AdapterError, AdapterConnectionError

from pulse_bybit import BybitAdapter


# --- Mock Helpers ---


def mock_response(result_data, ret_code=0, ret_msg="OK"):
    """Create a mock Bybit V5 response."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "retCode": ret_code,
        "retMsg": ret_msg,
        "result": result_data,
    }
    mock.raise_for_status.return_value = None
    return mock


# --- Fixtures ---


@pytest.fixture
def adapter():
    a = BybitAdapter(api_key="test-key", api_secret="test-secret")
    a._session = MagicMock()
    a.connected = True
    return a


@pytest.fixture
def price_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTCUSDT"},
        sender="test-bot",
    )


@pytest.fixture
def klines_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTCUSDT", "type": "klines", "interval": "60"},
        sender="test-bot",
    )


@pytest.fixture
def buy_message():
    return PulseMessage(
        action="ACT.TRANSACT.REQUEST",
        parameters={"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def cancel_message():
    return PulseMessage(
        action="ACT.CANCEL",
        parameters={"symbol": "BTCUSDT", "order_id": "abc123"},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def status_message():
    return PulseMessage(
        action="ACT.QUERY.STATUS",
        parameters={"symbol": "BTCUSDT", "order_id": "abc123"},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def balance_message():
    return PulseMessage(
        action="ACT.QUERY.BALANCE",
        parameters={},
        sender="test-bot",
        validate=False,
    )


# --- Test Initialization ---


class TestBybitAdapterInit:

    def test_basic_init(self):
        adapter = BybitAdapter(api_key="key", api_secret="secret")
        assert adapter.name == "bybit"
        assert adapter.base_url == "https://api.bybit.com"
        assert adapter.connected is False

    def test_testnet_init(self):
        adapter = BybitAdapter(testnet=True)
        assert adapter.base_url == "https://api-testnet.bybit.com"

    def test_repr(self):
        adapter = BybitAdapter()
        assert "testnet=False" in repr(adapter)


# --- Test to_native: Market Data ---


class TestToNativeMarketData:

    def test_price_query(self, adapter, price_message):
        native = adapter.to_native(price_message)
        assert native["method"] == "GET"
        assert native["endpoint"] == "/v5/market/tickers"
        assert native["params"]["symbol"] == "BTCUSDT"
        assert native["params"]["category"] == "spot"
        assert native["signed"] is False

    def test_klines_query(self, adapter, klines_message):
        native = adapter.to_native(klines_message)
        assert native["endpoint"] == "/v5/market/kline"
        assert native["params"]["interval"] == "60"

    def test_depth_query(self, adapter):
        msg = PulseMessage(
            action="ACT.QUERY.DATA",
            parameters={"symbol": "BTCUSDT", "type": "depth"},
        )
        native = adapter.to_native(msg)
        assert native["endpoint"] == "/v5/market/orderbook"

    def test_symbol_uppercased(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "btcusdt"})
        native = adapter.to_native(msg)
        assert native["params"]["symbol"] == "BTCUSDT"

    def test_unknown_query_type_raises(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"type": "invalid"})
        with pytest.raises(AdapterError, match="Unknown query type"):
            adapter.to_native(msg)

    def test_klines_no_symbol_raises(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"type": "klines"})
        with pytest.raises(AdapterError, match="Symbol required"):
            adapter.to_native(msg)

    def test_custom_category(self, adapter):
        msg = PulseMessage(
            action="ACT.QUERY.DATA",
            parameters={"symbol": "BTCUSDT", "category": "linear"},
        )
        native = adapter.to_native(msg)
        assert native["params"]["category"] == "linear"


# --- Test to_native: Orders ---


class TestToNativeOrders:

    def test_market_buy(self, adapter, buy_message):
        native = adapter.to_native(buy_message)
        assert native["method"] == "POST"
        assert native["endpoint"] == "/v5/order/create"
        assert native["params"]["symbol"] == "BTCUSDT"
        assert native["params"]["side"] == "Buy"
        assert native["params"]["orderType"] == "Market"
        assert native["params"]["qty"] == "0.001"
        assert native["signed"] is True

    def test_sell_side(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTCUSDT", "side": "SELL", "quantity": 0.1},
            validate=False,
        )
        native = adapter.to_native(msg)
        assert native["params"]["side"] == "Sell"

    def test_limit_order(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            validate=False,
            parameters={
                "symbol": "ETHUSDT", "side": "BUY", "quantity": 1,
                "order_type": "LIMIT", "price": 2000,
            },
        )
        native = adapter.to_native(msg)
        assert native["params"]["orderType"] == "Limit"
        assert native["params"]["price"] == "2000"
        assert native["params"]["timeInForce"] == "GTC"

    def test_limit_no_price_raises(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTCUSDT", "side": "BUY", "quantity": 1, "order_type": "LIMIT"},
            validate=False,
        )
        with pytest.raises(AdapterError, match="Price required"):
            adapter.to_native(msg)

    def test_order_missing_field_raises(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTCUSDT", "side": "BUY"},
            validate=False,
        )
        with pytest.raises(AdapterError, match="Missing required field"):
            adapter.to_native(msg)

    def test_cancel_order(self, adapter, cancel_message):
        native = adapter.to_native(cancel_message)
        assert native["method"] == "POST"
        assert native["endpoint"] == "/v5/order/cancel"
        assert native["params"]["orderId"] == "abc123"
        assert native["signed"] is True

    def test_cancel_no_symbol_raises(self, adapter):
        msg = PulseMessage(action="ACT.CANCEL", parameters={"order_id": "123"}, validate=False)
        with pytest.raises(AdapterError, match="Symbol required"):
            adapter.to_native(msg)


# --- Test to_native: Account ---


class TestToNativeAccount:

    def test_order_status(self, adapter, status_message):
        native = adapter.to_native(status_message)
        assert native["endpoint"] == "/v5/order/realtime"
        assert native["params"]["orderId"] == "abc123"
        assert native["signed"] is True

    def test_open_orders(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.LIST", parameters={}, validate=False)
        native = adapter.to_native(msg)
        assert native["endpoint"] == "/v5/order/realtime"
        assert native["signed"] is True

    def test_wallet_balance(self, adapter, balance_message):
        native = adapter.to_native(balance_message)
        assert native["endpoint"] == "/v5/account/wallet-balance"
        assert native["signed"] is True

    def test_unsupported_action_raises(self, adapter):
        msg = PulseMessage(action="ACT.CREATE.TEXT", parameters={}, validate=False)
        with pytest.raises(AdapterError, match="Unsupported action"):
            adapter.to_native(msg)


# --- Test call_api ---


class TestCallAPI:

    def test_get_request(self, adapter):
        adapter._session.get.return_value = mock_response(
            {"list": [{"symbol": "BTCUSDT", "lastPrice": "65000"}]}
        )
        result = adapter.call_api({
            "method": "GET",
            "endpoint": "/v5/market/tickers",
            "params": {"category": "spot", "symbol": "BTCUSDT"},
            "signed": False,
        })
        assert result["list"][0]["lastPrice"] == "65000"

    def test_post_request(self, adapter):
        adapter._session.post.return_value = mock_response(
            {"orderId": "abc123", "orderLinkId": ""}
        )
        result = adapter.call_api({
            "method": "POST",
            "endpoint": "/v5/order/create",
            "params": {"symbol": "BTCUSDT", "side": "Buy", "qty": "0.001"},
            "signed": True,
        })
        assert result["orderId"] == "abc123"

    def test_api_error_response(self, adapter):
        adapter._session.get.return_value = mock_response(
            {}, ret_code=10001, ret_msg="Invalid symbol"
        )
        with pytest.raises(AdapterError, match="Invalid symbol"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/v5/market/tickers",
                "params": {"symbol": "INVALID"},
                "signed": False,
            })

    def test_connection_error(self, adapter):
        adapter._session.get.side_effect = ConnectionError("Network down")
        with pytest.raises(AdapterConnectionError, match="Cannot reach"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/v5/market/tickers",
                "signed": False,
            })


# --- Test Full Pipeline ---


class TestFullPipeline:

    def test_price_query(self, adapter, price_message):
        adapter._session.get.return_value = mock_response(
            {"list": [{"symbol": "BTCUSDT", "lastPrice": "65000.50"}]}
        )
        response = adapter.send(price_message)
        assert response.type == "RESPONSE"
        assert response.envelope["sender"] == "adapter:bybit"
        assert response.content["parameters"]["result"]["list"][0]["lastPrice"] == "65000.50"

    def test_order_pipeline(self, adapter, buy_message):
        adapter._session.post.return_value = mock_response(
            {"orderId": "order-123", "orderLinkId": ""}
        )
        response = adapter.send(buy_message)
        assert response.content["parameters"]["result"]["orderId"] == "order-123"

    def test_pipeline_tracks_requests(self, adapter, price_message):
        adapter._session.get.return_value = mock_response({"list": []})
        adapter.send(price_message)
        adapter.send(price_message)
        assert adapter._request_count == 2


# --- Test Signing ---


class TestSigning:

    def test_sign_get_headers(self, adapter):
        params = {"category": "spot", "symbol": "BTCUSDT"}
        headers = adapter._sign_get(params)
        assert "X-BAPI-API-KEY" in headers
        assert "X-BAPI-SIGN" in headers
        assert "X-BAPI-TIMESTAMP" in headers
        assert headers["X-BAPI-API-KEY"] == "test-key"
        assert len(headers["X-BAPI-SIGN"]) == 64

    def test_sign_post_headers(self, adapter):
        params = {"symbol": "BTCUSDT", "side": "Buy"}
        headers = adapter._sign_post(params)
        assert "X-BAPI-SIGN" in headers
        assert "Content-Type" in headers

    def test_sign_without_key_raises(self, adapter):
        adapter._api_key = None
        with pytest.raises(AdapterError, match="API key and secret required"):
            adapter._sign_get({"test": "param"})


# --- Test Supported Actions ---


class TestSupportedActions:

    def test_supported_actions(self, adapter):
        actions = adapter.supported_actions
        assert "ACT.QUERY.DATA" in actions
        assert "ACT.TRANSACT.REQUEST" in actions
        assert "ACT.CANCEL" in actions
        assert len(actions) == 6

    def test_supports_check(self, adapter):
        assert adapter.supports("ACT.QUERY.DATA") is True
        assert adapter.supports("ACT.CREATE.TEXT") is False


# --- Test Exchange Switching ---


class TestExchangeSwitching:
    """Prove exchange switching works."""

    def test_same_actions_as_binance(self):
        from pulse_binance import BinanceAdapter
        binance = BinanceAdapter(api_key="k", api_secret="s")
        bybit = BybitAdapter(api_key="k", api_secret="s")
        assert set(binance.supported_actions) == set(bybit.supported_actions)

    def test_same_message_works(self, adapter, price_message):
        adapter._session.get.return_value = mock_response({"list": []})
        response = adapter.send(price_message)
        assert response.type == "RESPONSE"
