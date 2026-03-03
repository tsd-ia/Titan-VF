import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init as colorama_init

# --- CONFIGURACIÓN TITAN v47.9.99 (ANTIVENGANZA) ---
VERSION = "v47.9.99"
BRANDING = "🦅 TITAN ICT: BOZAL MECÁNICO (ANTIVENGANZA)"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO
HARVEST_TRIGGER = 2.5      # Gatillo de Cosecha Agresiva
HARVEST_LOCK = 1.0         # Bloquear $1.00
TRAILING_STEP = 0.2        # Mover SL cada $0.20 extra
RR_RATIO = 1.0             # Ratio para Profit de $25 (con SL de 2500 pts)
MAX_BULLETS = 6            # Límite STORM
MAGIC = 47990              # Magic v47.9.99
COOLDOWN_TIME = 1800       # 30 minutos en segundos

# CONFIGURACIÓN POR ACTIVO
ASSET_CONFIG = {
    "GOLD": {"lot": 0.01, "sl_points": 2500, "trail": True, "burst": 2}, # SL $25 (Sniper-Shield)
    "FX":   {"lot": 0.02, "sl_points": 1250, "trail": True, "burst": 3}  # SL $25 (Sniper-Shield)
}

STATE = {
    "is_running": True, "active_symbols": [], "symbols_data": {}, 
    "last_logs": ["Antivenganza Mode Active... Protocol 30m Load"],
    "cooldown_until": 0
}

def add_log_dash(msg):
    STATE["last_logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(STATE["last_logs"]) > 6: STATE["last_logs"].pop(0)

def is_killzone():
    tz_chile = pytz.timezone('America/Santiago')
    now = datetime.now(tz_chile)
    h, m = now.hour, now.minute
    londres = (4 <= h < 8)
    ny = (9 <= h < 13) and (h > 9 or m >= 30)
    return londres or ny

def get_asset_type(sym):
    return "GOLD" if "XAU" in sym.upper() or "GOLD" in sym.upper() else "FX"

def check_cooldown():
    """Detecta pérdidas recientes y activa el bloqueo de 30 minutos."""
    if time.time() < STATE["cooldown_until"]: return True
    
    # Revisar historial de la última hora
    to_time = datetime.now()
    from_time = to_time - timedelta(hours=1)
    history = mt5.history_deals_get(from_time, to_time)
    
    if history:
        for deal in reversed(history):
            if deal.magic == MAGIC and (deal.entry == 1): # Es un cierre
                if deal.profit < 0:
                    loss_time = deal.time
                    if time.time() - loss_time < COOLDOWN_TIME:
                        STATE["cooldown_until"] = loss_time + COOLDOWN_TIME
                        add_log_dash(f"🛡️ BOZAL ACTIVADO: Bloqueo de 30 min por SL")
                        return True
                break # Solo evaluamos el último cierre del magic
    return False

def get_h1_liquidity(sym):
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 1, 1)
    if rates is not None and len(rates) > 0:
        return rates[0]['high'], rates[0]['low']
    return None, None

def manage_positions(positions):
    """Cosecha 1.50 -> 0.50 + Trailing Stop por USD"""
    for p in positions:
        if p.magic != MAGIC: continue
        s_i = mt5.symbol_info(p.symbol)
        tick = mt5.symbol_info_tick(p.symbol)
        if not s_i or not tick: continue
        
        profit_usd = p.profit + p.commission + p.swap
        cfg = ASSET_CONFIG[get_asset_type(p.symbol)]
        
        # 1. COSECHA INICIAL (1.50 -> 0.50)
        if profit_usd >= HARVEST_TRIGGER and p.sl == 0:
             # Calcular precio necesario para ganar $0.50
             points_needed = (HARVEST_LOCK / (s_i.trade_tick_value / s_i.point)) / p.volume
             target_sl = p.price_open + points_needed if p.type == 0 else p.price_open - points_needed
             mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(target_sl, s_i.digits)), "tp": p.tp})
             add_log_dash(f"💰 {p.symbol} COSECHA $0.50 LOCK")
        
        # 2. TRAILING STOP (Después de la cosecha)
        elif profit_usd >= (HARVEST_TRIGGER + TRAILING_STEP) and cfg["trail"]:
             # Mover SL dinámico para seguir el precio con respiro
             current_sl_profit = (p.sl - p.price_open) * (s_i.trade_tick_value / s_i.point) * p.volume if p.type==0 else (p.price_open - p.sl) * (s_i.trade_tick_value / s_i.point) * p.volume
             if profit_usd - current_sl_profit > (HARVEST_LOCK + TRAILING_STEP):
                 new_lock = profit_usd - 0.70 # Dejamos $0.70 de respiro prudente
                 points_new = (new_lock / (s_i.trade_tick_value / s_i.point)) / p.volume
                 new_sl = p.price_open + points_new if p.type == 0 else p.price_open - points_new
                 
                 is_better = (p.type==0 and new_sl > p.sl) or (p.type==1 and (p.sl==0 or new_sl < p.sl))
                 if is_better:
                     mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(new_sl, s_i.digits)), "tp": p.tp})

