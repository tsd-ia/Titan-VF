import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- AUDITORÍA MAESTRA TITAN v38.8 (14 DÍAS) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 100.0

def run_day_simulation(date_target, current_balance):
    if not mt5.initialize(): return None
    
    # Horario de operación 07:00 a 19:00 (Antes del cierre de Oro)
    start = date_target.replace(hour=7, minute=0, second=0, microsecond=0)
    end = date_target.replace(hour=18, minute=45, second=0, microsecond=0)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start, end)
    if rates is None or len(rates) < 10: 
        # Si no hay XAUUSDm, probar XAUUSD (algunas cuentas cambian)
        rates = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M1, start, end)
        if rates is None or len(rates) < 10: return None
    
    df = pd.DataFrame(rates)
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_up'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    
    balance = current_balance
    pos_list = []
    history = []
    
    # Parámetros Titan v38.8 (HFT Scalping Sensitive)
    limit = 3 if balance < 150 else 6
    
    for i in range(20, len(df)):
        price = df.iloc[i]['close']
        rsi = df.iloc[i]['rsi']
        ema = df.iloc[i]['ema20']
        bb_up = df.iloc[i]['bb_up']
        bb_low = df.iloc[i]['bb_low']
        
        # 1. Gestión de Salidas (Escalado según cuenta real del Comandante)
        for p in pos_list[:]:
            # XAUUSDm: 1.0 lot = $100 per point. 0.01 lot = $1 per point.
            # Diferencia de precio directa es profit en $ para 0.01
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            
            # Cierre rápido como se ve en las capturas ($1.00 - $2.50)
            if pnl >= 1.20: 
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)
            elif pnl <= -25.0: # SL Bunker 
                balance += pnl
                history.append(pnl)
                pos_list.remove(p)

        # 2. Entradas Metralleta (Más sensibilidad)
        if len(pos_list) < limit:
            # Reversión rápida + RSI flexible
            v_buy = (price <= bb_low + 0.1) or (rsi < 40)
            v_sell = (price >= bb_up - 0.1) or (rsi > 60)
            
            # Distancia mínima reducida para modo metralleta
            can_fire = True
            if len(pos_list) > 0:
                dist = abs(price - pos_list[-1]['entry'])
                if dist < 0.20: can_fire = False
                
            if v_buy and can_fire and price > ema:
                pos_list.append({"type": "BUY", "entry": price})
            elif v_sell and can_fire and price < ema:
                pos_list.append({"type": "SELL", "entry": price})
                
    return {"balance": balance, "trades": len(history), "profit": balance - current_balance}

if __name__ == "__main__":
    current_bal = INITIAL_BALANCE
    print(f"🕵️‍♂️ AUDITORÍA MAESTRA v38.8 | SALDO INICIAL: ${INITIAL_BALANCE}")
    print("="*60)
    
    report = []
    for d in range(14, 0, -1):
        target = datetime.now() - timedelta(days=d)
        if target.weekday() >= 5: continue
            
        res = run_day_simulation(target, current_bal)
        if res:
            dia = target.strftime('%a %d/%b')
            print(f"📅 {dia} | Profit: ${res['profit']:>6.2f} | Trades: {res['trades']:>3} | Bal: ${res['balance']:>7.2f}")
            current_bal = res['balance']
            
    print("="*60)
    print(f"🏆 RESULTADO TOTAL 14 DÍAS: ${current_bal - INITIAL_BALANCE:.2f} USD")
