import os
import requests
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "^NSEI",
]

INTERVAL = "5m"
HMA_LENGTH = 200
LOOKBACK = 4

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    resp = requests.post(url, data=payload, timeout=15)
    if resp.status_code != 200:
        print(f"Telegram send failed: {resp.text}")


def wma(series, length):
    weights = pd.Series(range(1, length + 1))
    return series.rolling(length).apply(
        lambda x: (x * weights.values).sum() / weights.sum(), raw=True
    )


def hma(series, length):
    half_length = int(length / 2)
    sqrt_length = int(length ** 0.5)
    raw_hma = 2 * wma(series, half_length) - wma(series, length)
    return wma(raw_hma, sqrt_length)


def check_symbol(symbol):
    period_map = {"5m": "10d", "15m": "10d", "30m": "20d", "1h": "60d", "1d": "2y"}
    period = period_map.get(INTERVAL, "10d")

    data = yf.download(symbol, period=period, interval=INTERVAL, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if data.empty or len(data) < HMA_LENGTH + 10:
        print(f"{symbol}: not enough data, skipping")
        return

    data = data.iloc[:-1]
    close = data["Close"]
    hma_line = hma(close, HMA_LENGTH)

    alerts = []
    n = len(close)
    for i in range(n - LOOKBACK, n):
        prev_c, curr_c = close.iloc[i - 1], close.iloc[i]
        prev_h, curr_h = hma_line.iloc[i - 1], hma_line.iloc[i]
        if pd.isna(prev_h) or pd.isna(curr_h):
            continue
        when = close.index[i].strftime("%d-%b %H:%M")
        if prev_c <= prev_h and curr_c > curr_h:
            alerts.append(
                f"🟢 {symbol}\nPrice HMA({HMA_LENGTH}) ke UPAR close hua\n"
                f"Candle: {when}\nClose: {curr_c:.2f} | HMA: {curr_h:.2f}\n"
                f"Timeframe: {INTERVAL}"
            )
        elif prev_c >= prev_h and curr_c < curr_h:
            alerts.append(
                f"🔴 {symbol}\nPrice HMA({HMA_LENGTH}) ke NEECHE close hua\n"
                f"Candle: {when}\nClose: {curr_c:.2f} | HMA: {curr_h:.2f}\n"
                f"Timeframe: {INTERVAL}"
            )

    if not alerts:
        print(f"{symbol}: no crossover in last {LOOKBACK} candles "
              f"({close.iloc[-1]:.2f} vs HMA {hma_line.iloc[-1]:.2f})")
        return

    for msg in alerts:
        print(msg)
        send_telegram_message(msg)


def main():
    for symbol in SYMBOLS:
        try:
            check_symbol(symbol)
        except Exception as exc:
            print(f"{symbol}: error -> {exc}")


if __name__ == "__main__":
    main()
