# OhMyCrypto 🚀

**The Sonic Arbitrage Monitor for macOS**

Start your day with the sound of money (literally). OhMyCrypto connects to major exchanges, scans for price discrepancies, and **sings to you** when it finds an arbitrage opportunity.

> *"Why stare at charts when your Mac can scream at you?"*

## 🤔 What is this?
I built this because I was tired of missing arbitrage windows while doing my homework.

It's a Python-based, async-powered market scanner that:
1.  **Watches multiple exchanges** (Binance, OKX, etc.) simultaneously.
2.  **Calculates the spread** in real-time (factoring in fees, because fees hurt).
3.  **Uses macOS native Text-to-Speech** to vocally alert you when a profitable trade exists.

## ⚡ Features
* **Blazing Fast**: Uses `asyncio` and `ccxt.async_support` to poll multiple exchanges in parallel.
* **Smart Math**: Doesn't just look at price; checks the Order Book depth (Bid/Ask) to ensure the trade is real.
* **Sonic Alerts**:
    * *Small Profit*: Polite notification.
    * *Huge Profit*: Excited singing (yes, it actually sings).

## 🛠 Installation

You need Python 3.9+ and a Mac (for the voice features).

1.  **Clone the repo**
    ```bash
    git clone [https://github.com/JeremyL691/OhMyCrypto.git](https://github.com/JeremyL691/OhMyCrypto.git)
    cd OhMyCrypto
    ```

2.  **Set up the environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Run it**
    ```bash
    cd src
    python main.py
    ```

## 🎮 Usage

By default, it watches **BTC/USDT** on Binance and OKX. Want to watch something else?

```bash
# Watch Ethereum with a $2000 trade simulation
python main.py --symbol ETH/USDT --trade-size 2000