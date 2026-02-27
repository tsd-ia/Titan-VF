import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import ta

# --- AUDITORÍA REAL DE DATOS ---
def audit_real_data():
    if not mt5.initialize():
        print("Error MT5")
        return

    sym = "XAUUSDm"
    # Ayer: 25 de Febrero
    start = datetime(2026, 2, 25, 7, 0)
    end = datetime(2026, 2, 25, 10, 0) # Solo las primeras 3 horas para la muestra

    rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, start, end)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Indicadores igual que en TitanBrain
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_up'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    
    print(f"🕵️‍♂️ AUDITANDO DATOS REALES DE {sym}...")
    print(f"Muestra inicial de 5 velas de ayer:")
    print(df[['time', 'open', 'high', 'low', 'close']].head())
    
    trades_encontrados = 0
    balance = 500.0
    
    print("\n--- PRIMERAS 5 OPERACIONES SIMULADAS (REGLAS TITAN v38.8) ---")
    for i in range(20, len(df)):
        price = df.iloc[i]['close']
        rsi = df.iloc[i]['rsi']
        low_bb = df.iloc[i]['bb_low']
        high_bb = df.iloc[i]['bb_up']
        ts = df.iloc[i]['time']
        
        # Lógica Sniper: Suelo BB + RSI bajo
        if price <= low_bb and rsi < 40 and trades_encontrados < 5:
            profit_simulado = 2.0 # Meta rápida
            print(f"✅ TRADE #{trades_encontrados+1} | HORA: {ts} | TIPO: BUY | PRECIO: {price:.3f}")
            print(f"   [Filtros]: RSI {rsi:.1f} | BB_LOW {low_bb:.3f}")
            trades_encontrados += 1

if __name__ == "__main__":
    audit_real_data()
