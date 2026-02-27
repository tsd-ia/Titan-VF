import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- AUDITORIA SEMANAL TITAN v39.7 (REGLA DE LOS $100 Y GATILLO HIBRIDO) ---
# Version sin caracteres especiales para evitar fallos de codificacion
SYMBOL = "XAUUSDm"
MONDAY_START_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    print("Cargando Big Data para Auditoria Detallada (60 dias)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['weekday'] = df['time'].dt.weekday # 0=Mon, 4=Fri
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) 
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = MONDAY_START_BALANCE
    pos_list = []
    weekly_log = []
    
    week_start_date = None
    current_week_num = 1

    print("Analizando Semana por Semana con Reseteo de Lunes...")

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        if week_start_date is None:
            week_start_date = row['date']

        # GESTION DE VIERNES (CIERRE 18:45)
        if row['weekday'] == 4 and now.hour == 18 and now.minute == 45:
            for p in pos_list[:]:
                pnl = (row['close'] - p['entry']) if p['type'] == 'BUY' else (p['entry'] - row['close'])
                balance += pnl
                pos_list.remove(p)
            
            withdrawal = max(0, balance - MONDAY_START_BALANCE)
            weekly_log.append({
                "Week": current_week_num,
                "Start": str(week_start_date),
                "End": str(row['date']),
                "FinalBalance": balance,
                "Withdrawal": withdrawal,
                "Status": "GANANCIA OK" if withdrawal > 0 else "SIN RETIRO"
            })
            
            balance = MONDAY_START_BALANCE
            current_week_num += 1
            week_start_date = None
            continue

        if balance <= 0:
            balance = 0
            continue

        if not (7 <= now.hour <= 23): continue

        # --- LOGICA v39.7 ---
        if balance < 100:
            limit = 6
            rsi_buy, rsi_sell = 30, 70
        else:
            limit = 50
            rsi_buy, rsi_sell = 40, 60

        price = row['close']
        rsi = row['rsi']
        ema50 = row['ema50']

        # Cierres
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= 1.2 or pnl <= -25.0: # TP 1.2 para compensar spread/comision
                balance += pnl
                pos_list.remove(p)

        # Entradas
        if len(pos_list) < limit:
            too_close = any(abs(price - p['entry']) < 0.20 for p in pos_list)
            if not too_close:
                if rsi < rsi_buy and price > ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"BUY", "entry":price})
                elif rsi > rsi_sell and price < ema50:
                    for _ in range(min(5, limit - len(pos_list))):
                        pos_list.append({"type":"SELL", "entry":price})

    with open("AUDITORIA_DETALLADA_v39_7.txt", "w") as f:
        f.write("AUDITORIA SEMANA POR SEMANA - TITAN v39.7\n")
        f.write("="*70 + "\n")
        f.write("SEM | DESDE      | HASTA      | BAL. FINAL | RETIRO     | STATUS\n")
        f.write("-" * 70 + "\n")
        total_retirado = 0
        for w in weekly_log:
            f.write(f"{w['Week']:>3} | {w['Start']} | {w['End']} | ${w['FinalBalance']:>9.2f} | ${w['Withdrawal']:>9.2f} | {w['Status']}\n")
            total_retirado += w['Withdrawal']
        f.write("-" * 70 + "\n")
        f.write(f"TOTAL RETIRADO EN 2 MESES: ${total_retirado:.2f} USD\n")
        f.write("="*70 + "\n")

if __name__ == "__main__":
    run_simulation()
