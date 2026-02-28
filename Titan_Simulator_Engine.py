import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

class TitanSimulator:
    def __init__(self, symbol="XAUUSDm", initial_balance=200.0, lot=0.01):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.lot = lot
        self.balance = initial_balance
        self.spread_penalty = 0.45 
        self.positions = [] 
        self.trades_history = []
        self.equity_history = []
        
    def get_data(self, days=60):
        if not mt5.initialize(): return None
        utc_to = datetime.now()
        utc_from = utc_to - timedelta(days=days)
        rates = mt5.copy_rates_range(self.symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
        if rates is None: return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Indicadores
        df['rsi'] = self.calculate_rsi(df['close'], 14)
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        std = df['close'].rolling(window=20).std()
        df['bb_h'] = df['ema20'] + (std * 2)
        df['bb_l'] = df['ema20'] - (std * 2)
        df['atr'] = (df['high'] - df['low']).rolling(window=14).mean()
        
        return df

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def run(self, df, start_hour=0, end_hour=23):
        self.balance = self.initial_balance
        self.positions = []
        self.trades_history = []
        self.equity_history = []
        last_fire_time = datetime(2000, 1, 1)
        daily_pnl = {}

        for i in range(50, len(df)):
            row = df.iloc[i]
            ts = row['time']
            price = row['close']
            day_key = ts.strftime('%Y-%m-%d')
            if day_key not in daily_pnl: daily_pnl[day_key] = 0.0

            # --- LÓGICA DE ESCALADO v40.1 ---
            current_open_pnl = 0
            active_bullets = len(self.positions)
            
            # --- INTERÉS COMPUESTO ESTABLE ---
            # No subimos a 0.02 hasta que tengamos $400 (Piso del Jefe)
            lot_multiplier = max(1, int(self.balance / 400))
            base_lot = 0.01 * lot_multiplier
            
            remaining_positions = []
            for p in self.positions:
                diff = (price - p["entry"]) if p["type"] == "BUY" else (p["entry"] - price)
                p_pnl = (diff * (p["lot"] / 0.01)) - self.spread_penalty
                current_open_pnl += p_pnl
                
                if p_pnl >= 15.0 or p_pnl <= -12.5:
                    self.balance += p_pnl
                    daily_pnl[day_key] += p_pnl
                    self.trades_history.append({"pnl": p_pnl, "date": day_key})
                else:
                    remaining_positions.append(p)
            self.positions = remaining_positions

            # --- GATILLO CON BONO ORÁCULO ---
            if start_hour <= ts.hour <= end_hour:
                is_buy = (price < row['bb_l'] and row['rsi'] < 30)
                is_sell = (price > row['bb_h'] and row['rsi'] > 70)
                
                # Oráculo de Binance (Bono x2)
                is_oracle = row['atr'] > (df['atr'].mean() * 2.5)
                
                can_expand = True
                if active_bullets >= 1:
                    if current_open_pnl <= 0.10: can_expand = False
                
                if (is_buy or is_sell) and can_expand and active_bullets < 10:
                    cooldown = (ts - last_fire_time).total_seconds() >= 60
                    if cooldown:
                        side = "BUY" if is_buy else "SELL"
                        # Bono Oráculo sube el lote de esa bala específica
                        final_lot = base_lot * 2 if is_oracle else base_lot
                        if final_lot > 0.05: final_lot = 0.05
                        
                        self.positions.append({"type": side, "entry": price, "time": ts, "lot": final_lot})
                        last_fire_time = ts

            if i % 60 == 0:
                self.equity_history.append({"time": ts.isoformat(), "balance": round(self.balance + current_open_pnl, 2)})

        return self.get_report(daily_pnl)

    def get_report(self, daily_pnl):
        if not self.trades_history: return {"error": "No trades"}
        df_t = pd.DataFrame(self.trades_history)
        wins = len(df_t[df_t['pnl'] > 0])
        win_rate = (wins / len(df_t)) * 100
        return {
            "net_profit": round(self.balance - self.initial_balance, 2),
            "win_rate": f"{win_rate:.1f}%",
            "total_trades": len(self.trades_history),
            "final_balance": round(self.balance, 2),
            "wins": wins,
            "losses": len(df_t) - wins,
            "daily_performance": daily_pnl,
            "equity_curve": self.equity_history
        }
