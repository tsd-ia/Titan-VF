import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime
from colorama import Fore, Style, init as colorama_init
import requests

# --- CONFIGURACIÓN TITAN v47.9.570 (AUDITORÍA Y RE-BLINDAJE) ---
VERSION = "v47.9.570"
BRANDING = "🦅 TITAN ICT: PRECISION BALLISTIC"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO PROFESIONAL
MAX_BULLETS = 3            
MAGIC = 48105              

ASSET_CONFIG = {
    "GOLD": {
        "lot": 0.01, 
        "sl_usd": 4.5,      # $4.5 para que el Spread de $3.6 no lo mate
        "trail_trig": 1.2,  # Gatillo a $1.2
        "trail_lock": 0.8,  # Asegura $0.8
        "trail_step": 0.4
    },
    "FX": {
        "lot": 0.02, 
        "sl_usd": 4.0,      # $4 (~20 pips) para que el precio respire
        "trail_trig": 1.0,  
        "trail_lock": 0.7,  
        "trail_step": 0.3
    }
}

STATE = {
    "is_running": True, 
    "active_symbols": [], 
    "symbols_data": {}, 
    "last_logs": ["🚀 BALÍSTICA BLINDADA - v570"],
    "last_heartbeat": 0, 
    "last_tg_monitor": 0, 
    "tracked_positions": {}
}

# --- TELEGRAM ---
TELEGRAM_TOKEN = '8217691336:AAFWduUGkO_f-QRF6MN338HY-MA46CjzHMg'
TELEGRAM_CHAT_ID = '8339882349'

def send_telegram(msg):
    def _send():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": f"🦅 TITAN {VERSION}\n{msg}", "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=8)
        except Exception: pass
    threading.Thread(target=_send, daemon=True).start()

def add_log_dash(msg):
    STATE["last_logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(STATE["last_logs"]) > 6: STATE["last_logs"].pop(0)

def get_asset_type(sym):
    return "GOLD" if "XAU" in sym.upper() or "GOLD" in sym.upper() else "FX"

def get_m15_range(sym):
    try:
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 1, 1)
        if rates is not None and len(rates) > 0:
            return float(rates[0]['high']), float(rates[0]['low'])
    except Exception: pass
    return None, None

def get_rsi(sym, period=14):
    try:
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, period + 1)
        if rates is None or len(rates) < period: return 50
        deltas = np.diff([r['close'] for r in rates])
        up = deltas[deltas >= 0].sum() / period
        down = -deltas[deltas < 0].sum() / period
        if down == 0: return 100
        rs = up / down
        return 100 - (100 / (1 + rs))
    except Exception: return 50

def get_ema(sym, timeframe, period):
    try:
        rates = mt5.copy_rates_from_pos(sym, timeframe, 0, period + 3)
        if rates is None or len(rates) < period: return None
        closes = np.array([r['close'] for r in rates])
        alpha = 2 / (period + 1)
        ema = closes[0]
        for c in closes[1:]: ema = (c * alpha) + (ema * (1 - alpha))
        return float(ema)
    except Exception: return None

def individual_trailing(p):
    try:
        s_i = mt5.symbol_info(p.symbol)
        if not s_i: return
        cfg = ASSET_CONFIG[get_asset_type(p.symbol)]
        profit = p.profit + getattr(p, 'commission', 0.0) + getattr(p, 'swap', 0.0)
        
        # SL inicial más amplio
        if p.sl == 0:
            pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / p.volume
            new_sl = p.price_open - pts_sl if p.type == 0 else p.price_open + pts_sl
            mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(new_sl, s_i.digits)), "tp": 0.0})
            return

        tick = mt5.symbol_info_tick(p.symbol)
        if not tick: return
        
        if profit >= cfg["trail_trig"]:
            pts_lock = (cfg["trail_lock"] / (s_i.trade_tick_value / s_i.point)) / p.volume
            pts_step = (cfg["trail_step"] / (s_i.trade_tick_value / s_i.point)) / p.volume
            
            if p.type == 0: # BUY
                target_sl = p.price_open + pts_lock
                trail_sl = tick.bid - pts_step
                new_sl = max(target_sl, trail_sl)
                if new_sl > p.sl + (pts_step * 0.2):
                    mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(new_sl, s_i.digits))})
            else: # SELL
                target_sl = p.price_open - pts_lock
                trail_sl = tick.ask + pts_step
                new_sl = min(target_sl, trail_sl)
                if p.sl == 0 or new_sl < p.sl - (pts_step * 0.2):
                    mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(new_sl, s_i.digits))})
    except Exception: pass

