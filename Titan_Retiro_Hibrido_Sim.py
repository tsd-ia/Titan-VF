import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR ENJAMBRE RESCATE v39.7 (REGLA DE LOS $100) ---
SYMBOL = "XAUUSDm"
MONDAY_START_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    print("🛰️ Cargando Big Data: Simulando ENJAMBRE DE RESCATE (RETIRO SEMANAL)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) # El Protector
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = MONDAY_START_BALANCE
    pos_list = []
    total_withdrawn = 0
    weekly_withdrawals = []
    current_date = None

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        # 1. Gestion de Retiro / Re-inicio Lunes
        if current_date != row['date']:
            if current_date is not None and current_date.weekday() == 4: # Viernes
                withdrawal = max(0, balance - MONDAY_START_BALANCE)
                total_withdrawn += withdrawal
                weekly_withdrawals.append(withdrawal)
                balance = MONDAY_START_BALANCE # Reset Lunes
                pos_list = []
            current_date = row['date']

        if balance <= 0:
            balance = 0 # Esperar al proximo ciclo de $200 (simulando inyeccion de lunes)
            continue

        if not (7 <= now.hour <= 23): continue

        # --- REGLA TACTICA v39.7 ---
        # Si el balance es menor a $100, el bot se vuelve SUPER-PROTECTOR
        # Si el balance es mayor a $200, se activa el GATILLO HIBRIDO
        if balance < 100:
            limit = 6
            rsi_buy, rsi_sell = 30, 70 # Gatillo conservador
            m5_shield = True
        else:
            limit = 50
            rsi_buy, rsi_sell = 40, 60 # Gatillo Comandante (Hibrido)
            m5_shield = True

        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']

        # Cierres
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= 1.2 or pnl <= -25.0:
                balance += pnl
                pos_list.remove(p)

        # Entradas
        if len(pos_list) < limit:
            too_close = any(abs(price - p['entry']) < 0.15 for p in pos_list)
            if not too_close:
                # El Escudo M5 siempre manda
                if rsi < rsi_buy and price > ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"BUY", "entry":price})
                elif rsi > rsi_sell and price < ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"SELL", "entry":price})

    with open("REPORTE_RETIROS_v39_7.txt", "w") as f:
        f.write("TITAN v39.7: ESTRATEGIA DE RETIRO CON GATILLO HIBRIDO\n")
        f.write("="*60 + "\n")
        f.write(f"Total Retirado (60 dias): ${total_withdrawn:.2f}\n")
        f.write(f"Sueldo Promedio Semanal: ${total_withdrawn/8:.2f}\n\n")
        for i, w in enumerate(weekly_withdrawals):
            f.write(f"SEM {i+1} | Retiro: ${w:>10.2f}\n")

run_simulation()
