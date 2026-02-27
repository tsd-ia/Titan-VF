import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR PROTOCOLO APOLLO (OBJETIVO: $500 SEMANALES) ---
# Sin emojis para evitar errores de consola
SYMBOL = "XAUUSDm"
MONDAY_START_BALANCE = 200.0

def run_apollo_sim():
    if not mt5.initialize(): return

    print("Cargando Big Data para el Protocolo APOLLO (Objetivo $500/Semana)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) 
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = MONDAY_START_BALANCE
    pos_list = []
    weekly_withdrawals = []
    total_withdrawn = 0
    current_date = None

    print("Simulando 60 dias (Protocolo de Ataque Apollo)...")

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        if current_date != row['date']:
            if current_date is not None and current_date.weekday() == 4: # Viernes
                withdrawal = max(0, balance - MONDAY_START_BALANCE)
                total_withdrawn += withdrawal
                weekly_withdrawals.append(withdrawal)
                balance = MONDAY_START_BALANCE
                pos_list = []
            
            current_date = row['date']

        if balance <= 0: 
            balance = 0
            continue 

        if not (7 <= now.hour <= 23): continue

        # ESCALADO TARTICO APOLLO
        # Multiplicamos el riesgo si el balance semanal sube
        lot = 0.01
        limit = 6
        if balance > 400: 
            lot = 0.05  # FUEGO PESADO
            limit = 12
        elif balance > 300:
            lot = 0.03
            limit = 10
        elif balance > 250:
            lot = 0.02
            limit = 8

        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']
        m_speed = row['vol_pts']

        # Cierres
        for p in pos_list[:]:
            pnl = ((price-p['entry']) if p['type']=='BUY' else (p['entry']-price)) * (p['lot'] / 0.01)
            
            # Profit Target Adaptativo
            tp_target = 1.5 * (p['lot']/0.01)
            if pnl >= tp_target or pnl <= -25.0:
                balance += pnl
                pos_list.remove(p)

        # Entradas con Protector M5
        if len(pos_list) < limit:
            if m_speed < 60:
                if rsi < 30 and price > ema50:
                    pos_list.append({"type":"BUY", "entry":price, "lot": lot})
                elif rsi > 70 and price < ema50:
                    pos_list.append({"type":"SELL", "entry":price, "lot": lot})
                
    with open("REPORTE_APOLLO_500.txt", "w") as f:
        f.write("TITAN PROTOCOLO APOLLO: OBJETIVO $500 SEMANALES\n")
        f.write("="*60 + "\n")
        f.write(f"Total Retirado (60 dias): ${total_withdrawn:.2f}\n")
        f.write(f"Sueldo Promedio Semanal: ${total_withdrawn/8:.2f}\n\n")
        for i, w in enumerate(weekly_withdrawals):
            status = "OK" if w >= 500 else "FALLO"
            f.write(f"SEM {i+1} | Retiro: ${w:>10.2f} | {status}\n")

if __name__ == "__main__":
    run_apollo_sim()
