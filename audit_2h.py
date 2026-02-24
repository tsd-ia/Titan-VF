import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import pytz

if not mt5.initialize():
    print("Error MT5")
    quit()

# 2 horas atrás desde ahora (Hora local)
end_time = datetime.now()
start_time = end_time - timedelta(hours=2)

print(f"--- Auditoria de Trading (Últimas 2 Horas) ---")
print(f"Rango: {start_time.strftime('%H:%M')} a {end_time.strftime('%H:%M')}\n")

# Obtener historial de "deals" (operaciones ejecutadas)
deals = mt5.history_deals_get(start_time, end_time)

if deals is None or len(deals) == 0:
    print("No se encontraron operaciones en las últimas 2 horas.")
else:
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    # Solo deals de entrada/salida de mercado (excluir depósitos/ajustes)
    df = df[df['entry'].isin([mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT])]
    
    # Agrupar por símbolo
    summary = []
    for symbol in df['symbol'].unique():
        sym_df = df[df['symbol'] == symbol]
        # Las ganancias reales están en los deals de salida (OUT)
        out_deals = sym_df[sym_df['entry'] == mt5.DEAL_ENTRY_OUT]
        total_pnl = out_deals['profit'].sum() + out_deals['commission'].sum() + out_deals['swap'].sum()
        count = len(out_deals)
        
        # Rendimiento
        wins = len(out_deals[out_deals['profit'] > 0])
        losses = len(out_deals[out_deals['profit'] <= 0])
        
        summary.append({
            "Instrumento": symbol,
            "Trades": count,
            "Profit Total": f"${total_pnl:.2f}",
            "Wins": wins,
            "Losses": losses,
            "Efectividad": f"{(wins/count*100):.1f}%" if count > 0 else "0%"
        })

    # Imprimir Cuadro Comparativo
    print(f"{'INSTRUMENTO':<12} | {'TRADES':<6} | {'PROFIT':<10} | {'W/L':<6} | {'EFICACIA'}")
    print("-" * 60)
    for s in summary:
        wl = f"{s['Wins']}/{s['Losses']}"
        print(f"{s['Instrumento']:<12} | {s['Trades']:<6} | {s['Profit Total']:<10} | {wl:<6} | {s['Efectividad']}")

mt5.shutdown()
