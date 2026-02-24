# PULSE-Bybit

**Bybit V5 adapter for PULSE Protocol — trade Bybit with semantic messages.**

Write your trading bot once, run it on any exchange. Same code works with Binance, Kraken, OKX — just change one line.

## Quick Start

```bash
pip install pulse-bybit
```

```python
from pulse import PulseMessage
from pulse_bybit import BybitAdapter

# Connect
adapter = BybitAdapter(api_key="your-key", api_secret="your-secret")
adapter.connect()

# Get BTC price
msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "BTCUSDT"})
response = adapter.send(msg)
print(response.content["parameters"]["result"])

# Place an order
order = PulseMessage(
    action="ACT.TRANSACT.REQUEST",
    parameters={"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001},
    validate=False,
)
result = adapter.send(order)
```

## Switch Exchanges in One Line

```python
# from pulse_binance import BinanceAdapter as Adapter
# from pulse_kraken import KrakenAdapter as Adapter
from pulse_bybit import BybitAdapter as Adapter

adapter = Adapter(api_key="...", api_secret="...")
```

Your bot code stays exactly the same. Only the import changes.

## Supported Actions

| PULSE Action | What It Does | Bybit Endpoint |
|---|---|---|
| `ACT.QUERY.DATA` | Price, klines, order book | `/v5/market/tickers`, `/v5/market/kline`, `/v5/market/orderbook` |
| `ACT.TRANSACT.REQUEST` | Place market/limit order | `/v5/order/create` |
| `ACT.CANCEL` | Cancel an order | `/v5/order/cancel` |
| `ACT.QUERY.STATUS` | Check order status | `/v5/order/realtime` |
| `ACT.QUERY.LIST` | List open orders | `/v5/order/realtime` |
| `ACT.QUERY.BALANCE` | Wallet balance | `/v5/account/wallet-balance` |

## Features

- **HMAC-SHA256 authentication** — fully handled for you
- **Server time sync** — automatic clock synchronization on connect
- **Testnet support** — `BybitAdapter(testnet=True)` for safe testing
- **Spot and derivatives** — pass `category="linear"` for futures
- **Tiny footprint** — one file, ~15 KB, no heavy dependencies

## Query Types

```python
# Price (default)
PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "BTCUSDT"})

# Klines/candlesticks
PulseMessage(action="ACT.QUERY.DATA", parameters={
    "symbol": "BTCUSDT", "type": "klines", "interval": "60"
})

# Order book depth
PulseMessage(action="ACT.QUERY.DATA", parameters={
    "symbol": "BTCUSDT", "type": "depth", "limit": 20
})
```

## Order Types

```python
# Market order
PulseMessage(action="ACT.TRANSACT.REQUEST", validate=False, parameters={
    "symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001
})

# Limit order
PulseMessage(action="ACT.TRANSACT.REQUEST", validate=False, parameters={
    "symbol": "ETHUSDT", "side": "SELL", "quantity": 1.0,
    "order_type": "LIMIT", "price": 2000
})
```

## Testing

```bash
pip install pytest
pytest tests/ -q  # 35 tests, all mocked (no real API calls)
```

## PULSE Ecosystem

| Package | Provider | Install |
|---|---|---|
| [pulse-protocol](https://pypi.org/project/pulse-protocol/) | Core | `pip install pulse-protocol` |
| [pulse-binance](https://pypi.org/project/pulse-binance/) | Binance | `pip install pulse-binance` |
| **pulse-bybit** | **Bybit** | `pip install pulse-bybit` |
| [pulse-kraken](https://pypi.org/project/pulse-kraken/) | Kraken | `pip install pulse-kraken` |
| [pulse-okx](https://pypi.org/project/pulse-okx/) | OKX | `pip install pulse-okx` |
| [pulse-openai](https://pypi.org/project/pulse-openai/) | OpenAI | `pip install pulse-openai` |
| [pulse-anthropic](https://pypi.org/project/pulse-anthropic/) | Anthropic | `pip install pulse-anthropic` |
| [pulse-gateway](https://pypi.org/project/pulse-gateway/) | Gateway | `pip install pulse-gateway` |

## License

Apache 2.0 — open source, free forever.