def init_mt5():
    if not mt5.initialize(): return False
    all_syms = [s.name for s in mt5.symbols_get()]
    for base in BASE_SYMBOLS:
        found = next((s for s in all_syms if base.lower() in s.lower()), None)
        if found:
            mt5.symbol_select(found, True)
            STATE["active_symbols"].append(found)
            STATE["symbols_data"][found] = {
                "status":"VIGIL", "h1_high":0, "h1_low":0, "pnl": 0.0, "pos": 0, "spread": 0,
                "sweep": False, "last_trade": 0, "type": get_asset_type(found)
            }
    return len(STATE["active_symbols"]) > 0

def main_loop(mode_24h=False):
    if not init_mt5(): return
    threading.Thread(target=draw_dashboard, daemon=True).start()
    
    while STATE["is_running"]:
        try:
            acc = mt5.account_info()
            pos = mt5.positions_get()
            cur = [p for p in pos if p.magic == MAGIC] if pos else []
            if cur: manage_positions(cur)
            
            killzone = is_killzone() or mode_24h
            on_cooldown = check_cooldown()
            
            for sym in STATE["active_symbols"]:
                s_i = mt5.symbol_info(sym)
                tick = mt5.symbol_info_tick(sym)
                if not s_i or not tick: continue
                s_d = STATE["symbols_data"][sym]
                sym_pos = [p for p in cur if p.symbol == sym]
                asset_type = s_d["type"]
                cfg = ASSET_CONFIG[asset_type]
                
                h_high, h_low = get_h1_liquidity(sym)
                s_d.update({"h1_high": h_high, "h1_low": h_low, "pos": len(sym_pos), "pnl": sum(p.profit for p in sym_pos), "spread": s_i.spread})
                
                if (not killzone or on_cooldown) and len(sym_pos) == 0: 
                    s_d["status"] = "COOLDOWN" if on_cooldown else "OUT_CLOCK"
                    continue

                # --- MODO METRALLETA ICT (CON MSS ADELANTADO) ---
                sweep_buy = tick.ask < s_d["h1_low"]
                sweep_sell = tick.bid > s_d["h1_high"]
                
                if sweep_buy or sweep_sell:
                    s_d["status"] = f"🎯 SWEEPING_{asset_type}"
                    
                    # VALIDACIÓN DE MSS (Giro del Cuchillo en M1)
                    rates_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                    mss_ok = False
                    if rates_m1 is not None and len(rates_m1) >= 2:
                        if sweep_buy and tick.bid > rates_m1[-2]['high']: mss_ok = True
                        elif sweep_sell and tick.ask < rates_m1[-2]['low']: mss_ok = True
                    
                    # Disparo si hay giro (MSS) y no superamos balas
                    if mss_ok and len(sym_pos) < MAX_BULLETS and (time.time() - s_d["last_trade"] > 3):
                        side = "BUY" if sweep_buy else "SELL"
                        sl_pts = cfg["sl_points"] * s_i.point
                        
                        sl = tick.bid - sl_pts if side=="BUY" else tick.ask + sl_pts
                        # Ajuste de TP Dinámico (Más corto en FX)
                        tp_pts = sl_pts * (1.5 if asset_type=="FX" else RR_RATIO)
                        tp = tick.bid + tp_pts if side=="BUY" else tick.ask - tp_pts
                        
                        for _ in range(cfg['burst']):
                            res = mt5.order_send({
                                "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                                "sl": float(round(sl, s_i.digits)), "tp": float(round(tp, s_i.digits)),
                                "magic": MAGIC, "comment": f"TITAN_{asset_type}_MET",
                                "deviation": 100, "type_filling": mt5.ORDER_FILLING_IOC
                            })
                            if res.retcode == mt5.TRADE_RETCODE_DONE: 
                                add_log_dash(f"🔫 {sym} {side} ráfaga x{cfg['burst']} | {asset_type} | MSS OK")
                                s_d["last_trade"] = time.time()
                else:
                    s_d["status"] = "HUNTER" if len(sym_pos) == 0 else "WAR"

            time.sleep(0.5) 
        except Exception as e:
            time.sleep(1)

def draw_dashboard():
    while STATE["is_running"]:
        os.system('cls' if os.name == 'nt' else 'clear')
        acc = mt5.account_info()
        if not acc: continue
        print(f"{Fore.CYAN}{'═'*115}")
        print(f"{Fore.GREEN}{Style.BRIGHT} 🦅 {BRANDING} | {VERSION} | MOD: {'24H' if False else 'KZ'}")
        print(f"{Fore.WHITE} BALANCE: ${Fore.GREEN}{acc.balance:.2f} {Fore.WHITE}| EQUITY: ${Fore.CYAN}{acc.equity:.2f} {Fore.WHITE}| PnL: {Fore.YELLOW}${acc.profit:.2f}")
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
