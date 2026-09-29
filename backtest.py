import os
import requests
import pandas as pd
import yfinance as yf

SYMBOL = "^NSEI"
INTERVAL = "5m"
PERIOD = "60d"
HMA_LENGTH = 200

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


def run_backtest():
    data = yf.download(SYMBOL, period=PERIOD, interval=INTERVAL, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.dropna()

    close = data["Close"]
    hma_line = hma(close, HMA_LENGTH)

    df = pd.DataFrame({"close": close, "hma": hma_line}).dropna()
    df["position"] = 0
    df.loc[df["close"] > df["hma"], "position"] = 1
    df.loc[df["close"] < df["hma"], "position"] = -1
    df["signal_change"] = df["position"].diff().fillna(0) != 0

    trades = []
    entry_price = None
    entry_side = None
    entry_time = None

    for time, row in df.iterrows():
        if row["signal_change"] and entry_price is not None:
            exit_price = row["close"]
            pct = (exit_price - entry_price) / entry_price * 100
            if entry_side == -1:
                pct = -pct
            trades.append({"pct": pct})
        if row["signal_change"]:
            entry_price = row["close"]
            entry_side = row["position"]
            entry_time = time

    if not trades:
        send_telegram_message(f"📊 Backtest {SYMBOL} HMA({HMA_LENGTH}) {INTERVAL}\nCoi trade nahi mila is period mein.")
        return

    trades_df = pd.DataFrame(trades)
    total_trades = len(trades_df)
    wins = (trades_df["pct"] > 0).sum()
    losses = (trades_df["pct"] <= 0).sum()
    win_rate = wins / total_trades * 100
    avg_win = trades_df.loc[trades_df["pct"] > 0, "pct"].mean() if wins else 0
    avg_loss = trades_df.loc[trades_df["pct"] <= 0, "pct"].mean() if losses else 0
    total_return = trades_df["pct"].sum()
    best_trade = trades_df["pct"].max()
    worst_trade = trades_df["pct"].min()

    start_date = df.index[0].strftime("%d-%b")
    end_date = df.index[-1].strftime("%d-%b")

    msg = (
        f"📊 Backtest Result\n"
        f"{SYMBOL} | HMA({HMA_LENGTH}) | {INTERVAL} candle\n"
        f"Period: {start_date} se {end_date} ({total_trades} trades)\n\n"
        f"Win rate: {win_rate:.1f}% ({wins} win / {losses} loss)\n"
        f"Avg win: {avg_win:.2f}% | Avg loss: {avg_loss:.2f}%\n"
        f"Best trade: {best_trade:.2f}% | Worst: {worst_trade:.2f}%\n"
        f"Total return (sum of %): {total_return:.2f}%\n\n"
        f"⚠️ Ye sirf simulation hai, brokerage/slippage/tax shamil nahi hai."
    )
    print(msg)
    send_telegram_message(msg)


if __name__ == "__main__":
    run_backtest()
