"""
PULSE-Bybit Adapter.

Bridge PULSE Protocol messages to Bybit V5 API.
Same interface as pulse-binance — swap exchanges in one line.

Example:
    >>> from pulse_bybit import BybitAdapter
    >>> adapter = BybitAdapter(api_key="...", api_secret="...")
    >>> from pulse import PulseMessage
    >>> msg = PulseMessage(
    ...     action="ACT.QUERY.DATA",
    ...     parameters={"symbol": "BTCUSDT"}
    ... )
    >>> response = adapter.send(msg)
    >>> print(response.content["parameters"]["result"]["price"])
"""

from pulse_bybit.adapter import BybitAdapter
from pulse_bybit.version import __version__

__all__ = ["BybitAdapter", "__version__"]
