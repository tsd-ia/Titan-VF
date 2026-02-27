import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR ENJAMBRE ELITE (0.01 SIEMPRE) ---
# Sin emojis para evitar errores de codificacion
SYMBOL = "XAUUSDm"
MONDAY_START_BALANCE = 200.0

def run_enjambre_sim():
    if not mt5.initialize(): return

    print("Cargando Big Data para ENJAMBRE (Lote 0.01 - Alta Frecuencia)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) # Protector M5
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = MONDAY_START_BALANCE
    pos_list = []
    weekly_withdrawals = []
    total_withdrawn = 0
    current_date = None

    print("Simulando ciclos de 2 meses...")

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        # 1. Retiro de Viernes
        if current_date != row['date']:
            if current_date is not None and current_date.weekday() == 4: # Si era viernes
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

        # --- REGLA DEL COMANDANTE: 0.01 SIEMPRE ---
        lot = 0.01
        limit = 20 # Iniciamos con enjambre de 20
        if balance > 400: limit = 40 # Mas balas si hay mas margen
        elif balance > 300: limit = 30

        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']
        m_speed = row['vol_pts']

        # Cierres
        for p in pos_list[:]:
            pnl = (price-p['entry']) if p['type']=='BUY' else (p['entry']-price)
            # TP de $1.0 (Scalping ultra-rapido)
            if pnl >= 1.0 or pnl <= -25.0:
                balance += pnl
                pos_list.remove(p)

        # Entradas con Proteccion M5
        if len(pos_list) < limit:
            if m_speed < 60:
                if rsi < 35 and price > ema50:
                    # Metemos ráfagas de 5 balas
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"BUY", "entry":price})
                elif rsi > 65 and price < ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"SELL", "entry":price})
                
    with open("REPORTE_ENJAMBRE_001.txt", "w") as f:
        f.write("TITAN PROTOCOLO ENJAMBRE: 0.01 SIEMPRE\n")
        f.write("="*60 + "\n")
        f.write(f"Total Retirado (60 dias): ${total_withdrawn:.2f}\n")
        f.write(f"Sueldo Promedio Semanal: ${total_withdrawn/8:.2f}\n\n")
        for i, w in enumerate(weekly_withdrawals):
            status = "OK" if w >= 500 else "FAIL"
            f.write(f"SEM {i+1} | Retiro: ${w:>10.2f} | {status}\n")

if __name__ == "__main__":
    run_enjambre_sim()
