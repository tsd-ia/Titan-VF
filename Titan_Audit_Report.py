
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import pytz

def generate_war_report():
    if not mt5.initialize():
        print("❌ Error al inicializar MT5")
        return

    # Definir el rango de tiempo (Chile UTC-3)
    tz_chile = pytz.timezone('America/Santiago')
    
    # Inicio: Ayer 02:00 AM Chile
    start_date = datetime(2026, 2, 23, 2, 0, 0)
    start_date_utc = tz_chile.localize(start_date).astimezone(pytz.utc)
    
    # Fin: Ahora (Chile)
    end_date = datetime.now()
    
    print(f"📊 Generando reporte desde {start_date_utc} UTC...")

    # Obtener historial de deals (órdenes ejecutadas)
    deals = mt5.history_deals_get(start_date_utc, end_date)
    
    if deals is None or len(deals) == 0:
        print("⚠️ No se encontraron jugadas en este periodo.")
        mt5.shutdown()
        return

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    
    # Filtrar solo entradas/salidas reales (no depósitos/ajustes)
    # entry: 0=IN, 1=OUT, 2=OUT_BY_POS
    # type: 0=BUY, 1=SELL
    df = df[df['entry'].isin([1, 2])] # Solo cierres para calcular PnL real
    
    # Agrupar por instrumento
    report_data = []
    instruments = df['symbol'].unique()

    for sym in instruments:
        sym_deals = df[df['symbol'] == sym]
        
        pos_monto = sym_deals[sym_deals['profit'] > 0]['profit'].sum()
        neg_monto = sym_deals[sym_deals['profit'] < 0]['profit'].sum()
        neto = sym_deals['profit'].sum()
        jugadas = len(sym_deals)
        ganadas = len(sym_deals[sym_deals['profit'] > 0])
        winrate = (ganadas / jugadas * 100) if jugadas > 0 else 0
        
        mejor = sym_deals['profit'].max()
        peor = sym_deals['profit'].min()
        
        report_data.append({
            "Instrumento": sym,
            "Ganancias ($)": f"{pos_monto:.2f}",
            "Pérdidas ($)": f"{neg_monto:.2f}",
            "Neto ($)": f"{neto:.2f}",
            "Jugadas": jugadas,
            "Winrate (%)": f"{winrate:.1f}%",
            "Mejor Cierre": f"{mejor:.2f}",
            "Peor Cierre": f"{peor:.2f}"
        })

    # Totales Globales
    total_pos = df[df['profit'] > 0]['profit'].sum()
    total_neg = df[df['profit'] < 0]['profit'].sum()
    total_neto = df['profit'].sum()
    total_jugadas = len(df)
    
    report_df = pd.DataFrame(report_data)
    
    # Generar Markdown
    with open("REPORTE_GUERRA_TITAN.md", "w", encoding="utf-8") as f:
        f.write(f"# ⚔️ REPORTE DE GUERRA TITAN\n")
        f.write(f"**Periodo:** {start_date.strftime('%Y-%m-%d %H:%M')} hasta Ahora (Chile)\n\n")
        
        f.write("## 💹 Resumen por Instrumento\n")
        f.write(report_df.to_markdown(index=False))
        f.write("\n\n")
        
        f.write("## 🏁 Balance Total de Operación\n")
        f.write(f"- **💰 Ganancia Total Brutal:** +${total_pos:.2f}\n")
        f.write(f"- **📉 Pérdida Total Sangrienta:** ${total_neg:.2f}\n")
        f.write(f"- **⚖️ Diferencia Salida (Neto):** **${total_neto:.2f}**\n")
        f.write(f"- **🎲 Cantidad de Jugadas:** {total_jugadas}\n")
        f.write(f"- **🏆 Rendimiento Global:** {(total_neto/total_pos*100 if total_pos > 0 else 0):.1f}% de retención.\n")
        
        f.write("\n\n---\n*Generado automáticamente por Auditoria Titán v27.6*")

    print("✅ REPORTE_GUERRA_TITAN.md generado con éxito.")
    mt5.shutdown()

if __name__ == "__main__":
    generate_war_report()