def main_loop():
    if not mt5.initialize(): return
    threading.Thread(target=draw_dashboard, daemon=True).start()
    
    all_syms = [s.name for s in mt5.symbols_get()]
    for base in BASE_SYMBOLS:
        found = next((s for s in all_syms if base.lower() in s.lower()), None)
        if found:
            mt5.symbol_select(found, True)
            STATE["active_symbols"].append(found)
            STATE["symbols_data"][found] = {"pnl":0, "pos":0, "spread":0, "b_ratio":0, "ema_trend":"WAIT", "status":"VIGIL", "rsi": 50}

    while STATE["is_running"]:
        try:
            acc = mt5.account_info()
            pos = mt5.positions_get()
            cur = [p for p in pos if p.magic == MAGIC] if pos else []
            
            # TRACK CIERRES
            current_tickets = {p.ticket: p for p in cur}
            for t_id, p_old in list(STATE["tracked_positions"].items()):
                if t_id not in current_tickets:
                    send_telegram(f"🏁 CIERRE {p_old.symbol} | PnL: ${p_old.profit:+.2f}")
                    add_log_dash(f"🏁 CIERRE {p_old.symbol}")
                    del STATE["tracked_positions"][t_id]
            for p in cur: STATE["tracked_positions"][p.ticket] = p

            for p in cur: individual_trailing(p)
            
            if time.time() - STATE["last_tg_monitor"] > 60:
                send_telegram(f"📡 *ESTADO v570*\nEquity: ${acc.equity:.2f}\nMargen: {acc.margin_level:.0f}%")
                STATE["last_tg_monitor"] = time.time()

            for sym in STATE["active_symbols"]:
                s_i = mt5.symbol_info(sym)
                tick = mt5.symbol_info_tick(sym)
                if not s_i or not tick: continue
                s_d = STATE["symbols_data"][sym]
                sym_pos = [p for p in cur if p.symbol == sym]
                cfg = ASSET_CONFIG[get_asset_type(sym)]
                s_d.update({"pos": len(sym_pos), "pnl": sum(p.profit for p in sym_pos), "spread": s_i.spread})
                
                mh, ml = get_m15_range(sym)
                e21 = get_ema(sym, mt5.TIMEFRAME_M1, 21)
                e50 = get_ema(sym, mt5.TIMEFRAME_M1, 50)
                rsi = get_rsi(sym)
                s_d["rsi"] = rsi
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                
                if rates is not None and len(rates) >= 2:
                    lc = rates[-2]
                    c_range = abs(lc['high'] - lc['low'])
                    b_ratio = (abs(lc['close'] - lc['open']) / c_range * 100) if c_range > 0 else 0
                    s_d["b_ratio"] = b_ratio
                    s_d["ema_trend"] = "UP" if (e21 and e50 and e21 > e50) else "DOWN"

                    if len(sym_pos) == 0 and mh is not None:
                        p_up = (lc['close'] > mh)
                        p_dw = (lc['close'] < ml)
                        s_ok = (b_ratio >= 70)
                        t_ok = (s_d["ema_trend"] == "UP" if p_up else (s_d["ema_trend"] == "DOWN" if p_dw else False))
                        
                        # FILTRO RSI ANTI-TRAMPA
                        rsi_ok = (rsi < 80 if p_up else (rsi > 20 if p_dw else True))

                        if (p_up or p_dw) and s_ok and t_ok and rsi_ok:
                            side = 0 if p_up else 1
                            price = tick.ask if side == 0 else tick.bid
                            add_log_dash(f"🚀 FUEGO: {sym} (3 BALAS)")
                            send_telegram(f"🔥 *RAFAGA TITAN: {sym}*")
                            for _ in range(MAX_BULLETS):
                                mt5.order_send({
                                    "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                    "type": side, "price": price, "magic": MAGIC, "comment": "T_570", "type_filling": mt5.ORDER_FILLING_IOC
                                })
                        else:
                            if p_up or p_dw:
                                rsi_msg = f"RSI:{rsi:.0f}(OK)" if rsi_ok else f"RSI:{rsi:.0f}(OVER)"
                                s_d["status"] = f"⏳ GAT: {'B:OK' if s_ok else 'B:WAIT'} | {rsi_msg}"
                            else:
                                s_d["status"] = f"🔎 SCANNING ICT"
                
                if len(sym_pos) > 0: 
                    pnl_tot = sum(p.profit for p in sym_pos)
                    s_d["status"] = f"🚀 WAR {len(sym_pos)}B | ${pnl_tot:.2f}"

            time.sleep(1)
        except Exception:
            time.sleep(1)

def draw_dashboard():
    while STATE["is_running"]:
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
            acc = mt5.account_info()
            if not acc: continue
            print(f"{Fore.CYAN}{'═'*115}")
            print(f"{Fore.RED}{Style.BRIGHT} 🦅 {BRANDING} | {VERSION} | JEFE: DIEGO")
            print(f"{Fore.WHITE} BALANCE: ${Fore.GREEN}{acc.balance:.2f} {Fore.WHITE}| EQUITY: ${Fore.CYAN}{acc.equity:.2f} {Fore.WHITE}| MARGEN: {Fore.YELLOW}{acc.margin_level:.1f}%")
            print(f"{Fore.CYAN}{'─'*115}")
            print(f"{Fore.WHITE} {'ACTIVO':<10} | {'SPR':<4} | {'B%':<5} | {'RSI':<5} | {'EMA':<6} | {'PnL' :<10} | {'STATUS'}")
            print(f"{Fore.CYAN}{'─'*115}")
            for sym in STATE["active_symbols"]:
                d = STATE["symbols_data"][sym]
                pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
                b_col = Fore.GREEN if d['b_ratio']>=70 else Fore.YELLOW
                r_col = Fore.RED if (d['rsi']>80 or d['rsi']<20) else Fore.CYAN
                print(f" {sym:<10} | {d['spread']:<4} | {b_col}{d['b_ratio']:>4.0f}%{Style.RESET_ALL} | {r_col}{d['rsi']:>4.0f}{Style.RESET_ALL} | {d['ema_trend']:<6} | {pnl_col:<10} | {d['status']}")
            print(f"{Fore.CYAN}{'─'*115}")
            for l in STATE["last_logs"]: print(f" > {l}")
            print(f"{Fore.CYAN}{'═'*115}")
        except Exception: pass
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
