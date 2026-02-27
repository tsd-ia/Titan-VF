import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import ta

# --- RE-SIMULACIÓN MEJORADA (CONCONSEJO DE VOTOS) ---
START_DATE = datetime(2026, 2, 25, 7, 0)
END_DATE = datetime(2026, 2, 25, 22, 0)
INITIAL_BALANCE = 300.0
SYMBOL = "XAUUSDm"

def run_simulation():
    if not mt5.initialize():
        print("❌ Error al conectar con MT5")
        return

    # Obtener historial de velas M1
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, START_DATE, END_DATE)
    if rates is None or len(rates) == 0:
        print("❌ No hay datos.")
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Indicadores
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_upper'] = indicator_bb.bollinger_hband()
    df['bb_lower'] = indicator_bb.bollinger_lband()
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    limit = 10 # Para 300 USD

    for i in range(25, len(df)):
        now = df.iloc[i]['time']
        price = df.iloc[i]['close']
        
        # 1. Gestión de Salidas
        for p in pos_list[:]:
            p['pnl'] = (price - p['entry_price']) * 10 if p['type'] == 'BUY' else (p['entry_price'] - price) * 10
            
            # Cierre por profit (v38.1 Godzilla Air)
            if p['pnl'] >= 3.0: # Profit meta de $3
                balance += p['pnl']
                history.append(p['pnl'])
                pos_list.remove(p)
            elif p['pnl'] <= -25.0: # SL Bunker 2026
                balance += p['pnl']
                history.append(p['pnl'])
                pos_list.remove(p)

        # 2. Consejo de Votos (v31.0 Simplificado)
        if len(pos_list) < limit:
            v_buy = 0
            v_sell = 0
            
            # Voto 1: RSI
            rsi = df.iloc[i]['rsi']
            if rsi < 40: v_buy += 1
            elif rsi > 60: v_sell += 1
            
            # Voto 2: Bollinger
            if price < df.iloc[i]['bb_lower']: v_buy += 2
            elif price > df.iloc[i]['bb_upper']: v_sell += 2
            
            # Voto 3: Tendencia EMA
            if price > df.iloc[i]['ema20']: v_buy += 1
            else: v_sell += 1
            
            # Ejecutar si hay consenso
            if v_buy >= 3:
                pos_list.append({"type": "BUY", "entry_price": price, "time": now, "pnl": 0})
            elif v_sell >= 3:
                pos_list.append({"type": "SELL", "entry_price": price, "time": now, "pnl": 0})

    print(f"\n📊 SIMULACIÓN TITAN v38.8 (AYER)")
    print(f"💰 Balance Inicial: ${INITIAL_BALANCE}")
    print(f"💰 Balance Final: ${balance:.2f} (Profit: ${balance-INITIAL_BALANCE:.2f})")
    print(f"✅ Trades Totales: {len(history)}")
    if len(history) > 0:
        print(f"🎯 Efectividad: {(len([x for x in history if x > 0])/len(history))*100:.1f}%")

if __name__ == "__main__":
    run_simulation()
