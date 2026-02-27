import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- SIMULADOR DE ALTO IMPACTO v38.8 (2 BALAS POR MINUTO - $200 USD) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0

def run_hft_simulation(date_target, current_balance):
    if not mt5.initialize(): return None
    
    start = date_target.replace(hour=7, minute=0, second=0, microsecond=0)
    end = date_target.replace(hour=18, minute=45, second=0, microsecond=0)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start, end)
    if rates is None or len(rates) < 100: return None
    
    df = pd.DataFrame(rates)
    df['ema10'] = ta.trend.ema_indicator(df['close'], window=10) # EMA rápida para HFT
    df['rsi'] = ta.momentum.rsi(df['close'], window=7) # RSI ultra-sensible
    
    balance = current_balance
    pos_list = []
    history = []
    
    # Parámetros Comandante: 2 balas por minuto de promedio, Max 10 con $200
    limit = 10 
    tp_meta = 1.0 # Cierres rápidos para volumen
    sl_bunker = -25.0
    
    for i in range(10, len(df)):
        price = df.iloc[i]['close']
        rsi = df.iloc[i]['rsi']
        ema = df.iloc[i]['ema10']
        now = df.iloc[i]['time']
        
        # 1. Gestión de Salidas (HFT Style)
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            
            if pnl >= tp_meta:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
            elif pnl <= sl_bunker:
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)

        # 2. Entradas Metralleta (Simulando 2-3 balas por minuto cuando hay señal)
        if len(pos_list) < limit:
            # Lógica: Si el precio tiene momentum y RSI da espacio
            # Simulamos el 'fast-path' del Oráculo con la EMA-Rápida
            if price > ema and rsi < 75:
                # Metemos hasta 2 balas seguidas si la tendencia es clara
                bullets_to_fire = 2 if len(pos_list) <= (limit - 2) else 1
                for _ in range(bullets_to_fire):
                    pos_list.append({"type": "BUY", "entry": price + (np.random.uniform(-0.05, 0.05))})
            elif price < ema and rsi > 25:
                bullets_to_fire = 2 if len(pos_list) <= (limit - 2) else 1
                for _ in range(bullets_to_fire):
                    pos_list.append({"type": "SELL", "entry": price + (np.random.uniform(-0.05, 0.05))})
                
    return {"balance": balance, "trades": len(history), "profit": balance - current_balance}

if __name__ == "__main__":
    print(f"🚀 [INFORME MAESTRO HFT] - 14 DÍAS | BALANCE INICIAL: ${INITIAL_BALANCE}")
    print(f"🎯 REFERENCIA: 2-3 Balas p/min | Scalping Puro | Oro")
    print("="*65)
    
    current_bal = INITIAL_BALANCE
    total_trades = 0
    report_data = []
    
    for d in range(14, 0, -1):
        target = datetime.now() - timedelta(days=d)
        if target.weekday() >= 5: continue
            
        res = run_hft_simulation(target, current_bal)
        if res:
            dia = target.strftime('%a %d/%b')
            print(f"📅 {dia} | Profit: ${res['profit']:>7.2f} | Trades: {res['trades']:>4} | Bal: ${res['balance']:>8.2f}")
            current_bal = res['balance']
            total_trades += res['trades']
            
    print("="*65)
    print(f"🏆 RENDIMIENTO TOTAL (2 Semanas): ${current_bal - INITIAL_BALANCE:.2f} USD")
    print(f"📈 VOLUMEN ACUMULADO: {total_trades} Operaciones")
    print(f"💰 PROMEDIO DIARIO: ${(current_bal - INITIAL_BALANCE)/10:.2f} USD")
