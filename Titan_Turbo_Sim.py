import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR TURBO METRALLETA v38.8 ---
START_DATE = datetime(2026, 2, 25, 7, 0)
END_DATE = datetime(2026, 2, 25, 22, 0)
INITIAL_BALANCE = 500.0 # Ponemos 500 para ver el potencial máximo
SYMBOL = "XAUUSDm"

def run_turbo_sim():
    if not mt5.initialize():
        print("❌ Error MT5")
        return

    print(f"🔥 [TURBO SIM] Re-analizando ayer con MODO METRALLETA HFT...")
    
    # Bajamos a datos de Tick o M1 muy denso
    # Para ser realistas con 700 trades, necesitamos simular entradas múltiples
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, START_DATE, END_DATE)
    if rates is None: return

    df = pd.DataFrame(rates)
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=10) # EMA rápida para HFT
    df['rsi'] = ta.momentum.rsi(df['close'], window=7) # RSI ultra-sensible
    
    balance = INITIAL_BALANCE
    pos_list = []
    history = []
    
    limit = 10 # Metralleta
    tp_points = 20 # 20 puntos = $2 de profit (Scalping agresivo)
    dist_bullets = 20 # Distancia mínima entre balas exigida
    
    for i in range(10, len(df)):
        now = pd.to_datetime(df.iloc[i]['time'], unit='s')
        # Simulamos 6 ticks por minuto (análisis cada 10s)
        for tick_step in range(6): 
            # Variación aleatoria pequeña para simular ticks dentro del minuto
            price = df.iloc[i]['close'] + (np.random.uniform(-0.05, 0.05))
            
            # 1. Gestión de Salidas
            for p in pos_list[:]:
                pnl = (price - p['entry_price']) * 10 if p['type'] == 'BUY' else (p['entry_price'] - price) * 10
                
                # Salida rápida HFT
                if pnl >= 1.50: # Salidas de $1.5 para volumen
                    balance += pnl
                    history.append(pnl)
                    pos_list.remove(p)
                elif pnl <= -25.0:
                    balance += pnl
                    history.append(pnl)
                    pos_list.remove(p)

            # 2. Lógica Metralleta (Múltiples entradas)
            if len(pos_list) < limit:
                rsi = df.iloc[i]['rsi']
                ema = df.iloc[i]['ema20']
                
                # Criterio HFT: Si el precio está a favor de la EMA y RSI no está saturado
                can_buy = price > ema and rsi < 80
                can_sell = price < ema and rsi > 20
                
                # Filtro de distancia (Metralleta 20 pts)
                last_price = pos_list[-1]['entry_price'] if pos_list else (0 if can_buy else 99999)
                dist = abs(price - last_price) * 100 # a puntos
                
                if can_buy and (len(pos_list) == 0 or dist >= dist_bullets):
                    pos_list.append({"type": "BUY", "entry_price": price, "time": now})
                elif can_sell and (len(pos_list) == 0 or dist >= dist_bullets):
                    pos_list.append({"type": "SELL", "entry_price": price, "time": now})

    print(f"\n🚀 REPORTE METRALLETA HFT (SIMULACIÓN)")
    print(f"💰 Balance Inicial: ${INITIAL_BALANCE}")
    print(f"💰 Balance Final: ${balance:.2f} (Profit: ${balance-INITIAL_BALANCE:.2f})")
    print(f"✅ OPERACIONES TOTALES: {len(history)}")
    if len(history) > 0:
        win_rate = (len([x for x in history if x > 0])/len(history))*100
        print(f"🎯 Win Rate: {win_rate:.1f}%")
        print(f"📈 Promedio por trade: ${sum(history)/len(history):.2f}")

if __name__ == "__main__":
    run_turbo_sim()
