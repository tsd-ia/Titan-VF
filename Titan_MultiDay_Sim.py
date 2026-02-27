import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR DOBLE JORNADA v38.8 (CONSEJO DE VOTOS HFT) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0
LOT_SIZE = 0.01

def run_multi_day_sim(days_back):
    if not mt5.initialize():
        print("❌ Error MT5")
        return

    # Ajuste de días (Ayer y Antes de ayer)
    target_date = datetime.now() - timedelta(days=days_back)
    start_date = target_date.replace(hour=7, minute=0, second=0, microsecond=0)
    end_date = target_date.replace(hour=22, minute=0, second=0, microsecond=0)

    print(f"\n📅 SIMULANDO: {start_date.strftime('%d/%m/%Y')} (07:00 - 22:00)")
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0:
        print("❌ No hay datos para este día.")
        return 0, 0

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Indicadores HFT
    df['ema10'] = ta.trend.ema_indicator(df['close'], window=10)
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    
    # v38.8: Con $200 el límite es de 6 balas
    limit = 6 
    dist_bullets = 15 # 15 pts para ser agresivo
    
    for i in range(20, len(df)):
        price = df.iloc[i]['close']
        rsi = df.iloc[i]['rsi']
        ema = df.iloc[i]['ema10']
        low_bb = df.iloc[i]['bb_low']
        high_bb = df.iloc[i]['bb_high']
        
        # 1. Salidas (Scalping $1.50 - $3.00)
        for p in pos_list[:]:
            pnl = (price - p['entry_price']) * 10 if p['type'] == 'BUY' else (p['entry_price'] - price) * 10
            
            if pnl >= 1.80:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
            elif pnl <= -25.0:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)

        # 2. Entradas Metralleta
        if len(pos_list) < limit:
            # Votos: Reversión + Tendencia
            v_buy = (price <= low_bb) + (rsi < 40) + (price > ema)
            v_sell = (price >= high_bb) + (rsi > 60) + (price < ema)
            
            last_p = pos_list[-1]['entry_price'] if pos_list else (0 if v_buy >= 2 else 99999)
            dist = abs(price - last_p) * 100
            
            if v_buy >= 2 and (len(pos_list) == 0 or dist >= dist_bullets):
                pos_list.append({"type": "BUY", "entry_price": price})
            elif v_sell >= 2 and (len(pos_list) == 0 or dist >= dist_bullets):
                pos_list.append({"type": "SELL", "entry_price": price})

    profit = balance - INITIAL_BALANCE
    print(f"💰 Balance Final: ${balance:.2f} | Profit: ${profit:.2f}")
    print(f"✅ Trades: {len(history)} | Win Rate: {(len([x for x in history if x > 0])/len(history)*100 if history else 0):.1f}%")
    return profit, len(history)

if __name__ == "__main__":
    # Ayer (1 día atrás)
    p1, t1 = run_multi_day_sim(1)
    # Antes de ayer (2 días atrás)
    p2, t2 = run_multi_day_sim(2)
    
    print("\n" + "🏁" + "="*40 + "🏁")
    print(f"📉 RESUMEN FINAL $200 USD:")
    print(f"Día 1: ${p1:.2f} ({t1} trades)")
    print(f"Día 2: ${p2:.2f} ({t2} trades)")
    print(f"TOTAL ESTIMADO: ${p1+p2:.2f} USD")
    print("="*42)
