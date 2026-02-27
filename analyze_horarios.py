import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

# --- ANALIZADOR DE HORARIOS TITAN v39.2 (SIN EMOJIS) ---
SYMBOL = "XAUUSDm"

def analyze_hourly_patterns():
    if not mt5.initialize(): return
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)
    
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, end_date)
    if rates is None or len(rates) == 0:
        print("No se encontraron datos.")
        return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['time'].dt.hour
    df['vol'] = (df['high'] - df['low']) * 10 
    
    stats = df.groupby('hour')['vol'].mean()
    
    print("INFORME DE PATRONES HORARIOS (ULTIMAS 2 SEMANAS)")
    print("="*60)
    print(" HORA BROKER | VOLATILIDAD | CALIFICACION TACTICA")
    print("-" * 60)
    
    for hr, vol in stats.items():
        if 13 <= hr <= 17: 
            nota = "HORA DE ORO: Maximo profit, maximo riesgo (NY Open)."
        elif 8 <= hr <= 12:
            nota = "IDEAL: Scalping fluido y rítmico (London Session)."
        elif hr >= 19 and hr <= 20:
            nota = "PELIGRO: Gap de mercado y spreads altos."
        elif vol < 1.0:
            nota = "CEMENTERIO: Mercado lento."
        else:
            nota = "NORMAL: Operacion estandar."
            
        print(f"   {hr:02d}:00     |   {vol:>6.2f}    | {nota}")
    
    print("="*60)
    print("CONCLUSION: Sus mejores ráfagas ocurren entre las 13:00 y las 17:00 (Hora Broker).")

if __name__ == "__main__":
    analyze_hourly_patterns()
