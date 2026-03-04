import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init as colorama_init

# --- CONFIGURACIÓN TITAN v47.9.340 (MODO ATRACADOR) ---
VERSION = "v47.9.340"
BRANDING = "🦅 TITAN ICT: EJECUCIÓN DIRECTA (TOUCH & GO)"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO
MAX_BULLETS = 2            
MAGIC = 48105              
COOLDOWN_TIME = 900        
MAX_TOTAL_SYMBOLS = 10     
BYPASS_COOLDOWN = True    

# CONFIGURACIÓN POR ACTIVO
ASSET_CONFIG = {
    "GOLD": {
        "lot": 0.01, "lot_reinf": 0.02, "sl_usd": 10.0, "trail": True, 
        "h_trigger": 2.5, "h_lock": 0.5, "t_step": 0.5, "air": 2.0,
        "calculate_be": True, "strict_filter": True, "r_trigger": 3.0
    },
    "FX":   {
        "lot": 0.02, "lot_reinf": 0.02, "sl_usd": 2.0, "trail": True, 
        "h_trigger": 0.3, "h_lock": 0.1, "t_step": 0.2, "air": 0.5,
        "calculate_be": True, "strict_filter": True, "r_trigger": 1.0
    }
}

STATE = {
    "is_running": True, "active_symbols": [], "symbols_data": {}, 
    "last_logs": ["🚀 MOTOR ATRACADOR ACTIVADO - DISPARO AL CONTACTO"],
    "last_heartbeat": 0
}

def add_log_dash(msg):
    STATE["last_logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(STATE["last_logs"]) > 6: STATE["last_logs"].pop(0)

def get_asset_type(sym):
    return "GOLD" if "XAU" in sym.upper() or "GOLD" in sym.upper() else "FX"

def get_h1_liquidity(sym):
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 1, 1)
    if rates is not None and len(rates) > 0:
        return rates[0]['high'], rates[0]['low']
    return None, None

def manage_positions(positions):
    for p in positions:
        s_i = mt5.symbol_info(p.symbol)
        if not s_i: continue
        profit_usd = p.profit + getattr(p, 'commission', 0.0) + getattr(p, 'swap', 0.0)
        cfg = ASSET_CONFIG[get_asset_type(p.symbol)]
        
        if profit_usd <= -(cfg["sl_usd"] + 0.5):
             mt5.Close(p.symbol, ticket=p.ticket)
             add_log_dash(f"💀 {p.symbol} GUILLOTINA (${profit_usd})")
             continue

        is_risky = (p.type == 0 and p.sl < p.price_open) or (p.type == 1 and (p.sl == 0 or p.sl > p.price_open))
        if profit_usd >= cfg["h_trigger"] and is_risky:
             pts = (cfg["h_lock"] / (s_i.trade_tick_value / s_i.point)) / p.volume
             target_sl = p.price_open + pts if p.type == 0 else p.price_open - pts
             mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(target_sl, s_i.digits)), "tp": p.tp})
             add_log_dash(f"✅ {p.symbol} PROTEGIDO")

def init_mt5():
    if not mt5.initialize(): return False
    all_syms = [s.name for s in mt5.symbols_get()]
    for base in BASE_SYMBOLS:
        found = next((s for s in all_syms if base.lower() in s.lower()), None)
        if found:
            mt5.symbol_select(found, True)
            STATE["active_symbols"].append(found)
            STATE["symbols_data"][found] = {
                "status":"VIGIL", "h1_high":0.0, "h1_low":0.0,
                "pnl": 0.0, "pos": 0, "spread": 0, "type": get_asset_type(found), "last_trade": 0
            }
    return len(STATE["active_symbols"]) > 0

