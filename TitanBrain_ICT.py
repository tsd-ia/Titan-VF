import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime
from colorama import Fore, Style, init as colorama_init
import requests

# --- CONFIGURACIÓN TITAN v47.9.600 (RECONSTRUCCIÓN DE HONOR) ---
VERSION = "v47.9.600"
BRANDING = "🦅 TITAN ICT: SNIPER MODE"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO PARA CUENTA BAJA ($23)
MAX_BULLETS = 3            
MAGIC = 48105              

ASSET_CONFIG = {
    "GOLD": {
        "lot": 0.01, 
        "sl_usd": 15.0,     # Protección máxima contra spread
        "trail_trig": 1.5,  
        "trail_lock": 0.5,  # Aseguramos rápido
        "trail_step": 0.5
    },
    "FX": {
        "lot": 0.02, 
        "sl_usd": 3.5,      # Margen de respiración FX
        "trail_trig": 0.4,  # Salida rápida para liquidez
        "trail_lock": 0.1,  
        "trail_step": 0.1   # Cashflow puro céntimo a céntimo
    }
}

STATE = {
    "is_running": True, 
    "active_symbols": [], 
    "symbols_data": {}, 
    "last_logs": ["🎯 MODO SNIPER ACTIVADO v600"],
    "last_heartbeat": 0, 
    "last_tg_monitor": 0, 
    "tracked_positions": {},
    "fired_today": {} # Control de spam de gatillo
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

def individual_trailing(p):
    try:
        s_i = mt5.symbol_info(p.symbol)
        if not s_i: return
        cfg = ASSET_CONFIG[get_asset_type(p.symbol)]
        profit = p.profit + getattr(p, 'commission', 0.0) + getattr(p, 'swap', 0.0)
        
        # SL inicial forzado
        if p.sl == 0:
            pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / p.volume
            new_sl = p.price_open - pts_sl if p.type == 0 else p.price_open + pts_sl
            mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(new_sl, s_i.digits))})
            return

        tick = mt5.symbol_info_tick(p.symbol)
        if not tick: return
        
        # Trailing ultra-rápido para cashflow
        if profit >= cfg["trail_trig"]:
            pts_lock = (cfg["trail_lock"] / (s_i.trade_tick_value / s_i.point)) / p.volume
            pts_step = (cfg["trail_step"] / (s_i.trade_tick_value / s_i.point)) / p.volume
            
            if p.type == 0: # BUY
                target_sl = p.price_open + pts_lock
                trail_sl = tick.bid - pts_step
                new_sl = max(target_sl, trail_sl)
                if new_sl > p.sl + (pts_step * 0.1): # Mueve cada 10 centavos
                    mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(new_sl, s_i.digits))})
            else: # SELL
                target_sl = p.price_open - pts_lock
                trail_sl = tick.ask + pts_step
                new_sl = min(target_sl, trail_sl)
                if p.sl == 0 or new_sl < p.sl - (pts_step * 0.1):
                    mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(new_sl, s_i.digits))})
    except Exception: pass

def get_asset_type(sym):
    return "GOLD" if "XAU" in sym.upper() or "GOLD" in sym.upper() else "FX"

def get_m15_range(sym):
    try:
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 1, 1)
        if rates is not None and len(rates) > 0:
            return float(rates[0]['high']), float(rates[0]['low'])
    except Exception: pass
    return None, None

