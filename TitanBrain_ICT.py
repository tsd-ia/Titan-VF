import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init as colorama_init

# --- CONFIGURACIÓN TITAN v47.9.127 (ANTI-SPREAD) ---
VERSION = "v47.9.127"
BRANDING = "🦅 TITAN ICT: ESCUDO ANTI-SPREAD"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO
HARVEST_TRIGGER = 2.5      # Gatillo de Cosecha Agresiva
HARVEST_LOCK = 1.0         # Bloquear $1.00
TRAILING_STEP = 2.0        # Mover SL cada $2.00 extra (Más aire)
RR_RATIO = 1.0             # Ratio para Profit de $25 (con SL de 2500 pts)
MAX_BULLETS = 6            # Límite STORM
MAGIC = 48105              # Magic v47.105
COOLDOWN_TIME = 1800       # 30 minutos
REINFORCE_PROFIT = 3.0     # Profit para buscar refuerzos (agrupado)
BYPASS_COOLDOWN = True    # <--- DÉLO EN TRUE PARA SALTAR EL BLOQUEO AHORA

# CONFIGURACIÓN POR ACTIVO
ASSET_CONFIG = {
    "GOLD": {
        "lot": 0.01, "sl_usd": 25.0, "trail": True, "burst": 2,
        "h_trigger": 5.0, "h_lock": 1.5, "t_step": 1.0, "air": 1.5
    },
    "FX":   {
        "lot": 0.02, "sl_usd": 25.0, "trail": True, "burst": 3,
        "h_trigger": 1.5, "h_lock": 0.4, "t_step": 0.5, "air": 0.7
    }
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
    # Desbloqueado 24h por solicitud del Comandante
    return True

def get_asset_type(sym):
    return "GOLD" if "XAU" in sym.upper() or "GOLD" in sym.upper() else "FX"

def check_cooldown():
    """Detecta pérdidas recientes y activa el bloqueo de 30 minutos."""
    if BYPASS_COOLDOWN: return False
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
        
        # Lectura segura de Profit (Evita el error de 'commission' que colgó el bot)
        profit_usd = p.profit + getattr(p, 'commission', 0.0) + getattr(p, 'swap', 0.0)
        cfg = ASSET_CONFIG[get_asset_type(p.symbol)]
        
        # Detectar si el SL actual está en zona de riesgo (pérdida)
        is_risky = (p.type == 0 and p.sl < p.price_open) or (p.type == 1 and (p.sl == 0 or p.sl > p.price_open))
        
        # 1. COSECHA INICIAL (Mover SL a terreno positivo una vez superado el trigger)
        if profit_usd >= cfg["h_trigger"] and is_risky:
             # Calcular precio necesario para el lock inicial
             points_needed = (cfg["h_lock"] / (s_i.trade_tick_value / s_i.point)) / p.volume
             target_sl = p.price_open + points_needed if p.type == 0 else p.price_open - points_needed
             mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(target_sl, s_i.digits)), "tp": p.tp})
             add_log_dash(f"💰 {p.symbol} BE PROTEGIDO ${cfg['h_lock']}")
        
        # 2. TRAILING STOP DINÁMICO (Solo si ya estamos en profit lock)
        elif profit_usd >= (cfg["h_trigger"] + cfg["t_step"]) and not is_risky:
             current_sl_profit = (p.sl - p.price_open) * (s_i.trade_tick_value / s_i.point) * p.volume if p.type==0 else (p.price_open - p.sl) * (s_i.trade_tick_value / s_i.point) * p.volume
             if profit_usd - current_sl_profit > cfg["t_step"]:
                 new_lock = profit_usd - cfg["air"] 
                 points_new = (new_lock / (s_i.trade_tick_value / s_i.point)) / p.volume
                 new_sl = p.price_open + points_new if p.type == 0 else p.price_open - points_new
                 
                 is_better = (p.type==0 and new_sl > p.sl) or (p.type==1 and new_sl < p.sl)
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
                "status":"VIGIL", "h1_high":0, "h1_low":0, "m1_h":0, "m1_l":0,
                "pnl": 0.0, "pos": 0, "spread": 0, "sweep": False, 
                "last_trade": 0, "last_reinf": 0, "type": get_asset_type(found)
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

                # --- MODO ICT REAL (SWEEP H1 + MSS M1) ---
                h_high, h_low = get_h1_liquidity(sym)
                if h_high is None: continue
                s_d.update({"h1_high": h_high, "h1_low": h_low})
                
                sweep_buy = tick.ask < h_low
                sweep_sell = tick.bid > h_high
                
                if (sweep_buy or sweep_sell) and len(sym_pos) == 0:
                    # VALIDACIÓN MSS (Ruptura de vela M1 anterior en dirección opuesta)
                    rates_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                    if rates_m1 is None or len(rates_m1) < 2: continue
                    
                    mss_ok = False
                    if sweep_buy and tick.bid > rates_m1[-2]['high']: mss_ok = True
                    elif sweep_sell and tick.ask < rates_m1[-2]['low']: mss_ok = True
                    
                    if mss_ok and (time.time() - s_d["last_trade"] > 3):
                        side = "BUY" if sweep_buy else "SELL"
                        points_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                        sl = tick.bid - points_sl if side=="BUY" else tick.ask + points_sl
                        tp = tick.bid + (points_sl * 2) if side=="BUY" else tick.ask - (points_sl * 2)
                        
                        for _ in range(cfg['burst']):
                            mt5.order_send({
                                "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                                "sl": float(round(sl, s_i.digits)), "tp": float(round(tp, s_i.digits)),
                                "magic": MAGIC, "comment": "ICT_VANG",
                                "deviation": 100, "type_filling": mt5.ORDER_FILLING_IOC
                            })
                        add_log_dash(f"� {sym} {side} ICT MSS SOLTADO")
                        s_d["last_trade"] = time.time()
                
                # ESTATUS DE COMBATE
                if len(sym_pos) == 0:
                    s_d["status"] = f"🔎 SCAN ICT: {h_low:.5f}-{h_high:.5f}"
                else:
                    current_pnl = sum(p.profit for p in sym_pos)
                    # REFUERZOS SOLO SI ESTÁN EN PROFIT BE
                    all_in_profit = all((p.type == 0 and p.sl > p.price_open) or (p.type == 1 and p.sl < p.price_open and p.sl != 0) for p in sym_pos)
                    
                    if len(sym_pos) < MAX_BULLETS and current_pnl >= REINFORCE_PROFIT and all_in_profit:
                         side = "BUY" if sym_pos[0].type == 0 else "SELL"
                         for _ in range(2):
                             mt5.order_send({
                                 "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                 "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                                 "sl": sym_pos[0].sl, "tp": sym_pos[0].tp,
                                 "magic": MAGIC, "comment": "ICT_REINF",
                                 "deviation": 100, "type_filling": mt5.ORDER_FILLING_IOC
                             })
                         add_log_dash(f"🚀 {sym} REFUERZOS +2 (PNL ${current_pnl:.2f})")
                         s_d["last_reinf"] = time.time()
                    
                    s_d["status"] = f"⚔️ WAR: {current_pnl:+.2f} | REINF: {'OK' if all_in_profit else 'WAIT BE'}"

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
            # Mostrar niveles M1 en el dashboard si no hay posición
            print(f" {sym:<10} | {d['type']:<5} | {d['spread']:<4} | {d['m1_high'] if 'm1_high' in d else d['h1_high']:<10.5f} | {d['m1_low'] if 'm1_low' in d else d['h1_low']:<10.5f} | {d['pos']}/{MAX_BULLETS:<2} | {pnl_col:<10} | {d['status']}")
        print(f"{Fore.CYAN}{'─'*115}")
        for line in STATE["last_logs"]: print(f" > {line}")
        print(f"{Fore.CYAN}{'═'*115}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
