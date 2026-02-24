import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

if not mt5.initialize():
    print("Error MT5")
    quit()

# Rango: Últimos 30 minutos
end_time = datetime.now()
start_time = end_time - timedelta(minutes=30)

print(f"--- 🚨 AUDITORÍA MODO METRALLETA v28.0 (30 MIN) ---")
print(f"Desde: {start_time.strftime('%H:%M:%S')} hasta {end_time.strftime('%H:%M:%S')}\n")

deals = mt5.history_deals_get(start_time, end_time)

if deals is None or len(deals) == 0:
    print("Esperando acción del mercado...")
else:
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df = df[df['entry'].isin([mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT])]
    
    summary = []
    for symbol in df['symbol'].unique():
        sym_df = df[df['symbol'] == symbol]
        out_deals = sym_df[sym_df['entry'] == mt5.DEAL_ENTRY_OUT]
        
        total_pnl = out_deals['profit'].sum() + out_deals['commission'].sum() + out_deals['swap'].sum()
        trades = len(out_deals)
        wins = len(out_deals[out_deals['profit'] > 0])
        losses = len(out_deals[out_deals['profit'] <= 0])
        
        # Métrica Metralleta: Trades por Minuto (TPM)
        tpm = trades / 30
        
        # Métrica de Riesgo: Pérdida Máxima vs Ganancia Media
        avg_win = out_deals[out_deals['profit'] > 0]['profit'].mean() if wins > 0 else 0
        max_loss = out_deals[out_deals['profit'] <= 0]['profit'].min() if losses > 0 else 0
        
        summary.append({
            "Sym": symbol,
            "Trades": trades,
            "TPM": f"{tpm:.2f}",
            "PnL": f"${total_pnl:.2f}",
            "W/L": f"{wins}/{losses}",
            "AvgWin": f"${avg_win:.2f}",
            "MaxLoss": f"${max_loss:.2f}",
            "Eff": f"{(wins/trades*100):.1f}%" if trades > 0 else "0%"
        })

    print(f"{'SYM':<8} | {'TPM':<5} | {'PnL':<10} | {'W/L':<6} | {'EFF':<6} | {'MAX-L':<8} | {'AVG-W'}")
    print("-" * 75)
    for s in summary:
        print(f"{s['Sym']:<8} | {s['TPM']:<5} | {s['PnL']:<10} | {s['W/L']:<6} | {s['Eff']:<6} | {s['MaxLoss']:<8} | {s['AvgWin']}")

mt5.shutdown()
