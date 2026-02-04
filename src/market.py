import asyncio
import ccxt.async_support as ccxt

def build_exchange(name, timeout_ms):
    exchange_class = getattr(ccxt, name)
    return exchange_class({
        "enableRateLimit": True,
        "timeout": timeout_ms,
    })

def build_exchanges(names, timeout_ms):
    return {name: build_exchange(name, timeout_ms) for name in names}

async def fetch_single(name, exchange, symbol):
    try:
        ticker = await exchange.fetch_ticker(symbol)
        return name, {
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "last": ticker.get("last"),
            "timestamp": ticker.get("timestamp"),
        }
    except Exception:
        return name, None

async def fetch_prices(exchanges, symbol):
    tasks = [fetch_single(name, ex, symbol) for name, ex in exchanges.items()]
    results = await asyncio.gather(*tasks)
    prices = {}
    for name, data in results:
        if data:
            prices[name] = data
    return prices

async def close_exchanges(exchanges):
    for ex in exchanges.values():
        await ex.close()