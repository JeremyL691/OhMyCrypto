import pandas as pd

def build_spread_table(prices, fee_rate):
    rows = []
    names = list(prices.keys())
    for buy in names:
        for sell in names:
            if buy == sell:
                continue
            buy_price = prices[buy]["ask"]
            sell_price = prices[sell]["bid"]
            if buy_price is None or sell_price is None:
                continue
            spread = (sell_price - buy_price) / buy_price
            net = spread - 2 * fee_rate
            rows.append({
                "buy_exchange": buy,
                "sell_exchange": sell,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "spread": spread,
                "net_spread": net,
            })
    return pd.DataFrame(rows)

def find_best_opportunity(prices, min_spread, fee_rate):
    df = build_spread_table(prices, fee_rate)
    if df.empty:
        return None
    best = df.sort_values("net_spread", ascending=False).iloc[0]
    if best["net_spread"] >= min_spread:
        return best
    return None

def simulate_profit(trade_size, net_spread):
    return trade_size * float(net_spread)