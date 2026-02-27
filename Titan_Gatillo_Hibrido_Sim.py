import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR GATILLO HIBRIDO v39.6 (ATAQUE COMANDANTE + ESCUDO M5) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    print("🛰️ Cargando Big Data: Simulando GATILLO HIBRIDO (Ataque 40/60 + Veto M5)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    
    # Indicadores
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) # El Escudo 
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    daily_stats = []

    print("⚔️ Ciclo de 60 dias con Lote 0.01 y Escudo Activo...")

    current_date = None
    account_blown = False

    for i in range(50, len(df)):
        if account_blown: break
        
        row = df.iloc[i]
        now = row['time']
        
        if current_date != row['date']:
            if current_date is not None:
                daily_stats.append({"Date": str(current_date), "Balance": balance})
            current_date = row['date']

        if not (7 <= now.hour <= 23): continue
        if balance <= 0: 
            balance = 0
            account_blown = True
            continue
            
        # --- REGLAS HIBRIDAS v39.6 ---
        lot = 0.01
        limit = 50 # El Enjambre sigue disponible
        
        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']
        m_speed = row['vol_pts']

        # 1. Cierres Rapidos ($1.00 para fluidez)
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= 1.0 or pnl <= -25.0:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
        
        # 2. Gatillo Hibrido: Umbral bajado a 40/60 pero con FILTRO M5 REAL
        if len(pos_list) < limit:
            too_close = any(abs(price - p['entry']) < 0.15 for p in pos_list) 
            
            if not too_close and m_speed < 60:
                # COMPRA: RSI < 40 (Gatillo bajado de 30) PERO Precio > EMA50 (Escudo activo)
                if rsi < 40 and price > ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"BUY", "entry":price})
                # VENTA: RSI > 60 (Gatillo bajado de 70) PERO Precio < EMA50 (Escudo activo)
                elif rsi > 60 and price < ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"SELL", "entry":price})

    if not account_blown:
        daily_stats.append({"Date": str(current_date), "Balance": balance})
    
    with open("REPORTE_GATILLO_HIBRIDO_v39_6.txt", "w") as f:
        f.write("INFORME TITAN v39.6: GATILLO HIBRIDO (CUIDADOR + ATAQUE)\n")
        f.write("="*60 + "\n")
        f.write(f"Balance Final: ${balance:.2f}\n")
        f.write(f"Resultado Neto: ${balance - INITIAL_BALANCE:.2f}\n")
        f.write(f"Trades Totales: {len(history)}\n")
        f.write(f"Cuenta Quemada: {'SI' if account_blown else 'NO'}\n\n")
        f.write("CRECIMIENTO DIARIO:\n")
        for ds in daily_stats:
            f.write(f"{ds['Date']} | ${ds['Balance']:.2f}\n")

run_simulation()