def main_loop():
    if not mt5.initialize(): return
    threading.Thread(target=draw_dashboard, daemon=True).start()
    
    all_syms = [s.name for s in mt5.symbols_get()]
    for base in BASE_SYMBOLS:
        found = next((s for s in all_syms if base.lower() in s.lower()), None)
        if found:
            mt5.symbol_select(found, True)
            STATE["active_symbols"].append(found)
            STATE["symbols_data"][found] = {"pnl":0, "pos":0, "spread":0, "b_ratio":0, "status":"VIGIL"}

    while STATE["is_running"]:
        try:
            acc = mt5.account_info()
            pos = mt5.positions_get()
            cur = [p for p in pos if p.magic == MAGIC] if pos else []
            
            # Trailing individual
            for p in cur: individual_trailing(p)

            # Monitoreo Telegram
            if time.time() - STATE["last_tg_monitor"] > 120:
                send_telegram(f"⚖️ *EQUITY:* ${acc.equity:.2f} | *PnL:* ${acc.profit:+.2f}")
                STATE["last_tg_monitor"] = time.time()

            for sym in STATE["active_symbols"]:
                s_i = mt5.symbol_info(sym)
                tick = mt5.symbol_info_tick(sym)
                if not s_i or not tick: continue
                s_d = STATE["symbols_data"][sym]
                sym_pos = [p for p in cur if p.symbol == sym]
                s_d.update({"pos": len(sym_pos), "pnl": sum(p.profit for p in sym_pos), "spread": s_i.spread})
                
                mh, ml = get_m15_range(sym)
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 3)
                
                if rates is not None and len(rates) >= 3:
                    lc = rates[-2] # Vela que cerró
                    prev = rates[-3] # Vela anterior
                    
                    c_range = abs(lc['high'] - lc['low'])
                    b_ratio = (abs(lc['close'] - lc['open']) / c_range * 100) if c_range > 0 else 0
                    s_d["b_ratio"] = b_ratio

                    if len(sym_pos) == 0 and mh is not None:
                        # CONDICIÓN SNIPER: Dos velas rompiendo el nivel
                        p_up = (lc['close'] > mh) and (prev['close'] > mh)
                        p_dw = (lc['close'] < ml) and (prev['close'] < ml)
                        s_ok = (b_ratio >= 70)

                        if (p_up or p_dw) and s_ok:
                            side = 0 if p_up else 1
                            price = tick.ask if side == 0 else tick.bid
                            cfg = ASSET_CONFIG[get_asset_type(sym)]
                            
                            # DISPARO ÚNICO Y CONTROLADO
                            add_log_dash(f"🚀 SNIPER DISPARO: {sym} (3B)")
                            send_telegram(f"🎯 *SNIPER {sym}* | Breakout M15 Confirmado.")
                            
                            for _ in range(MAX_BULLETS):
                                mt5.order_send({
                                    "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                    "type": side, "price": price, "magic": MAGIC, "comment": "T_600_SNIPER", "type_filling": mt5.ORDER_FILLING_IOC
                                })
                            time.sleep(1) # Delay para evitar doble disparo por latencia
                        else:
                            if lc['close'] > mh: s_d["status"] = "⏳ ESPERANDO CONFIRMACIÓN (Vela 2)"
                            elif lc['close'] < ml: s_d["status"] = "⏳ ESPERANDO CONFIRMACIÓN (Vela 2)"
                            else: s_d["status"] = f"🔎 SCANNING ICT"
                
                if len(sym_pos) > 0: 
                    s_d["status"] = f"🚀 WAR {len(sym_pos)}B | ${sum(p.profit for p in sym_pos):.2f}"

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
            print(f"{Fore.WHITE} {'ACTIVO':<10} | {'SPR':<4} | {'B%':<5} | {'PnL' :<10} | {'STATUS'}")
            print(f"{Fore.CYAN}{'─'*115}")
            for sym in STATE["active_symbols"]:
                d = STATE["symbols_data"][sym]
                pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
                b_col = Fore.GREEN if d['b_ratio']>=70 else Fore.YELLOW
                print(f" {sym:<10} | {d['spread']:<4} | {b_col}{d['b_ratio']:>4.0f}%{Style.RESET_ALL} | {pnl_col:<10} | {d['status']}")
            print(f"{Fore.CYAN}{'─'*115}")
            for l in STATE["last_logs"]: print(f" > {l}")
            print(f"{Fore.CYAN}{'═'*115}")
        except Exception: pass
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
