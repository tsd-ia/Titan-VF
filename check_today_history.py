import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

def check_today_history():
    if not mt5.initialize():
        print("❌ Error MT5")
        return

    # Hoy desde las 00:00
    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    to_date = datetime.now()
    
    # Obtener deals (ejecuciones reales)
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None:
        print("❌ No hay historial")
        return

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    # Filtrar solo entradas (type 0=buy, 1=sell) o cierres
    # Los deals incluyen in/out/out_by
    # Contaremos entradas para saber cuántos trades se abrieron
    entradas = df[df['entry'] == 0] # 0 = ENTRY_IN
    
    print(f"📊 HISTORIAL REAL DE HOY ({from_date.strftime('%d/%m/%Y')})")
    print(f"✅ Trades Abiertos hoy: {len(entradas)}")
    
    # Ver profit total de hoy
    total_profit = df['profit'].sum()
    print(f"💰 Profit Real Acumulado: ${total_profit:.2f} USD")

if __name__ == "__main__":
    check_today_history()
