import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd
import json

if not mt5.initialize():
    print("Failed to initialize MT5")
    quit()

# Rango: Desde el inicio de la sesión de hoy (o últimas 12 horas para cubrir los $100 iniciales)
end_date = datetime.now()
start_date = end_date - timedelta(hours=12)

history_deals = mt5.history_deals_get(start_date, end_date)
if history_deals is None or len(history_deals) == 0:
    print("No hay trades en el historial reciente.")
else:
    df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    # Filtrar solo 'OUT' (cierres) que tengan beneficio (evitar depósitos/ajustes)
    df = df[(df['entry'] == 1) & (df['symbol'] != '')]
    
    # Cálculos Estadísticos
    total_trades = len(df)
    ganadores = df[df['profit'] > 0]
    perdedores = df[df['profit'] <= 0]
    
    winrate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
    total_profit = df['profit'].sum()
    max_ganada = df['profit'].max()
    max_perdida = df['profit'].min()
    pnl_promedio = df['profit'].mean()
    
    # Diferencia de montos (Profit acumulado vs Pérdida acumulada)
    gross_profit = ganadores['profit'].sum()
    gross_loss = abs(perdedores['profit'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    print(f"--- TITAN PERFORMANCE REPORT v29.0 ---")
    print(f"Total Trades: {total_trades}")
    print(f"Winrate: {winrate:.1f}%")
    print(f"Profit Neto: ${total_profit:.2f} USD")
    print(f"Max Ganada: ${max_ganada:.2f}")
    print(f"Max Perdida: ${max_perdida:.2f}")
    print(f"PnL Promedio: ${pnl_promedio:.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Monto Ganado Acum: ${gross_profit:.2f}")
    print(f"Monto Perdido Acum: ${gross_loss:.2f}")

mt5.shutdown()
