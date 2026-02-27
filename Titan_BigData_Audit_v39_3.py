import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta

# --- AUDITORIA ESTRATEGA TITAN v39.3 (CEREBRO PROTECTOR) ---
SYMBOL = "XAUUSDm"
INITIAL_BALANCE = 200.0

def run_simulation():
    if not mt5.initialize(): return

    print("🛰️ Cargando historial de 2 meses...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0: return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    
    # Indicadores
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50) # Proxy M5
    df['rsi'] = ta.momentum.rsi(df['close'], window=7)
    df['vol_pts'] = (df['high'] - df['low']) * 10
    
    balance = INITIAL_BALANCE
    pos_list = []
    daily_results = []
    
    current_date = None
    day_profit = 0
    day_trades = 0
    session_pnl = 0.0
    circuit_breaker_until = None
    
    limit = 6 # Mas realista para balance de $200
    tp_meta = 1.5 # Simular spread y comisiones
    sl_bunker = -25.0

    print("⚔️ Simulando con Circuit Breaker (-$40) y Anti-Cuchillo...")

    for i in range(50, len(df)):
        row = df.iloc[i]
        now = row['time']
        
        # 1. Reset Diario
        if current_date != row['date']:
            if current_date is not None:
                daily_results.append({"Date": str(current_date), "Profit": day_profit, "Trades": day_trades, "Balance": balance})
            current_date = row['date']
            day_profit = 0
            day_trades = 0
            session_pnl = 0.0
            circuit_breaker_until = None
            
        if not (7 <= now.hour <= 23): continue
        if balance <= 0: break
            
        # 2. Check Circuit Breaker
        if circuit_breaker_until and now < circuit_breaker_until:
            continue

        price = row['close']
        rsi = row['rsi']
        ema20 = row['ema20']
        ema50 = row['ema50']
        m5_trend = "BUY" if price > ema50 else "SELL"
        m_speed = row['vol_pts']
        
        # 3. Gestion de Posiciones (Cierres)
        for p in pos_list[:]:
            pnl = (price - p['entry']) if p['type'] == 'BUY' else (p['entry'] - price)
            if pnl >= tp_meta or pnl <= sl_bunker:
                balance += pnl
                day_profit += pnl
                session_pnl += pnl
                day_trades += 1
                pos_list.remove(p)
                
                # Circuit Breaker v39.3
                if session_pnl <= -40.0:
                    circuit_breaker_until = now + timedelta(minutes=15)
        
        # 4. Entradas con Protocolo ESTRATEGA
        if len(pos_list) < limit and not circuit_breaker_until:
            
            # v39.3: Escudo Anti-Latigazo
            if m_speed > 60: continue 
            
            # Buscando señal HFT base
            if rsi < 35: # Sobreventa
                # v39.3: Anti-Cuchillo (No comprar si cae fuerte en M5 y precio < ema20)
                if m5_trend == "SELL" and price < ema20:
                    continue # VETO PROTECTOR
                
                for _ in range(min(2, limit - len(pos_list))):
                    pos_list.append({"type": "BUY", "entry": price})
                        
            elif rsi > 65: # Sobrecompra
                # v39.3: Anti-Cuchillo (No vender si sube fuerte en M5 y precio > ema20)
                if m5_trend == "BUY" and price > ema20:
                    continue # VETO PROTECTOR
                
                for _ in range(min(2, limit - len(pos_list))):
                    pos_list.append({"type": "SELL", "entry": price})

    # Ultimo dia
    daily_results.append({"Date": str(current_date), "Profit": day_profit, "Trades": day_trades, "Balance": balance})
    
    summary_file = "BigData_Audit_v39_3_Realista.txt"
    with open(summary_file, "w") as f:
        f.write("INFORME ESTRATEGA TITAN v39.3 (CEREBRO PROTECTOR)\n")
        f.write("="*60 + "\n")
        f.write(f"Balance Final: ${balance:.2f}\n")
        f.write(f"Resultado Neto: ${balance - INITIAL_BALANCE:.2f}\n")
        f.write(f"Filtros Proteccion: Circuit Breaker -$40 / Anti-Cuchillo ON\n\n")
        f.write("FECHA      | PROFIT | TRADES | BALANCE\n")
        f.write("-" * 50 + "\n")
        for dr in daily_results:
            f.write(f"{dr['Date']} | {dr['Profit']:>7.2f} | {dr['Trades']:>6} | {dr['Balance']:>8.2f}\n")

    print(f"✅ Auditoria Protectora Completa: {summary_file}")

if __name__ == "__main__":
    run_simulation()