def main_loop():
    if not init_mt5(): return
    threading.Thread(target=draw_dashboard, daemon=True).start()
    
    while STATE["is_running"]:
        try:
            if time.time() - STATE["last_heartbeat"] > 20:
                add_log_dash("💓 ESCANEANDO LIQUIDEZ H1...")
                STATE["last_heartbeat"] = time.time()

            pos = mt5.positions_get()
            cur = [p for p in pos if p.magic == MAGIC] if pos else []
            if cur: manage_positions(cur)
            
            for sym in STATE["active_symbols"]:
                s_i = mt5.symbol_info(sym)
                tick = mt5.symbol_info_tick(sym)
                if not s_i or not tick: continue
                s_d = STATE["symbols_data"][sym]
                sym_pos = [p for p in cur if p.symbol == sym]
                cfg = ASSET_CONFIG[s_d["type"]]
                
                h_h, h_l = get_h1_liquidity(sym)
                s_d.update({"h1_high": h_h if h_h else 0.0, "h1_low": h_l if h_l else 0.0, "pos": len(sym_pos), "pnl": sum(p.profit for p in sym_pos), "spread": s_i.spread})
                
                # EJECUCIÓN DIRECTA POR CONTACTO (MODO ATRACADOR)
                if len(sym_pos) == 0 and (time.time() - s_d["last_trade"] > 30):
                    # ¿TOCÓ EL TECHO? -> VENTA DIRECTA
                    if h_h and tick.bid >= (h_h - (2 * s_i.point)):
                        side = "SELL"
                        pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                        sl = tick.ask + pts_sl
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                            "type": 1, "price": tick.bid, "sl": float(round(sl, s_i.digits)), 
                            "magic": MAGIC, "comment": "TOUCH_H1_SELL", "type_filling": mt5.ORDER_FILLING_IOC
                        })
                        add_log_dash(f"🚀 {sym} VENTA POR CONTACTO H1")
                        s_d["last_trade"] = time.time()
                    
                    # ¿TOCÓ EL SUELO? -> COMPRA DIRECTA
                    elif h_l and tick.bid <= (h_l + (2 * s_i.point)):
                        side = "BUY"
                        pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                        sl = tick.bid - pts_sl
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                            "type": 0, "price": tick.ask, "sl": float(round(sl, s_i.digits)), 
                            "magic": MAGIC, "comment": "TOUCH_H1_BUY", "type_filling": mt5.ORDER_FILLING_IOC
                        })
                        add_log_dash(f"🚀 {sym} COMPRA POR CONTACTO H1")
                        s_d["last_trade"] = time.time()
                
                if len(sym_pos) == 0:
                    dist_h = (h_h - tick.bid)/s_i.point if h_h else 999
                    dist_l = (tick.bid - h_l)/s_i.point if h_l else 999
                    label = "H" if dist_h < dist_l else "L"
                    s_d["status"] = f"🔎 SCAN {label} ({min(dist_h, dist_l):.1f} pts)"
                else:
                    # REFUERZOS (BALAS)
                    pnl = sum(p.profit for p in sym_pos)
                    all_be = all((p.type==0 and p.sl >= p.price_open) or (p.type==1 and p.sl <= p.price_open and p.sl != 0) for p in sym_pos)
                    if len(sym_pos) < MAX_BULLETS and pnl >= cfg["r_trigger"] and all_be:
                         side = "BUY" if sym_pos[0].type == 0 else "SELL"
                         mt5.order_send({
                             "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot_reinf"],
                             "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                             "sl": sym_pos[0].sl, "magic": MAGIC, "comment": "REINF_V340", "type_filling": mt5.ORDER_FILLING_IOC
                         })
                         add_log_dash(f"🚀 {sym} REFUERZO {cfg['lot_reinf']}")
                    s_d["status"] = f"🔥 WAR {pnl:+.2f}"

            time.sleep(1)
        except Exception:
            time.sleep(1)

def draw_dashboard():
    while STATE["is_running"]:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Fore.CYAN}{'═'*115}")
        print(f"{Fore.RED}{Style.BRIGHT} 🦅 {BRANDING} | {VERSION} | JEFE: DIEGO (MODO ATRACADOR)")
        print(f"{Fore.CYAN}{'─'*115}")
        print(f"{Fore.WHITE} {'ACTIVO':<10} | {'TIPO':<5} | {'SPR':<4} | {'H1 HIGH':<10} | {'H1 LOW':<10} | {'BALS':<4} | {'PnL' :<10} | {'STATUS'}")
        print(f"{Fore.CYAN}{'─'*115}")
        for sym in STATE["active_symbols"]:
            d = STATE["symbols_data"][sym]
            pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
            print(f" {sym:<10} | {d['type']:<5} | {d['spread']:<4} | {d['h1_high']:<10.5f} | {d['h1_low']:<10.5f} | {d['pos']}/{MAX_BULLETS:<2} | {pnl_col:<10} | {d['status']}")
        print(f"{Fore.CYAN}{'─'*115}")
        for line in STATE["last_logs"]: print(f" > {line}")
        print(f"{Fore.CYAN}{'═'*115}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
