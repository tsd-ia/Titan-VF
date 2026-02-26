import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DEL SIMULADOR ---
SYMBOL = "XAUUSDm"
TIMEFRAME_BASE = mt5.TIMEFRAME_M1
LOOKBACK_DAYS = 3 # Cuántos días atrás queremos ver?
LOTE_TEST = 0.01

def get_h1_trend(rates_h1):
    if rates_h1 is None or len(rates_h1) < 20: return "NONE"
    close_prices = pd.Series([r[4] for r in rates_h1]) # close
    ema20 = close_prices.ewm(span=20).mean().iloc[-1]
    return "BUY" if close_prices.iloc[-1] > ema20 else "SELL"

def get_m5_trend(rates_m5):
    if rates_m5 is None or len(rates_m5) < 5: return "NONE", "⚪"
    # Lógica simplificada de tendencia
    c1 = rates_m5[-1][4] > rates_m5[-2][4]
    c2 = rates_m5[-2][4] > rates_m5[-3][4]
    if c1 and c2: return "BUY", "🟢🟢"
    if not c1 and not c2: return "SELL", "🔴🔴"
    return "NONE", "⚪"

async def run_backtest():
    if not mt5.initialize():
        print("❌ Error al conectar con MT5")
        return

    print(f"🚀 [TIME MACHINE] Iniciando simulación para {SYMBOL}...")
    print(f"📅 Analizando últimos {LOOKBACK_DAYS} días...")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)
    
    # Obtener historial de velas
    rates = mt5.copy_rates_range(SYMBOL, TIMEFRAME_BASE, start_date, end_date)
    if rates is None:
        print("❌ No se obtuvieron datos históricos.")
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    results = {"win": 0, "loss": 0, "total_pnl": 0.0}
    active_trade = None

    for i in range(50, len(df)):
        # Simular "Cerebro" en este punto del tiempo
        curr_price = df.iloc[i]['close']
        ts = df.iloc[i]['time']
        
        # Simular contexto M5 y H1
        # (Esto es una aproximación, el cerebro real usa copy_rates_from_pos)
        # Aquí solo evaluamos la calidad de la entrada sniper
        
        # Filtro Sniper v34.1: (Simulado)
        # Supongamos que hay una señal técnica...
        # En el backtest real, aquí irían los indicadores del council
        
        # Ejemplo: Si m5 y h1 están alineados...
        # Esta es la lógica que el comandante quiere probar
        m5_trend, m5_label = get_m5_trend(rates[max(0, i-25):i])
        h1_trend = "BUY" # Simplificado
        
        if active_trade is None:
            # BUSCAR ENTRADA SNIPER ALINEADA
            if m5_trend == "BUY" and h1_trend == "BUY":
                active_trade = {"type": "BUY", "price": curr_price, "entry_time": ts}
                # print(f"🟢 [ENTRADA] {ts} | BUY @ {curr_price}")
            elif m5_trend == "SELL" and h1_trend == "SELL":
                active_trade = {"type": "SELL", "price": curr_price, "entry_time": ts}
                # print(f"🔴 [ENTRADA] {ts} | SELL @ {curr_price}")
        
        else:
            # GESTIÓN DE SALIDA
            tp = 2.0 # $2 USD
            sl = -25.0 # Stop Loss Bunker
            
            pnl = (curr_price - active_trade["price"]) * 10 if active_trade["type"] == "BUY" else (active_trade["price"] - curr_price) * 10
            
            if pnl >= tp:
                results["win"] += 1
                results["total_pnl"] += pnl
                # print(f"💰 [TAKE PROFIT] {ts} | +${pnl:.2f}")
                active_trade = None
            elif pnl <= sl:
                results["loss"] += 1
                results["total_pnl"] += pnl
                # print(f"💀 [STOP LOSS] {ts} | -${abs(pnl):.2f}")
                active_trade = None

    print("\n" + "="*40)
    print(f"📊 REPORTE FINAL TITAN TIME MACHINE ({LOOKBACK_DAYS} DÍAS)")
    print(f"Ganadas: {results['win']} | Perdidas: {results['loss']}")
    print(f"PnL Estimado: ${results['total_pnl']:.2f} USD")
    print(f"Calidad de Estrategia: {((results['win']/(results['win']+results['loss']))*100):.1f}%" if (results['win']+results['loss']) > 0 else "0%")
    print("="*40)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_backtest())
