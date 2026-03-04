import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init as colorama_init

# --- CONFIGURACIÓN TITAN v47.9.175 (SYNC DASHBOARD) ---
VERSION = "v47.9.175"
BRANDING = "🦅 TITAN ICT: VISION H1 + GATILLO M1"
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
        "lot": 0.01, "sl_usd": 10.0, "trail": True, "burst": 1,
        "h_trigger": 3.0, "h_lock": 0.5, "t_step": 1.0, "air": 2.5,
        "calculate_be": True, "strict_filter": True, "r_trigger": 5.0
    },
    "FX":   {
        "lot": 0.02, "sl_usd": 15.0, "trail": True, "burst": 3,
        "h_trigger": 1.0, "h_lock": 0.3, "t_step": 0.5, "air": 0.7,
        "calculate_be": True, "strict_filter": False, "r_trigger": 3.0
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

def get_ema(symbol, tf, period):
    """Calcula EMA simple para filtro de tendencia."""
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, period + 10)
    if rates is None or len(rates) < period: return 0
    closes = pd.Series([r['close'] for r in rates])
    ema = closes.ewm(span=period, adjust=False).mean()
    return float(ema.iloc[-1])

def get_rsi(symbol, tf, period=14):
    """Calcula RSI para medir fuerza de impulso."""
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, period + 20)
    if rates is None or len(rates) < period: return 50
    delta = pd.Series([r['close'] for r in rates]).diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 0.001) # Evitar división por cero
    return float(100 - (100 / (1 + rs)).iloc[-1])

def get_atr(symbol, tf, period=14):
    """Calcula ATR para medir volatilidad real."""
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, period + 1)
    if rates is None or len(rates) < period: return 1.0
    df = pd.DataFrame(rates)
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift())
    df['l-pc'] = abs(df['low'] - df['close'].shift())
    tr = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

def get_h1_bias(symbol):
    """Radar de Visión H1: Combina EMA y Estructura (High/Low anterior)."""
    ema_bias = get_ema(symbol, mt5.TIMEFRAME_H1, 21)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 1, 1)
    tick = mt5.symbol_info_tick(symbol)
    if not ema_bias or not rates or not tick: return 0
    
    h1_high, h1_low = rates[0]['high'], rates[0]['low']
    
    # Alcista: Precio > EMA y rompiendo/cerca del Alto H1
    if tick.bid > ema_bias and tick.bid > h1_low: return 1
    # Bajista: Precio < EMA y rompiendo/cerca del Bajo H1
    if tick.ask < ema_bias and tick.ask < h1_high: return -1
    return 0

def get_m15_liquidity(sym):
    """Obtiene la liquidez de la vela M15 anterior (más señales)."""
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 1, 1)
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
                "status":"VIGIL", "h1_high":0.0, "h1_low":0.0,
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
                
                # RECARGA DE DATOS PARA EL DASHBOARD
                h_h, h_l = get_m15_liquidity(sym)
                s_d.update({
                    "h1_high": h_h if h_h else 0.0, 
                    "h1_low": h_l if h_l else 0.0,
                    "pos": len(sym_pos), 
                    "pnl": sum(p.profit for p in sym_pos), 
                    "spread": s_i.spread
                })
                
                if (not killzone or on_cooldown) and len(sym_pos) == 0: 
                    s_d["status"] = "COOLDO" if on_cooldown else "FUERA_H"
                    continue

                # --- MODO ICT: VISIÓN H1 + EJECUCIÓN M1 ---
                bias = get_h1_bias(sym)
                status_bias = "BULL" if bias == 1 else "BEAR" if bias == -1 else "NEUTRO"
                
                if bias == 0: 
                    s_d["status"] = "🔎 SCAN: SIN TENDENCIA"
                    continue
                
                s_d["status"] = f"🔎 {status_bias} M1-SCAN"
                
                # Señales en M1 alineadas con H1
                rates_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                if rates_m1 is None or len(rates_m1) < 2: continue
                
                # 1. ¿Hay MSS a favor del Bias?
                m1_mss_buy = (tick.bid > rates_m1[-2]['high']) and bias == 1
                m1_mss_sell = (tick.ask < rates_m1[-2]['low']) and bias == -1
                
                if (m1_mss_buy or m1_mss_sell) and len(sym_pos) == 0:
                    # FILTROS DINÁMICOS
                    trend_ok = True
                    if cfg.get("strict_filter"):
                        ema9 = get_ema(sym, mt5.TIMEFRAME_M1, 9)
                        ema21 = get_ema(sym, mt5.TIMEFRAME_M1, 21)
                        trend_ok = (m1_mss_buy and ema9 > ema21) or (m1_mss_sell and ema9 < ema21)
                    
                    momentum_ok = True
                    if cfg.get("strict_filter"):
                        rsi = get_rsi(sym, mt5.TIMEFRAME_M1, 14)
                        momentum_ok = (m1_mss_buy and rsi > 50) or (m1_mss_sell and rsi < 50)
                    
                    if trend_ok and momentum_ok and (time.time() - s_d["last_trade"] > 3):
                        side = "BUY" if m1_mss_buy else "SELL"
                        points_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                        sl = tick.bid - points_sl if side=="BUY" else tick.ask + points_sl
                        tp = tick.bid + (points_sl * 4) if side=="BUY" else tick.ask - (points_sl * 4) # TP largo para dejar correr
                        
                        for _ in range(cfg['burst']):
                            mt5.order_send({
                                "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                                "sl": float(round(sl, s_i.digits)), "tp": float(round(tp, s_i.digits)),
                                "magic": MAGIC, "comment": "TITAN_H1_M1",
                                "deviation": 100, "type_filling": mt5.ORDER_FILLING_IOC
                            })
                        add_log_dash(f"� {sym} {side} (H1 BIAS OK)")
                        s_d["last_trade"] = time.time()
                
                # ESTATUS DE COMBATE
                if len(sym_pos) == 0:
                    status_bias = "BULL" if bias == 1 else "BEAR"
                    s_d["status"] = f"🔎 {status_bias} M1-SCAN"
                else:
                    current_pnl = sum(p.profit for p in sym_pos)
                    # REFUERZOS SOLO SI ESTÁN EN PROFIT BE
                    all_in_profit = all((p.type == 0 and p.sl > p.price_open) or (p.type == 1 and p.sl < p.price_open and p.sl != 0) for p in sym_pos)
                    
                    if len(sym_pos) < MAX_BULLETS and current_pnl >= cfg["r_trigger"] and all_in_profit:
                         side = "BUY" if sym_pos[0].type == 0 else "SELL"
                         # Solo añadimos DE A UNA bala para mayor seguridad
                         mt5.order_send({
                             "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                             "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                             "sl": sym_pos[0].sl, "tp": sym_pos[0].tp,
                             "magic": MAGIC, "comment": "ICT_REINF",
                             "deviation": 100, "type_filling": mt5.ORDER_FILLING_IOC
                         })
                         add_log_dash(f"🚀 {sym} REFUERZO +1 (SEGURIDAD)")
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
            # Mostrar niveles M15/Precio en el dashboard
            print(f" {sym:<10} | {d['type']:<5} | {d['spread']:<4} | {d['h1_high']:<10.5f} | {d['h1_low']:<10.5f} | {d['pos']}/{MAX_BULLETS:<2} | {pnl_col:<10} | {d['status']}")
        print(f"{Fore.CYAN}{'─'*115}")
        for line in STATE["last_logs"]: print(f" > {line}")
        print(f"{Fore.CYAN}{'═'*115}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
