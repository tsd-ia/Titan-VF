import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- COMPARATIVA MAESTRA: RETIROS SEMANALES (CAZADOR vs PROTECTOR) ---
SYMBOL = "XAUUSDm"
MONDAY_START_BALANCE = 200.0

def simulate_bot(bot_type, data):
    balance = MONDAY_START_BALANCE
    pos_list = []
    weekly_withdrawals = []
    total_withdrawn = 0
    current_date = None
    cb_until = None
    session_pnl = 0.0

    for i in range(50, len(data)):
        row = data.iloc[i]
        now = row['time']
        
        # 1. Cambio de Día / Retiro Viernes
        if current_date != row['date']:
            if current_date is not None and current_date.weekday() == 4: # Viernes
                withdrawal = max(0, balance - MONDAY_START_BALANCE)
                total_withdrawn += withdrawal
                weekly_withdrawals.append(withdrawal)
                balance = MONDAY_START_BALANCE
                pos_list = []
            
            current_date = row['date']
            session_pnl = 0.0
            cb_until = None

        if balance <= 0: 
            balance = 0
            continue # Simular que espera al Lunes

        if not (7 <= now.hour <= 23): continue

        # 2. Configuración por Bot
        if bot_type == "CAZADOR":
            limit = 10
            tp_meta = 1.0
            protector_active = False
            cb_active = False
        else: # PROTECTOR
            protector_active = True
            cb_active = True
            limit = 3 if balance < 300 else 6
            tp_meta = 1.2 if balance < 300 else 2.5

        if cb_active and cb_until and now < cb_until: continue

        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50'] # Proxy M5
        m_speed = row['vol_pts']

        # 3. Gestión de Cierres
        for p in pos_list[:]:
            pnl = (price-p['entry']) if p['type']=='BUY' else (p['entry']-price)
            if pnl >= tp_meta or pnl <= -25.0:
                balance += pnl
                session_pnl += pnl
                pos_list.remove(p)
                if cb_active and session_pnl <= -40.0:
                    cb_until = now + timedelta(minutes=15)

        # 4. Entradas
        if len(pos_list) < limit and (not cb_active or not cb_until):
            if protector_active:
                if m_speed > 60: continue
                # Filtro Anti-Cuchillo
                if rsi < 35 and price > ema50: pos_list.append({"type":"BUY", "entry":price})
                elif rsi > 65 and price < ema50: pos_list.append({"type":"SELL", "entry":price})
            else: # Cazador puro
                if rsi < 35: pos_list.append({"type":"BUY", "entry":price})
                elif rsi > 65: pos_list.append({"type":"SELL", "entry":price})
                
    return weekly_withdrawals, total_withdrawn

def run_comparison():
    if not mt5.initialize(): return
    print("🛰️ Cargando Big Data y simulando ambos bots con retiros...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10

    w_a, total_a = simulate_bot("CAZADOR", df)
    w_b, total_b = simulate_bot("PROTECTOR", df)

    with open("COMPARATIVA_RETIROS_TITAN.txt", "w") as f:
        f.write("CUADRO COMPARATIVO DE RETIROS (60 DIAS)\n")
        f.write("="*70 + "\n")
        f.write("SEMANA | RETIRO CAZADOR (v39.2) | RETIRO PROTECTOR (v39.3)\n")
        f.write("-" * 70 + "\n")
        
        num_weeks = max(len(w_a), len(w_b))
        for i in range(num_weeks):
            val_a = w_a[i] if i < len(w_a) else 0.0
            val_b = w_b[i] if i < len(w_b) else 0.0
            f.write(f" SEM {i+1} | ${val_a:>20.2f} | ${val_b:>21.2f}\n")
            
        f.write("-" * 70 + "\n")
        f.write(f" TOTAL | ${total_a:>20.2f} | ${total_b:>21.2f}\n")
        f.write("="*70 + "\n")
        f.write(f"DIFERENCIA A FAVOR DEL PROTECTOR: ${total_b - total_a:.2f} USD\n")

run_comparison()
