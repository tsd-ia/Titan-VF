import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR ENJAMBRE v39.4 (ESTRATEGIA REAL DEL COMANDANTE) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    print("🛰️ Cargando historial de 2 meses (Big Data)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    
    # Indicadores
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) # Protector M5
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    
    total_profit = 0
    max_drawdown = 0
    current_date = None
    daily_stats = []

    print("⚔️ Ejecutando Protocolo ENJAMBRE v39.4 (0.01 lot | 50 balcones)...")

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        if current_date != row['date']:
            if current_date is not None:
                daily_stats.append({"Date": str(current_date), "Balance": balance})
            current_date = row['date']

        if not (7 <= now.hour <= 23): continue
        if balance <= 0: break
            
        # --- REGLAS v39.4 ---
        lot = 0.01
        limit = 15
        if balance > 300: limit = 30
        if balance > 500: limit = 50
        
        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']
        m_speed = row['vol_pts']

        # 1. Cierres (Take Profit de $1.0 - $1.5 rápido)
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= 1.2 or pnl <= -25.0:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
        
        # 2. Entradas Metralleta (Distancia 0.15)
        if len(pos_list) < limit:
            # Solo si no hay una bala demasiado cerca (0.15 pts)
            too_close = any(abs(price - p['entry']) < 0.15 for p in pos_list)
            
            if not too_close and m_speed < 60:
                # Veto Protector Anti-Cuchillo (EMA50)
                if rsi < 30 and price > ema50:
                    # Metemos ráfaga de 3 abejas
                    for _ in range(min(3, limit - len(pos_list))):
                        pos_list.append({"type":"BUY", "entry":price})
                elif rsi > 70 and price < ema50:
                    for _ in range(min(3, limit - len(pos_list))):
                        pos_list.append({"type":"SELL", "entry":price})

    # Ultimo dia
    daily_stats.append({"Date": str(current_date), "Balance": balance})
    
    with open("REPORTE_FINAL_ENJAMBRE_v39_4.txt", "w") as f:
        f.write("INFORME MAESTRO TITAN v39.4: PROTOCOLO ENJAMBRE (60 DIAS)\n")
        f.write("="*60 + "\n")
        f.write(f"Balance Inicial: ${INITIAL_BALANCE}\n")
        f.write(f"Balance Final: ${balance:.2f}\n")
        f.write(f"Profit Neto: ${balance - INITIAL_BALANCE:.2f}\n")
        f.write(f"Trades Totales: {len(history)}\n\n")
        f.write("CRECIMIENTO DIARIO:\n")
        f.write("-" * 50 + "\n")
        for ds in daily_stats:
            f.write(f"{ds['Date']} | Balance: ${ds['Balance']:>8.2f}\n")

    print("✅ Auditoria v39.4 Completa: REPORTE_FINAL_ENJAMBRE_v39_4.txt")

if __name__ == "__main__":
    run_simulation()
