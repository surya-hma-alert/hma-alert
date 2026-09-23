"""
HMA Crossover Alert Script
---------------------------
Ye script har symbol ke liye price ka HMA (Hull Moving Average) nikalta hai
aur check karta hai ki price ne HMA ko cross kiya hai ya nahi (upar ya neeche).
Agar crossover hua hai, to Telegram par turant message bhej deta hai.
"""

import os
import requests
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "RELIANCE.NS",
    "TCS.NS",
    "^NSEI",
    "^NSEBANK",
]

INTERVAL = "5m"
HMA_LENGTH = 100

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    resp = requests.post(url, data=payload, timeout=15)
    if resp.status_code != 200:
        print(f"Telegram send failed: {resp.text}")


def wma(series: pd.Series, length: int) -> pd.Series:
    weights = pd.Series(range(1, length + 1))
    return series.rolling(length).apply(
        lambda x: (x * weights.values).sum() / weights.sum(), raw=True
    )


def hma(series: pd.Series, length: int) -> pd.Series:
    half_length = int(length / 2)
    sqrt_length = int(length ** 0.5)
    wma_half = wma(series, half_length)
    wma_full = wma(series, length)
    raw_hma = 2 * wma_half - wma_full
    return wma(raw_hma, sqrt_length)


def check_symbol(symbol: str) -> None:
    period_map = {"15m": "10d", "30m": "20d", "1h": "60d", "1d": "2y"}
    period = period_map.get(INTERVAL, "10d")

    data = yf.download(symbol, period=period, interval=INTERVAL, progress=False)
    if data.empty or len(data) < HMA_LENGTH + 5:
        print(f"{symbol}: not enough data, skipping")
        return

    close = data["Close"]
    hma_line = hma(close, HMA_LENGTH)

    prev_close, curr_close = close.iloc[-2], close.iloc[-1]
    prev_hma, curr_hma = hma_line.iloc[-2], hma_line.iloc[-1]

    if pd.isna(prev_hma) or pd.isna(curr_hma):
        print(f"{symbol}: HMA not ready yet, skipping")
        return

    crossed_above = prev_close <= prev_hma and curr_close > curr_hma
    crossed_below = prev_close >= prev_hma and curr_close < curr_hma

    if crossed_above:
        msg = (
            f"🟢 {symbol}\n"
            f"Price HMA({HMA_LENGTH}) ke UPAR cross hua!\n"
            f"Close: {curr_close:.2f} | HMA: {curr_hma:.2f}\n"
            f"Timeframe: {INTERVAL}"
        )
        print(msg)
        send_telegram_message(msg)
    elif crossed_below:
        msg = (
            f"🔴 {symbol}\n"
            f"Price HMA({HMA_LENGTH}) ke NEECHE cross hua!\n"
            f"Close: {curr_close:.2f} | HMA: {curr_hma:.2f}\n"
            f"Timeframe: {INTERVAL}"
        )
        print(msg)
        send_telegram_message(msg)
    else:
        print(f"{symbol}: no crossover ({curr_close:.2f} vs HMA {curr_hma:.2f})")


def main() -> None:
    for symbol in SYMBOLS:
        try:
            check_symbol(symbol)
        except Exception as exc:
            print(f"{symbol}: error -> {exc}")


if __name__ == "__main__":
    main()
