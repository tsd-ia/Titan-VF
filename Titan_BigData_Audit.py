import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- AUDITORIA DE BIG DATA TITAN v39.2 (2 MESES) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    
    # Indicadores rápidos para HFT
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=5)
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    daily_results = []
    
    current_date = None
    day_profit = 0
    day_trades = 0
    
    limit = 10 # Metralleta
    tp_meta = 1.0 # Profit muy rápido para volumen
    sl_bunker = -25.0
    
    for i in range(10, len(df)):
        row = df.iloc[i]
        now = row['time']
        if not (7 <= now.hour <= 23): continue
            
        if current_date != row['date']:
            if current_date is not None:
                daily_results.append({"Date": str(current_date), "Profit": day_profit, "Trades": day_trades, "Balance": balance})
            current_date = row['date']
            day_profit = 0
            day_trades = 0
            
        price = row['close']
        rsi = row['rsi']
        ema = row['ema_fast']
        
        # 1. Cierres
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= tp_meta or pnl <= sl_bunker:
                balance += pnl
                day_profit += pnl
                day_trades += 1
                history.append(pnl)
                pos_list.remove(p)
                
        # 2. Entradas Metralleta (Simulado por ritmo de 2-3 p/min)
        if len(pos_list) < limit:
            # Lógica simple de momentum HFT
            if price > ema and rsi < 75:
                # Disparar 2 balas
                for _ in range(min(2, limit - len(pos_list))):
                    pos_list.append({"type": "BUY", "entry": price + (np.random.uniform(-0.02, 0.02))})
            elif price < ema and rsi > 25:
                # Disparar 2 balas
                for _ in range(min(2, limit - len(pos_list))):
                    pos_list.append({"type": "SELL", "entry": price + (np.random.uniform(-0.02, 0.02))})

    # Ultimo dia
    daily_results.append({"Date": str(current_date), "Profit": day_profit, "Trades": day_trades, "Balance": balance})
    
    hourly_vol = df.groupby(df['time'].dt.hour)['vol_pts'].mean()

    summary_file = "BigData_Audit_Report.txt"
    with open(summary_file, "w") as f:
        f.write("INFORME MAESTRO TITAN (60 DIAS)\n")
        f.write("="*40 + "\n")
        f.write(f"Profit Total: ${balance - INITIAL_BALANCE:.2f}\n")
        f.write(f"Trades Totales: {len(history)}\n\n")
        f.write("FECHA      | PROFIT | TRADES | BALANCE\n")
        for dr in daily_results:
            f.write(f"{dr['Date']} | {dr['Profit']:>7.2f} | {dr['Trades']:>6} | {dr['Balance']:>8.2f}\n")
        f.write("\nVOLATILIDAD\n")
        for hr, vol in hourly_vol.items():
            f.write(f"{hr:02d}:00 | {vol:.2f} Pts\n")

if __name__ == "__main__":
    run_simulation()
