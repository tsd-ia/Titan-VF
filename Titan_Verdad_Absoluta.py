import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULACION DE LA VERDAD (ESTRATEGIA REAL DEL COMANDANTE) ---
SYMBOL = "XAUUSDm"
MONDAY_START_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    print("🛰️ Cargando historial... Sin filtros raros. Todo real.")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['weekday'] = df['time'].dt.weekday
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) # Escudo M5
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    
    balance = MONDAY_START_BALANCE
    pos_list = []
    daily_results = []
    weekly_withdrawals = []
    
    current_week_withdrawal = 0
    current_week_num = 1
    
    print("⚔️ Iniciando Combate: 2 Meses de Historia Real...")

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        # CIERRE DE VIERNES (18:45)
        if row['weekday'] == 4 and now.hour == 18 and now.minute == 45:
            # Liquidar todo
            for p in pos_list[:]:
                pnl = (row['close'] - p['entry']) if p['type'] == 'BUY' else (p['entry'] - row['close'])
                balance += pnl
                pos_list.remove(p)
            
            w = max(0, balance - MONDAY_START_BALANCE)
            weekly_withdrawals.append(w)
            # LOG SEMANAL
            daily_results.append(f"--- FIN SEMANA {current_week_num} | RETIRO: ${w:.2f} ---")
            
            # REINICIO LUNES
            balance = MONDAY_START_BALANCE
            current_week_num += 1
            continue

        if balance <= 0:
            balance = 0
            continue # Espera al proximo viernes/lunes

        # --- PARAMETROS DE LA VERDAD (ESTILO COMANDANTE) ---
        limit = 50 
        dist_min = 0.15 # Volvemos a los 0.15 del exito
        rsi_buy, rsi_sell = 40, 60 # Gatillo rapido
        
        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']

        # 1. Cierres ($1.00 rapido)
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= 1.0 or pnl <= -25.0:
                balance += pnl
                pos_list.remove(p)

        # 2. Entradas (Enjambre 5 abejas por tick)
        if len(pos_list) < limit:
            too_close = any(abs(price - p['entry']) < dist_min for p in pos_list)
            if not too_close:
                # El Escudo M5 manda para no morir
                if rsi < rsi_buy and price > ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"BUY", "entry":price})
                elif rsi > rsi_sell and price < ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"SELL", "entry":price})
        
        # Log Diario al final del dia (solo para ver progreso)
        if now.hour == 23 and now.minute == 59:
             daily_results.append(f"{row['date']} | Balance: ${balance:.2f} | Pos: {len(pos_list)}")

    with open("VERDAD_ABS_TITAN.txt", "w") as f:
        f.write("INFORME DE LA VERDAD ABSOLUTA: TITAN v39.7\n")
        f.write("="*60 + "\n")
        for line in daily_results:
            f.write(line + "\n")
        f.write("="*60 + "\n")
        f.write(f"TOTAL RETIRADO: ${sum(weekly_withdrawals):.2f}\n")

run_simulation()
