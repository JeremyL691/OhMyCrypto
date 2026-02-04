import argparse
import asyncio
import pandas as pd
from config import (
    PROJECT_NAME,
    DEFAULT_SYMBOL,
    DEFAULT_EXCHANGES,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MIN_SPREAD,
    DEFAULT_TRADE_SIZE,
    DEFAULT_FEE_RATE,
    DEFAULT_TIMEOUT,
)
from market import build_exchanges, fetch_prices, close_exchanges
from strategy import build_spread_table, find_best_opportunity, simulate_profit
import notifier  # <--- NEW IMPORT

def parse_args():
    parser = argparse.ArgumentParser(prog=PROJECT_NAME)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--exchanges", default=",".join(DEFAULT_EXCHANGES))
    parser.add_argument("--interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--min-spread", type=float, default=DEFAULT_MIN_SPREAD)
    parser.add_argument("--trade-size", type=float, default=DEFAULT_TRADE_SIZE)
    parser.add_argument("--fee-rate", type=float, default=DEFAULT_FEE_RATE)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--top", type=int, default=5)
    return parser.parse_args()

def format_prices(prices):
    rows = []
    for name, p in prices.items():
        rows.append({
            "exchange": name,
            "bid": p.get("bid"),
            "ask": p.get("ask"),
            "last": p.get("last"),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return "No prices"
    return df.to_string(index=False)

def format_spreads(df, top):
    if df.empty:
        return "No spreads"
    view = df.sort_values("net_spread", ascending=False).head(top)
    return view.to_string(index=False)

async def main_loop():
    args = parse_args()
    exchanges_list = [e.strip() for e in args.exchanges.split(",") if e.strip()]
    
    print(PROJECT_NAME + " with Voice Alert")
    print("Symbol:", args.symbol)
    
    clients = build_exchanges(exchanges_list, args.timeout)
    
    try:
        while True:
            prices = await fetch_prices(clients, args.symbol)
            
            if not prices:
                await asyncio.sleep(args.interval)
                continue

            spreads = build_spread_table(prices, args.fee_rate)
            best = find_best_opportunity(prices, args.min_spread, args.fee_rate)

            print("\nPrices")
            print(format_prices(prices))
            
            if best is not None:
                profit = simulate_profit(args.trade_size, best["net_spread"])
                
                # --- NEW FEATURE START ---
                # Check if profit is worth speaking (e.g. > $1)
                # You can adjust this threshold logic in notifier.py
                print(f"\n>>> ALERT: ${profit:.2f} PROFIT <<<")
                
                # Run voice alert in background (non-blocking)
                # We use a simple synchronous call here for simplicity
                notifier.notify_opportunity(profit, best["net_spread"])
                # --- NEW FEATURE END ---
                
                payload = dict(best)
                payload["simulated_profit"] = round(profit, 4)
                print("\nOPPORTUNITY")
                for k, v in payload.items():
                    print(f"{k}: {v}")
            else:
                print("\nNo huge opportunity")

            await asyncio.sleep(args.interval)

    except KeyboardInterrupt:
        pass
    finally:
        await close_exchanges(clients)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass