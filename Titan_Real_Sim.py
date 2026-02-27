import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR REALISTA "700 TRADES" v38.8 ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0

def run_day_sim(date_target):
    if not mt5.initialize():
        return None
    
    start = date_target.replace(hour=7, minute=0, second=0, microsecond=0)
    end = date_target.replace(hour=22, minute=0, second=0, microsecond=0)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start, end)
    if rates is None or len(rates) == 0:
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Indicadores HFT ultra-rápidos
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=5)
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    
    # Configuración HFT Metralleta
    limit = 6 # Con $200
    tp_meta = 0.50 # Profi muy rápido para volumen
    sl_bunker = -25.0
    
    for i in range(10, len(df)):
        price = df.iloc[i]['close']
        rsi = df.iloc[i]['rsi']
        ema = df.iloc[i]['ema_fast']
        
        # 1. Gestionar cierres (MODO HFT)
        for p in pos_list[:]:
            # XAUUSDm Multipler (0.01 lote = $1 por cada $1 de precio)
            pnl = (price - p['entry_p']) if p['type'] == 'BUY' else (p['entry_p'] - price)
            
            if pnl >= tp_meta:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
            elif pnl <= sl_bunker:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
                
        # 2. Entradas rápidas
        if len(pos_list) < limit:
            # Lógica: Seguir momentum + RSI
            if price > ema and rsi < 70:
                pos_list.append({"type": "BUY", "entry_p": price})
            elif price < ema and rsi > 30:
                pos_list.append({"type": "SELL", "entry_p": price})
                
    return {"balance": balance, "trades": len(history), "profit": balance - INITIAL_BALANCE}

if __name__ == "__main__":
    print(f"🕵️‍♂️ ANALIZANDO CON $200 USD (MODO METRALLETA)")
    
    # Ayer (25)
    res_ayer = run_day_sim(datetime.now() - timedelta(days=1))
    # Antes de ayer (24)
    res_antes = run_day_sim(datetime.now() - timedelta(days=2))
    
    if res_ayer:
        print(f"\n📊 AYER (25/02):")
        print(f"💰 Balance: ${res_ayer['balance']:.2f} | Profit: ${res_ayer['profit']:.2f}")
        print(f"✅ Trades: {res_ayer['trades']}")
        
    if res_antes:
        print(f"\n📊 ANTES DE AYER (24/02):")
        print(f"💰 Balance: ${res_antes['balance']:.2f} | Profit: ${res_antes['profit']:.2f}")
        print(f"✅ Trades: {res_antes['trades']}")
        
    if res_ayer and res_antes:
        t_profit = res_ayer['profit'] + res_antes['profit']
        print(f"\n🏆 RESULTADO TOTAL 48H: ${t_profit:.2f} USD")
