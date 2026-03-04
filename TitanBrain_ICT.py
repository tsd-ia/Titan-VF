import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime
from colorama import Fore, Style, init as colorama_init
import requests

# --- CONFIGURACIÓN TITAN v47.9.540 (ARRANQUE GARANTIZADO) ---
VERSION = "v47.9.540"
BRANDING = "🦅 TITAN ICT: GATILLO REPARADO"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO
MAX_BULLETS = 6            
MAGIC = 48105              
MAX_TOTAL_SYMBOLS = 10     

ASSET_CONFIG = {
    "GOLD": {
        "lot": 0.01, "lot_reinf": 0.01, "sl_usd": 10.0, "trail": True, 
        "h_trigger": 2.5, "h_lock": 1.5, "t_step": 0.5, "air": 2.0,
        "calculate_be": True, "r_trigger": 2.5
    },
    "FX":   {
        "lot": 0.02, "lot_reinf": 0.02, "sl_usd": 2.0, "trail": True, 
        "h_trigger": 0.3, "h_lock": 0.1, "t_step": 0.2, "air": 0.5,
        "calculate_be": True, "r_trigger": 0.6
    }
}

STATE = {
    "is_running": True, "active_symbols": [], "symbols_data": {}, 
    "last_logs": ["🚀 MOTOR REINICIADO v540"],
    "last_heartbeat": 0, "last_tg_monitor": 0, "tracked_positions": {}
}

# CONFIGURACIÓN TELEGRAM
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

def manage_positions(positions):
    sym_groups = {}
    for p in positions:
        if p.symbol not in sym_groups: sym_groups[p.symbol] = []
        sym_groups[p.symbol].append(p)

    for sym, pos_list in sym_groups.items():
        try:
            s_i = mt5.symbol_info(sym)
            if not s_i: continue
            cfg = ASSET_CONFIG[get_asset_type(sym)]
            
            pnl = sum(p.profit + getattr(p, 'commission', 0.0) + getattr(p, 'swap', 0.0) for p in pos_list)
            
            if pnl <= -(cfg["sl_usd"] + 1.0):
                for p in pos_list: mt5.Close(sym, ticket=p.ticket)
                add_log_dash(f"💀 EXIT CLUSTER {sym}")
                send_telegram(f"💀 *CLUSTER CERRADO:* {sym} (-${abs(pnl):.1f})")
                continue
                
            first = sorted(pos_list, key=lambda x: x.ticket)[0]
            is_p = (first.type == 0 and first.sl >= first.price_open) or (first.type == 1 and first.sl <= first.price_open and first.sl != 0)
            
            if pnl >= cfg["h_trigger"] and not is_p:
                pts = (cfg["h_lock"] / (s_i.trade_tick_value / s_i.point)) / (0.01 * len(pos_list))
                tsl = first.price_open + pts if first.type == 0 else first.price_open - pts
                fsl = float(round(tsl, s_i.digits))
                for p in pos_list:
                    mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": fsl, "tp": p.tp})
                add_log_dash(f"🛡️ PROTEGIDO {sym}")
                send_telegram(f"🛡️ *{sym}: PROTEGIDO (BE)*")
        except Exception: pass

def init_mt5():
    if not mt5.initialize(): return False
    acc = mt5.account_info()
    if acc:
        send_telegram(f"📢 *SISTEMA ONLINE v540*\nBalance: ${acc.balance:.2f}\nGatillos listos.")
    
    all_syms = [s.name for s in mt5.symbols_get()]
    for base in BASE_SYMBOLS:
        found = next((s for s in all_syms if base.lower() in s.lower()), None)
        if found:
            mt5.symbol_select(found, True)
            STATE["active_symbols"].append(found)
            STATE["symbols_data"][found] = {
                "status":"VIGIL", "pnl": 0.0, "pos": 0, "spread": 0, "type": get_asset_type(found),
                "b_ratio": 0, "ema_trend": "WAIT"
            }
    return len(STATE["active_symbols"]) > 0

