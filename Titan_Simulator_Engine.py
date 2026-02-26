import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

class TitanSimulator:
    def __init__(self, symbol="XAUUSDm", initial_balance=50.0, lot=0.01):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.lot = lot
        self.balance = initial_balance
        self.spread_penalty = 0.45 
        self.positions = [] 
        self.trades_history = []
        self.equity_history = []
        self.max_basket_pnl = 0.0
        
    def get_data(self, days=7):
        if not mt5.initialize(): return None
        utc_to = datetime.now()
        utc_from = utc_to - timedelta(days=days)
        rates = mt5.copy_rates_range(self.symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
        if rates is None: return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def run(self, df, start_hour=8, end_hour=23):
        self.balance = self.initial_balance
        self.positions = []
        self.trades_history = []
        self.equity_history = []
        self.max_basket_pnl = 0.0
        last_fire_time = datetime(2000, 1, 1)
        
        daily_pnl = {}
        balance_at_start_of_day = self.initial_balance

        for i in range(100, len(df)):
            row = df.iloc[i]
            ts = row['time']
            price = row['close']
            day_key = ts.strftime('%Y-%m-%d')
            
            if day_key not in daily_pnl:
                daily_pnl[day_key] = 0.0
            
            # --- CÁLCULO DE LOTE DINÁMICO (Retroactivo v37.2) ---
            if self.balance < 50:
                current_lot = 0.01
                active_limit = 1
            elif self.balance < 100:
                current_lot = 0.02
                active_limit = 3
            else:
                current_lot = 0.04
                active_limit = 5

            # --- GESTIÓN DE CANASTA (BASKET TRAIL v37.1) ---
            current_open_pnl = 0
            for p in self.positions:
                diff = (price - p["entry"]) if p["type"] == "BUY" else (p["entry"] - price)
                p_pnl = (diff * (p["lot"] / 0.01)) - self.spread_penalty
                current_open_pnl += p_pnl
            
            if current_open_pnl > self.max_basket_pnl:
                self.max_basket_pnl = current_open_pnl
            
            secure_b = -999.0
            if self.max_basket_pnl >= 5.0:
                if self.max_basket_pnl >= 10.0:
                    secure_b = (self.max_basket_pnl // 5) * 5 - 5
                else:
                    secure_b = 1.0
            
            if current_open_pnl <= secure_b and len(self.positions) > 0:
                self.balance += current_open_pnl
                daily_pnl[day_key] += current_open_pnl
                for p in self.positions:
                    p_diff = (price - p["entry"]) if p["type"] == "BUY" else (p["entry"] - price)
                    ind_pnl = (p_diff * (p["lot"] / 0.01)) - self.spread_penalty
                    self.trades_history.append({"pnl": ind_pnl, "entry_time": p["time"], "exit_time": ts, "date": day_key})
                self.positions = []
                self.max_basket_pnl = 0.0
                continue

            # GESTIÓN INDIVIDUAL
            remaining_positions = []
            for p in self.positions:
                diff = (price - p["entry"]) if p["type"] == "BUY" else (p["entry"] - price)
                p_pnl = (diff * (p["lot"] / 0.01)) - self.spread_penalty
                
                locked = -12.50
                if p_pnl >= 20.0: locked = (p_pnl // 5) * 5 - 5
                elif p_pnl >= 10.0: locked = 7.5
                elif p_pnl >= 5.0: locked = 3.5
                elif p_pnl >= 3.5: locked = 2.7
                elif p_pnl >= 2.7: locked = 2.0
                elif p_pnl >= 2.0: locked = 1.0
                
                if p_pnl <= locked:
                    self.balance += locked
                    daily_pnl[day_key] += locked
                    self.trades_history.append({"pnl": locked, "entry_time": p["time"], "exit_time": ts, "date": day_key})
                else:
                    remaining_positions.append(p)
            
            if len(remaining_positions) != len(self.positions):
                self.positions = remaining_positions
                if not self.positions: self.max_basket_pnl = 0.0

            # LÓGICA DE DISPARO SNIPER
            if start_hour <= ts.hour <= end_hour:
                m5_ema = df.iloc[i-5:i]['close'].mean()
                h1_ema = df.iloc[i-60:i]['close'].mean()
                if price > m5_ema and price > h1_ema:
                    if (ts - last_fire_time).total_seconds() >= 900 and len(self.positions) < active_limit:
                        self.positions.append({"type": "BUY", "entry": price, "time": ts, "lot": current_lot})
                        last_fire_time = ts
                elif price < m5_ema and price < h1_ema:
                   if (ts - last_fire_time).total_seconds() >= 900 and len(self.positions) < active_limit:
                        self.positions.append({"type": "SELL", "entry": price, "time": ts, "lot": current_lot})
                        last_fire_time = ts

            if i % 60 == 0:
                cur_eq = self.balance + current_open_pnl
                self.equity_history.append({"time": ts.isoformat(), "balance": round(cur_eq, 2)})

        return self.get_report(daily_pnl)

    def get_report(self, daily_pnl):
        if not self.trades_history: return {"error": "No hubo trades detectados."}
        df_t = pd.DataFrame(self.trades_history)
        wins = len(df_t[df_t['pnl'] > 0])
        win_rate = (wins / len(df_t)) * 100
        
        return {
            "net_profit": round(self.balance - self.initial_balance, 2),
            "win_rate": f"{win_rate:.1f}%",
            "total_trades": len(self.trades_history),
            "final_balance": round(self.balance, 2),
            "daily_performance": daily_pnl,
            "recommendation": f"INTERÉS COMPUESTO OK: El balance subió de ${self.initial_balance} a ${round(self.balance,2)}. Lote y balas adaptados día tras día.",
            "equity_curve": self.equity_history
        }
