import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- RE-SIMULADOR TITAN v39.3 (MODO SUELDO SEMANAL) ---
SYMBOL = "XAUUSDm"
MONDAY_START_BALANCE = 200.0

def run_weekly_strategy_sim():
    if not mt5.initialize(): return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    
    # Indicadores
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) # Anti-Cuchillo
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = MONDAY_START_BALANCE
    pos_list = []
    
    weekly_withdrawals = []
    daily_stats = []
    
    total_withdrawn = 0
    current_date = None
    cb_until = None
    session_pnl = 0.0

    print("⚔️ Simulando Ciclos de Lunes a Viernes con escalado inteligente...")

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        # 1. Gestion de Cambio de Dia
        if current_date != row['date']:
            if current_date is not None:
                daily_stats.append({"Date": str(current_date), "Balance": balance})
                
                # RETIRO SEMANAL: Si hoy es sabado (cierre de viernes)
                if current_date.weekday() == 4:
                    withdrawal = max(0, balance - MONDAY_START_BALANCE)
                    total_withdrawn += withdrawal
                    weekly_withdrawals.append({"Date": str(current_date), "Amount": withdrawal})
                    balance = MONDAY_START_BALANCE
                    pos_list = []

            current_date = row['date']
            session_pnl = 0.0
            cb_until = None

        if not (7 <= now.hour <= 23): continue
        if balance <= 0: 
            balance = 0
            continue # Simular que se espera al lunes
            
        # --- ESCALADO INTELIGENTE ---
        limit = 3 # Base protectora
        tp_meta = 1.2
        if balance > 300: 
            limit = 6 
            tp_meta = 2.5 # Mas ataque, mas respaldo
        elif balance > 250:
            limit = 4
        
        if cb_until and now < cb_until: continue

        price = row['close']
        rsi = row['rsi']
        ema20 = row['ema20']
        ema50 = row['ema50']
        m_speed = row['vol_pts']

        # Procesar Posiciones
        for p in pos_list[:]:
            p_pnl = (price-p['entry']) if p['type']=='BUY' else (p['entry']-price)
            if p_pnl >= tp_meta or p_pnl <= -25.0:
                balance += p_pnl
                session_pnl += p_pnl
                pos_list.remove(p)
                if session_pnl <= -40.0: cb_until = now + timedelta(minutes=15)
        
        # Entradas con Proteccion M5
        if len(pos_list) < limit and not cb_until:
            if m_speed < 60:
                # Lógica HFT base (RSI) con Veto Protector (EMA50)
                if rsi < 35 and price > ema50: # Solo buy si no hay caida libre
                    pos_list.append({"type":"BUY", "entry":price})
                elif rsi > 65 and price < ema50: # Solo sell si no hay subida libre
                    pos_list.append({"type":"SELL", "entry":price})

    # Guardar Informe
    with open("REPORTE_RETIROS_TITAN.txt", "w") as f:
        f.write("ESTRATEGIA TITAN: PLAN DE SUELDO SEMANAL (v39.3)\n")
        f.write("="*60 + "\n")
        f.write(f"Total Retirado (60 dias): ${total_withdrawn:.2f}\n")
        f.write(f"Sueldo Promedio Semanal: ${total_withdrawn/8:.2f}\n\n")
        f.write("RETIROS DE CADA VIERNES:\n")
        f.write("-" * 50 + "\n")
        for rw in weekly_withdrawals:
            f.write(f"Viernes {rw['Date']} | Retiro: ${rw['Amount']:>8.2f}\n")
        f.write("\nDETALLE DIARIO:\n")
        for ds in daily_stats:
            f.write(f"{ds['Date']} | Balance: ${ds['Balance']:>8.2f}\n")

run_weekly_strategy_sim()
