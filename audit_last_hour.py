import MetaTrader5 as mt5
from datetime import datetime, timedelta
import json

if not mt5.initialize():
    print("Failed to initialize MT5")
    quit()

# Rango de tiempo: última hora
end_date = datetime.now()
start_date = end_date - timedelta(hours=1.5) # Un poco más por si acaso

history_deals = mt5.history_deals_get(start_date, end_date)
if history_deals is None:
    print(f"No deals found. Error: {mt5.last_error()}")
else:
    deals_list = []
    for d in history_deals:
        deals_list.append({
            "ticket": d.ticket,
            "order": d.order,
            "time": datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M:%S'),
            "symbol": d.symbol,
            "type": "BUY" if d.type == 0 else "SELL",
            "entry": "IN" if d.entry == 0 else "OUT",
            "volume": d.volume,
            "price": d.price,
            "profit": d.profit,
            "comment": d.comment
        })
    print(json.dumps(deals_list, indent=2))

mt5.shutdown()
