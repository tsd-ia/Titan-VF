import MetaTrader5 as mt5
from datetime import datetime, timedelta
import json

if not mt5.initialize():
    print("Failed")
    quit()

# Ver los últimos 20 cierres reales
end = datetime.now()
start = end - timedelta(hours=3)
deals = mt5.history_deals_get(start, end)

if deals:
    # Filtrar solo entradas 'OUT'
    out_deals = [d for d in deals if d.entry == 1 and d.symbol != ""]
    # Ordenar por tiempo descendente
    out_deals.sort(key=lambda x: x.time, reverse=True)
    
    report = []
    for d in out_deals[:20]:
        report.append({
            "ticket": d.ticket,
            "time": datetime.fromtimestamp(d.time).strftime('%H:%M:%S'),
            "symbol": d.symbol,
            "type": "BUY" if d.type == 0 else "SELL",
            "profit": round(d.profit, 2),
            "comment": d.comment
        })
    print(json.dumps(report, indent=2))

acc = mt5.account_info()
print(f"Current Balance: {acc.balance}")
print(f"Current Equity: {acc.equity}")
mt5.shutdown()
