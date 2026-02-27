import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- COMPARADOR MAESTRO TITAN v39.3 (MODO INDESTRUCTIBLE) ---
SYMBOL = "XAUUSDm"

def simulate_bot(bot_type, data):
    balance = 200.0
    pos_list = []
    history = []
    daily_stats = {}
    circuit_breaker_until = None
    session_pnl = 0.0
    current_date = None

    for i in range(50, len(data)):
        row = data.iloc[i]
        now = row['time']
        
        if current_date != row['date']:
            if current_date is not None:
                daily_stats[current_date] = balance
            current_date = row['date']
            session_pnl = 0.0
            circuit_breaker_until = None
        
        if balance <= 0:
            balance = 0
            continue # Cuenta quemada para este bot
            
        if not (7 <= now.hour <= 23): continue
        if circuit_breaker_until and now < circuit_breaker_until: continue

        price = row['close']
        rsi = row['rsi']
        ema20 = row['ema20']
        ema50 = row['ema50']
        m_speed = row['vol_pts']

        # Cierres
        for p in pos_list[:]:
            pnl = (price-p['entry']) if p['type']=='BUY' else (p['entry']-price)
            tp = 1.0 if bot_type == "CAZADOR" else 1.5
            if pnl >= tp or pnl <= -25.0:
                balance += pnl
                session_pnl += pnl
                pos_list.remove(p)
                if bot_type == "PROTECTOR" and session_pnl <= -40.0:
                    circuit_breaker_until = now + timedelta(minutes=15)

        # Entradas
        limit = 10 if bot_type == "CAZADOR" else 4 # Reducimos para el protector para mas realismo
        if len(pos_list) < limit and not circuit_breaker_until:
            if bot_type == "CAZADOR":
                if rsi < 30: pos_list.append({"type":"BUY", "entry":price})
                elif rsi > 70: pos_list.append({"type":"SELL", "entry":price})
            else: # PROTECTOR
                if m_speed < 60:
                    if rsi < 30 and price > ema20 and price > ema50:
                        pos_list.append({"type":"BUY", "entry":price})
                    elif rsi > 70 and price < ema20 and price < ema50:
                        pos_list.append({"type":"SELL", "entry":price})
    
    return daily_stats

def run_comparative():
    if not mt5.initialize(): return
    print("🛰️ Cargando historial...")
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 60000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10

    print("⚔️ Simulando Bot Cazador...")
    stats_a = simulate_bot("CAZADOR", df)
    print("🛡️ Simulando Bot Protector...")
    stats_b = simulate_bot("PROTECTOR", df)

    with open("CUADRO_COMPARATIVO_RESCATE.txt", "w") as f:
        f.write("COMPARATIVA TITAN: CAZADOR vs PROTECTOR (HISTORIAL REAL)\n")
        f.write("="*70 + "\n")
        f.write("FECHA      | BALANCE CAZADOR | BALANCE PROTECTOR | STATUS\n")
        f.write("-" * 70 + "\n")
        for d in sorted(stats_a.keys()):
            sa, sb = stats_a[d], stats_b[d]
            status = "PROTECTOR GANA" if sb > sa else "CAZADOR GANA"
            if sa <= 0: status = "CAZADOR QUEMADO"
            f.write(f"{d} | {sa:>15.2f} | {sb:>17.2f} | {status}\n")

run_comparative()
