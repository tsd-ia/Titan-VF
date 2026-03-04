import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init as colorama_init

# --- CONFIGURACIÓN TITAN v47.9.350 (MODO FÉNIX - ESPEJO) ---
VERSION = "v47.9.350"
BRANDING = "🦅 TITAN ICT: ESTRATEGIA ESPEJO (BREAKOUT)"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO (CONTROL DE DAÑOS)
MAX_BULLETS = 1            # Solo 1 bala para recuperar con calma
MAGIC = 48105              
COOLDOWN_TIME = 1800       # 30 Minutos de enfriamiento tras pérdida
MAX_TOTAL_SYMBOLS = 3      # Reducido de 10 a 3 para no saturar
BYPASS_COOLDOWN = False    # Volvemos a activar la seguridad

ASSET_CONFIG = {
    "GOLD": {
        "lot": 0.01, "sl_usd": 10.0, "trail": True, 
        "h_trigger": 2.5, "h_lock": 0.5, "t_step": 0.5, "air": 2.0,
        "calculate_be": True, "r_trigger": 3.0
    },
    "FX":   {
        "lot": 0.02, "sl_usd": 2.0, "trail": True, 
        "h_trigger": 0.3, "h_lock": 0.1, "t_step": 0.2, "air": 0.5,
        "calculate_be": True, "r_trigger": 1.0
    }
}

STATE = {
    "is_running": True, "active_symbols": [], "symbols_data": {}, 
    "last_logs": ["� MODO RECUPERACIÓN ACTIVADO - ESTRATEGIA ESPEJO"],
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
        
        # LA GUILLOTINA: PROTECCIÓN TOTAL
        if profit_usd <= -(cfg["sl_usd"]):
             mt5.Close(p.symbol, ticket=p.ticket)
             add_log_dash(f"💀 EMERGENCY CLOSE {p.symbol} (${profit_usd})")
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
                "status":"VIGIL", "pnl": 0.0, "pos": 0, "spread": 0, "type": get_asset_type(found), "last_trade": 0
            }
    return len(STATE["active_symbols"]) > 0

def main_loop():
    if not init_mt5(): return
    threading.Thread(target=draw_dashboard, daemon=True).start()
    
    while STATE["is_running"]:
        try:
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
                s_d.update({"pos": len(sym_pos), "pnl": sum(p.profit for p in sym_pos), "spread": s_i.spread})
                
                # ESTRATEGIA ESPEJO (BREAKOUT TREND)
                if len(sym_pos) == 0 and len(cur) < MAX_TOTAL_SYMBOLS:
                    # ¿ROMPIÓ TECHO? -> COMPRAMOS (TENDENCIA)
                    if h_h and tick.bid >= h_h:
                        pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                        sl = tick.bid - pts_sl
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                            "type": 0, "price": tick.ask, "sl": float(round(sl, s_i.digits)), 
                            "magic": MAGIC, "comment": "FENIX_BREAK_UP", "type_filling": mt5.ORDER_FILLING_IOC
                        })
                        add_log_dash(f"� {sym} COMPRA (ROMPIÓ TECHO)")
                        s_d["last_trade"] = time.time()
                    
                    # ¿ROMPIÓ SUELO? -> VENDEMOS (TENDENCIA)
                    elif h_l and tick.bid <= h_l:
                        pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                        sl = tick.bid + pts_sl
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                            "type": 1, "price": tick.bid, "sl": float(round(sl, s_i.digits)), 
                            "magic": MAGIC, "comment": "FENIX_BREAK_DOWN", "type_filling": mt5.ORDER_FILLING_IOC
                        })
                        add_log_dash(f"� {sym} VENTA (ROMPIÓ SUELO)")
                        s_d["last_trade"] = time.time()
                
                if len(sym_pos) == 0:
                    dist_h = (h_h - tick.bid)/s_i.point if h_h else 999
                    dist_l = (tick.bid - h_l)/s_i.point if h_l else 999
                    s_d["status"] = f"🔎 {('H' if dist_h < dist_l else 'L')} {min(dist_h, dist_l):.1f}"
                else:
                    s_d["status"] = f"🚀 TRENDING {sum(p.profit for p in sym_pos):.2f}"

            time.sleep(1)
        except Exception:
            time.sleep(1)

def draw_dashboard():
    while STATE["is_running"]:
        os.system('cls' if os.name == 'nt' else 'clear')
        acc = mt5.account_info()
        if not acc: continue
        print(f"{Fore.CYAN}{'═'*115}")
        print(f"{Fore.YELLOW}{Style.BRIGHT} 🔥 {BRANDING} | {VERSION} | JEFE: DIEGO (MODO RECUPERACIÓN)")
        print(f"{Fore.WHITE} BALANCE: ${Fore.GREEN}{acc.balance:.2f} {Fore.WHITE}| EQUITY: ${Fore.CYAN}{acc.equity:.2f} {Fore.WHITE}| PnL: {Fore.YELLOW}${acc.profit:.2f}")
        print(f"{Fore.CYAN}{'─'*115}")
        print(f"{Fore.WHITE} {'ACTIVO':<10} | {'SPR':<4} | {'H1 HIGH':<10} | {'H1 LOW':<10} | {'POS':<4} | {'PnL' :<10} | {'STATUS'}")
        print(f"{Fore.CYAN}{'─'*115}")
        for sym in STATE["active_symbols"]:
            d = STATE["symbols_data"][sym]
            pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
            h1h, h1l = get_h1_liquidity(sym)
            print(f" {sym:<10} | {d['spread']:<4} | {h1h if h1h else 0:<10.5f} | {h1l if h1l else 0:<10.5f} | {d['pos']}/1  | {pnl_col:<10} | {d['status']}")
        print(f"{Fore.CYAN}{'─'*115}")
        for line in STATE["last_logs"]: print(f" > {line}")
        print(f"{Fore.CYAN}{'═'*115}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
