import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

def analyze_hft_frequency():
    if not mt5.initialize():
        print("❌ Error MT5")
        return

    # Última hora de actividad
    to_date = datetime.now()
    from_date = to_date - timedelta(hours=1)
    
    # Obtener deals (ejecuciones reales)
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None or len(deals) == 0:
        print(f"📊 ANALISIS DE FRECUENCIA (Última hora: {from_date.strftime('%H:%M')} - {to_date.strftime('%H:%M')})")
        print("ℹ️ No hay operaciones en la última hora.")
        return

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    
    # 0 = ENTRY_IN (Entradas a mercado)
    entradas = df[df['entry'] == 0]
    num_entradas = len(entradas)
    
    # Dividir por 60 minutos
    promedio_por_minuto = num_entradas / 60.0
    
    print(f"📊 ANÁLISIS DE RITMO TITAN (Última hora)")
    print(f"==========================================")
    print(f"✅ Entradas totales: {num_entradas}")
    print(f"⏱️ Promedio de entradas: {promedio_por_minuto:.2f} por minuto")
    
    if promedio_por_minuto > 0:
        segundos_entre_entrada = 60.0 / promedio_por_minuto
        print(f"⚡ Frecuencia: Una entrada cada {segundos_entre_entrada:.1f} segundos")
    
    # Ver profit de esta hora
    profit_hora = df['profit'].sum()
    print(f"💰 PnL de la última hora: ${profit_hora:.2f} USD")
    print(f"==========================================")

if __name__ == "__main__":
    analyze_hft_frequency()
