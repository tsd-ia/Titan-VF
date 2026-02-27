import MetaTrader5 as mt5
from datetime import datetime, timedelta

if not mt5.initialize():
    print("Error MT5")
    quit()

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
deals = mt5.history_deals_get(today, datetime.now())

if deals:
    print(f"{'Time':<20} | {'Sym':<10} | {'Type':<5} | {'Profit':<8} | {'Comment'}")
    print("-" * 60)
    for d in deals:
        if d.entry == mt5.DEAL_ENTRY_OUT:
            t = datetime.fromtimestamp(d.time).strftime('%H:%M:%S')
            dtype = "BUY" if d.type == mt5.DEAL_TYPE_SELL else "SELL"
            print(f"{t:<20} | {d.symbol:<10} | {dtype:<5} | {d.profit:<8.2f} | {d.comment}")
else:
    print("No deals today")
mt5.shutdown()