def main_loop():
    if not init_mt5(): return
    threading.Thread(target=draw_dashboard, daemon=True).start()
    
    while STATE["is_running"]:
        try:
            acc = mt5.account_info()
            pos = mt5.positions_get()
            cur = [p for p in pos if p.magic == MAGIC] if pos else []
            
            # TRACK CIERRES
            current_t = {p.ticket: p for p in cur}
            for t_id, p_old in list(STATE["tracked_positions"].items()):
                if t_id not in current_t:
                    send_telegram(f"🏁 CIERRE {p_old.symbol} | PnL: ${p_old.profit:+.2f}")
                    add_log_dash(f"🏁 CIERRE {p_old.symbol}")
                    del STATE["tracked_positions"][t_id]
            for p in cur: STATE["tracked_positions"][p.ticket] = p

            if cur: manage_positions(cur)
            
            if time.time() - STATE["last_tg_monitor"] > 30:
                send_telegram(f"📡 *TITAN v540 SCANNING*\nBal: ${acc.balance:.2f} | PnL: ${acc.profit:+.2f}")
                STATE["last_tg_monitor"] = time.time()

            for sym in STATE["active_symbols"]:
                s_i = mt5.symbol_info(sym)
                tick = mt5.symbol_info_tick(sym)
                if not s_i or not tick: continue
                s_d = STATE["symbols_data"][sym]
                sym_pos = [p for p in cur if p.symbol == sym]
                cfg = ASSET_CONFIG[s_d["type"]]
                s_d.update({"pos": len(sym_pos), "pnl": sum(p.profit for p in sym_pos), "spread": s_i.spread})
                
                mh, ml = get_m15_range(sym)
                e21 = get_ema(sym, mt5.TIMEFRAME_M1, 21)
                e50 = get_ema(sym, mt5.TIMEFRAME_M1, 50)
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                
                if rates is not None and len(rates) >= 2:
                    lc = rates[-2]
                    c_range = abs(lc['high'] - lc['low'])
                    b_ratio = (abs(lc['close'] - lc['open']) / c_range * 100) if c_range > 0 else 0
                    s_d["b_ratio"] = b_ratio
                    s_d["ema_trend"] = "UP" if (e21 and e50 and e21 > e50) else "DOWN"

                    if len(sym_pos) == 0 and mh is not None:
                        # TRIPLE FILTRO
                        p_up = (lc['close'] > mh)
                        p_dw = (lc['close'] < ml)
                        s_ok = (b_ratio >= 70)
                        t_ok = (s_d["ema_trend"] == "UP" if p_up else (s_d["ema_trend"] == "DOWN" if p_dw else False))

                        if (p_up or p_dw) and s_ok and t_ok:
                            side = 0 if p_up else 1
                            price = tick.ask if side == 0 else tick.bid
                            v_tot = cfg["lot"] * MAX_BULLETS
                            pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / v_tot
                            sl = price - pts_sl if side == 0 else price + pts_sl
                            
                            add_log_dash(f"🚀 FUEGO: {sym} (6 BALAS)")
                            send_telegram(f"� *RAFAGA LIBERADA: {sym}*")
                            for _ in range(MAX_BULLETS):
                                mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"], "type": side, "price": price, "sl": float(round(sl, s_i.digits)), "magic": MAGIC, "comment": "T_540_R", "type_filling": mt5.ORDER_FILLING_IOC})
                        else:
                            if p_up or p_dw:
                                filtrado = f"{'B:OK' if s_ok else f'B:{b_ratio:.0f}%'} | {'E:OK' if t_ok else 'E:WAIT'}"
                                s_d["status"] = f"⏳ GATILLO: {filtrado}"
                            else:
                                dh = (mh - tick.bid)/s_i.point
                                dl = (tick.bid - ml)/s_i.point
                                s_d["status"] = f"🔎 {('H' if dh < dl else 'L')} {min(dh, dl):.1f}"
                
                if len(sym_pos) > 0: s_d["status"] = f"🚀 WAR {len(sym_pos)}B | ${sum(p.profit for p in sym_pos):.2f}"

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
            print(f"{Fore.WHITE} BALANCE: ${Fore.GREEN}{acc.balance:.2f} {Fore.WHITE}| EQUITY: ${Fore.CYAN}{acc.equity:.2f} {Fore.WHITE}| PnL: ${Fore.YELLOW}{acc.profit:.2f}")
            print(f"{Fore.CYAN}{'─'*115}")
            print(f"{Fore.WHITE} {'ACTIVO':<10} | {'SPR':<4} | {'B%':<5} | {'EMA':<6} | {'M15 HIGH':<10} | {'M15 LOW':<10} | {'BALAS':<4} | {'PnL' :<10} | {'STATUS'}")
            print(f"{Fore.CYAN}{'─'*115}")
            for sym in STATE["active_symbols"]:
                d = STATE["symbols_data"][sym]
                pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
                mh, ml = get_m15_range(sym)
                b_col = Fore.GREEN if d['b_ratio']>=70 else Fore.YELLOW
                print(f" {sym:<10} | {d['spread']:<4} | {b_col}{d['b_ratio']:>4.0f}%{Style.RESET_ALL} | {d['ema_trend']:<6} | {mh if mh else 0:<10.5f} | {ml if ml else 0:<10.5f} | {d['pos']}/{MAX_BULLETS:<2} | {pnl_col:<10} | {d['status']}")
            print(f"{Fore.CYAN}{'─'*115}")
            for l in STATE["last_logs"]: print(f" > {l}")
            print(f"{Fore.CYAN}{'═'*115}")
        except Exception: pass
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
