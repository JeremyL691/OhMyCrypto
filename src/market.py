import asyncio
import time

try:
    import ccxt.async_support as ccxt
    CCXT_AVAILABLE = True
except ModuleNotFoundError:
    ccxt = None
    CCXT_AVAILABLE = False


FALLBACK_EXCHANGES = {
    "binance",
    "bitfinex",
    "bitget",
    "bitstamp",
    "bybit",
    "coinbase",
    "gate",
    "kraken",
    "kucoin",
    "okx",
}


def build_exchange(name, timeout_ms):
    if not CCXT_AVAILABLE:
        raise RuntimeError("ccxt is required to build exchange clients")
    exchange_class = getattr(ccxt, name)
    return exchange_class({
        "enableRateLimit": True,
        "timeout": timeout_ms,
    })


def validate_exchange_names(names):
    invalid = []
    for name in names:
        if CCXT_AVAILABLE:
            is_valid = hasattr(ccxt, name)
        else:
            is_valid = name in FALLBACK_EXCHANGES
        if not is_valid:
            invalid.append(name)
    return invalid


def build_exchanges(names, timeout_ms):
    invalid = validate_exchange_names(names)
    if invalid:
        raise ValueError(f"Unsupported exchanges: {', '.join(sorted(invalid))}")
    return {name: build_exchange(name, timeout_ms) for name in names}


def initialize_exchange_health(names):
    return {
        name: {
            "consecutive_errors": 0,
            "last_success_at": None,
            "last_error_at": None,
            "last_error": None,
            "last_latency_ms": None,
            "degraded": False,
        }
        for name in names
    }


async def fetch_single(name, exchange, symbol):
    started = time.monotonic()
    try:
        ticker = await exchange.fetch_ticker(symbol)
        latency_ms = round((time.monotonic() - started) * 1000, 2)
        fetched_at_ms = int(time.time() * 1000)
        return {
            "name": name,
            "price": {
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "last": ticker.get("last"),
                "timestamp": ticker.get("timestamp"),
                "fetched_at_ms": fetched_at_ms,
            },
            "error": None,
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - started) * 1000, 2)
        return {
            "name": name,
            "price": None,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": latency_ms,
        }


async def fetch_prices(exchanges, symbol):
    tasks = [fetch_single(name, ex, symbol) for name, ex in exchanges.items()]
    results = await asyncio.gather(*tasks)
    prices = {}
    for result in results:
        if result["price"]:
            prices[result["name"]] = result["price"]
    return prices, results


async def fetch_orderbooks_for_candidate(clients, symbol, candidate, limit):
    buy_name = candidate["buy_exchange"]
    sell_name = candidate["sell_exchange"]

    async def fetch_book(name):
        try:
            exchange = clients[name]
            book = await exchange.fetch_order_book(symbol, limit=limit)
            return name, book, None
        except Exception as exc:
            return name, None, f"{type(exc).__name__}: {exc}"

    buy_task = fetch_book(buy_name)
    sell_task = fetch_book(sell_name)
    results = await asyncio.gather(buy_task, sell_task)

    books = {}
    errors = {}
    for name, book, error in results:
        if error is not None:
            errors[name] = error
        else:
            books[name] = book

    return books, errors


def update_exchange_health(health, fetch_results, max_consecutive_errors, now=None):
    now = now or time.time()
    for result in fetch_results:
        name = result["name"]
        state = health[name]
        state["last_latency_ms"] = result["latency_ms"]
        if result["error"] is None:
            state["consecutive_errors"] = 0
            state["last_success_at"] = now
            state["degraded"] = False
            state["last_error"] = None
        else:
            state["consecutive_errors"] += 1
            state["last_error_at"] = now
            state["last_error"] = result["error"]
            state["degraded"] = state["consecutive_errors"] >= max_consecutive_errors
    return health

async def close_exchanges(exchanges):
    tasks = [ex.close() for ex in exchanges.values()]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
