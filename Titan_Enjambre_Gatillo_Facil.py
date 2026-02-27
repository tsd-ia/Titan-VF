import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR ENJAMBRE "GATILLO FACIL" v39.5 (MODO COMANDANTE) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    print("🛰️ Cargando historial... Bajando umbrales para MODO METRALLETA TOTAL.")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    
    # Indicadores
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) 
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    daily_stats = []

    print("⚔️ Ejecutando Protocolo ENJAMBRE v39.5 (Gatillo Rapido | RSI 45/55 | 60 dias)...")

    current_date = None
    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        if current_date != row['date']:
            if current_date is not None:
                daily_stats.append({"Date": str(current_date), "Balance": balance})
            current_date = row['date']

        if not (7 <= now.hour <= 23): continue
        if balance <= 0: 
            balance = 0
            continue
            
        # --- REGLAS AGRESIVAS v39.5 ---
        lot = 0.01
        limit = 50 # Cargador ampliado desde el inicio
        
        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']
        m_speed = row['vol_pts']

        # 1. Cierres Relampago (Take Profit de $0.50 - $0.80 para rotar rapido)
        # Esto es lo que permite sumar miles de trades
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= 0.8 or pnl <= -25.0:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
        
        # 2. Entradas Gatillo Facil (Umbrales de RSI mucho mas relajados)
        if len(pos_list) < limit:
            too_close = any(abs(price - p['entry']) < 0.10 for p in pos_list) # Distancia minima ultra corta
            
            if not too_close:
                # Comprar si RSI < 45 (en lugar de 30)
                if rsi < 45 and price > (ema50 - 1.0): # Filtro M5 muy relajado
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"BUY", "entry":price})
                # Vender si RSI > 55 (en lugar de 70)
                elif rsi > 55 and price < (ema50 + 1.0):
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"SELL", "entry":price})

    daily_stats.append({"Date": str(current_date), "Balance": balance})
    
    with open("REPORTE_ENJAMBRE_GATILLO_FACIL.txt", "w") as f:
        f.write("INFORME TITAN v39.5: GATILLO FACIL (60 DIAS)\n")
        f.write("="*60 + "\n")
        f.write(f"Balance Final: ${balance:.2f}\n")
        f.write(f"Profit Neto: ${balance - INITIAL_BALANCE:.2f}\n")
        f.write(f"Trades Totales: {len(history)}\n\n")
        f.write("CRECIMIENTO:\n")
        for ds in daily_stats:
            f.write(f"{ds['Date']} | ${ds['Balance']:.2f}\n")

run_simulation()
