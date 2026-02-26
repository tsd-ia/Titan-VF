import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

class TitanSimulator:
    def __init__(self, symbol="XAUUSDm", initial_balance=100.0, lot=0.01):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.lot = lot
        self.balance = initial_balance
        self.equity = initial_balance
        self.history = []
        self.trades = []
        
    def get_data(self, days=30):
        if not mt5.initialize():
            return None
        
        utc_to = datetime.now()
        utc_from = utc_to - timedelta(days=days)
        
        # Obtenemos velas de 1 minuto para precisión de Scalping
        rates = mt5.copy_rates_range(self.symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
        if rates is None: return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def run(self, df, start_hour=8, end_hour=23):
        self.balance = self.initial_balance
        self.history = []
        self.trades = []
        active_trade = None
        
        # Simulación de ráfaga
        for i in range(20, len(df)):
            row = df.iloc[i]
            ts = row['time']
            curr_hour = ts.hour
            price = row['close']
            
            # FILTRO DE HORARIO
            if not (start_hour <= curr_hour <= end_hour):
                if active_trade: # Forzar cierre si salimos de horario (o dejarlo, depende del bot)
                    pass 
                continue

            if active_trade is None:
                # ESTRATEGIA SNIPER (Aproximación por momentum)
                # En un backtest real aquí usaríamos indicadores de TA-Lib
                m1_dir = 1 if row['close'] > row['open'] else -1 # Momentum simple
                
                # Simular una entrada "Sniper"
                if m1_dir == 1: # Supongamos señal de compra
                    active_trade = {"type": "BUY", "entry_price": price, "time": ts}
            else:
                # GESTIÓN DE SALIDA (Aproximación a nuestro Trailing y SL)
                pnl = (price - active_trade["entry_price"]) * 10 if active_trade["type"] == "BUY" else (active_trade["entry_price"] - price) * 10
                
                # TP de $2.00 o SL de -$25.00
                if pnl >= 2.0 or pnl <= -25.0:
                    self.balance += pnl
                    self.trades.append({
                        "entry": active_trade["time"],
                        "exit": ts,
                        "type": active_trade["type"],
                        "pnl": pnl,
                        "hour": active_trade["time"].hour,
                        "day": active_trade["time"].strftime('%A')
                    })
                    active_trade = None
            
            self.history.append({"time": ts.isoformat(), "balance": self.balance})

        return self.get_report()

    def find_best_window(self, df):
        # Análisis inteligente para detectar la ráfaga más rentable
        hourly_raw = {}
        for h in range(24):
            temp_trades = [t for t in self.trades if t['hour'] == h]
            hourly_raw[h] = sum(t['pnl'] for t in temp_trades)
        
        # Encontrar ventana de 8 horas consecutivas más rentable
        best_pnl = -9999
        best_range = (0, 0)
        for start in range(24):
            window = [(start + i) % 24 for i in range(8)]
            win_pnl = sum(hourly_raw.get(h, 0) for h in window)
            if win_pnl > best_pnl:
                best_pnl = win_pnl
                best_range = (start, (start + 7) % 24)
        return best_range, best_pnl

    def get_report(self):
        if not self.trades: return {"error": "No hubo trades en el periodo"}
        
        df_trades = pd.DataFrame(self.trades)
        best_range, best_pnl = self.find_best_window(None) # Pasamos None porque ya usa self.trades
        
        # SMART ANALYSIS: Mejores Horas
        hourly_pnl = df_trades.groupby('hour')['pnl'].sum().to_dict()
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.balance,
            "total_trades": len(self.trades),
            "win_rate": f"{(len(df_trades[df_trades['pnl'] > 0]) / len(df_trades)) * 100:.1f}%",
            "net_profit": self.balance - self.initial_balance,
            "recommendation": f"Operar entre las {best_range[0]}:00 y las {best_range[1]}:00 (Profit Proyectado: ${best_pnl:.2f})",
            "hourly_performance": hourly_pnl,
            "equity_curve": self.history[::60]
        }

if __name__ == "__main__":
    # Test rápido de consola
    sim = TitanSimulator(initial_balance=300.0)
    data = sim.get_data(days=7)
    if data is not None:
        report = sim.run(data, start_hour=9, end_hour=18)
        print(f"💰 Resultado Simulación: ${report['net_profit']:.2f}")
        print(f"📈 Win Rate: {report['win_rate']}")
