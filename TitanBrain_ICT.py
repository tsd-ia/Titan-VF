import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init as colorama_init

# --- CONFIGURACIÓN TITAN v47.9.400 (FILTRO ORO SELECTIVO) ---
VERSION = "v47.9.400"
BRANDING = "🦅 TITAN ICT: FX DIRECTO + ORO CONFIRMADO"
BASE_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "AUDUSD"]
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO
MAX_BULLETS = 6            
MAGIC = 48105              
COOLDOWN_TIME = 900        
MAX_TOTAL_SYMBOLS = 10     
BYPASS_COOLDOWN = True    

ASSET_CONFIG = {
    "GOLD": {
        "lot": 0.01, "lot_reinf": 0.01, "sl_usd": 10.0, "trail": True, 
        "h_trigger": 2.5, "h_lock": 0.5, "t_step": 0.5, "air": 2.0,
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
    "last_logs": ["🚀 MOTOR REPARADO - ESCANEANDO BREAKOUTS"],
    "last_heartbeat": 0, "last_tg_monitor": 0, "tracked_positions": {}
}

# CONFIGURACIÓN TELEGRAM
TELEGRAM_TOKEN = '8217691336:AAFWduUGkO_f-QRF6MN338HY-MA46CjzHMg'
TELEGRAM_CHAT_ID = '8339882349'

def send_telegram(msg):
    def _send():
        try:
            import requests
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
             add_log_dash(f"💀 EMERGENCY EXIT {p.symbol}")
             continue

        is_risky = (p.type == 0 and p.sl < p.price_open) or (p.type == 1 and (p.sl == 0 or p.sl > p.price_open))
        if profit_usd >= cfg["h_trigger"] and is_risky:
             pts = (cfg["h_lock"] / (s_i.trade_tick_value / s_i.point)) / p.volume
             target_sl = p.price_open + pts if p.type == 0 else p.price_open - pts
             mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": float(round(target_sl, s_i.digits)), "tp": p.tp})
             add_log_dash(f"✅ {p.symbol} PROTEGIDO (BE)")
             send_telegram(f"🛡️ *{p.symbol} PROTEGIDO*\n*Ticket:* #{p.ticket}\n*Estado:* Break Even activado.")

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
            if time.time() - STATE["last_heartbeat"] > 30:
                add_log_dash("💓 CEREBRO OK - ESCANEANDO BREAKOUT H1...")
                STATE["last_heartbeat"] = time.time()

            acc = mt5.account_info()
            pos = mt5.positions_get()
            cur = [p for p in pos if p.magic == MAGIC] if pos else []
            
            # TRACKING PARA CIERRES
            current_tickets = {p.ticket: p for p in cur}
            for t_id, p_old in list(STATE["tracked_positions"].items()):
                if t_id not in current_tickets:
                    res_col = "🟢 PROFIT" if p_old.profit >= 0 else "🔴 LOSS"
                    msg = (f"🏁 *POSICIÓN CERRADA: {p_old.symbol}*\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"*Resultado:* {res_col} (${p_old.profit:+.2f})\n"
                           f"*Lote:* {p_old.volume}\n"
                           f"*Balance:* ${acc.balance:.2f}\n"
                           f"*Equity:* ${acc.equity:.2f}\n"
                           f"*PnL Total:* ${acc.profit:+.2f}")
                    send_telegram(msg)
                    add_log_dash(f"🏁 CIERRE {p_old.symbol}: ${p_old.profit:+.2f}")
                    del STATE["tracked_positions"][t_id]
            for p in cur: STATE["tracked_positions"][p.ticket] = p

            # MONITOREO 10 SEG
            if cur and (time.time() - STATE["last_tg_monitor"] > 10):
                msg = f"📊 *MONITOREO EN VIVO*\n━━━━━━━━━━━━━━━\n"
                for p in cur:
                    msg += f"• *{p.symbol}:* ${p.profit:+.2f} ({'BUY' if p.type==0 else 'SELL'} {p.volume})\n"
                msg += f"━━━━━━━━━━━━━━━\n*Equity:* ${acc.equity:.2f} | *PnL:* ${acc.profit:+.2f}"
                send_telegram(msg)
                STATE["last_tg_monitor"] = time.time()

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
                
                # --- LÓGICA DE ENTRADA DIFERENCIADA ---
                if len(sym_pos) == 0 and len(cur) < MAX_TOTAL_SYMBOLS:
                    is_gold = (s_d["type"] == "GOLD")
                    
                    # DETECCIÓN DE BREAKOUT
                    break_up = h_h and tick.bid >= h_h
                    break_down = h_l and tick.bid <= h_l
                    
                    if break_up or break_down:
                        # Si es ORO, buscamos confirmación de vela M1 (MSS)
                        if is_gold:
                            rates_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                            if rates_m1 is not None and len(rates_m1) >= 2:
                                last_m1 = rates_m1[-2]
                                trigger_buy = (tick.bid > last_m1['high']) and break_up
                                trigger_sell = (tick.ask < last_m1['low']) and break_down
                                
                                if trigger_buy or trigger_sell:
                                    side = "BUY" if trigger_buy else "SELL"
                                    pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                                    sl = tick.bid - pts_sl if side=="BUY" else tick.ask + pts_sl
                                    res = mt5.order_send({
                                        "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                        "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                                        "sl": float(round(sl, s_i.digits)), "magic": MAGIC, "comment": "ORO_CONF_H1",
                                        "type_filling": mt5.ORDER_FILLING_IOC
                                    })
                                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                        add_log_dash(f"🎯 ORO {side} CONFIRMADO")
                                        send_telegram(f"🥇 *ORO: ENTRADA CONFIRMADA*\n*Tipo:* {side} | *Lote:* {cfg['lot']}\n*MSS M1:* Velas alineadas en breakout.")
                                else:
                                    target_p = last_m1['high'] if break_up else last_m1['low']
                                    s_d["status"] = f"⏳ ORO WAIT M1 {('UP' if break_up else 'DOWN')} {target_p:.2f}"
                        
                        # Si es FX, entrada DIRECTA por contacto
                        else:
                            side = "BUY" if break_up else "SELL"
                            pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                            sl = tick.bid - pts_sl if side=="BUY" else tick.bid + pts_sl
                            res = mt5.order_send({
                                "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                                "sl": float(round(sl, s_i.digits)), "magic": MAGIC, "comment": "FX_DIRECT_H1",
                                "type_filling": mt5.ORDER_FILLING_IOC
                            })
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                add_log_dash(f"🚀 FX {sym} DISPARO DIRECTO")
                                send_telegram(f"⚡ *FX: DISPARO DIRECTO {sym}*\n*Tipo:* {side} | *Breakout:* Contacto H1.")

                # --- REFUERZOS ---
                elif len(sym_pos) > 0 and len(sym_pos) < MAX_BULLETS:
                    pnl = sum(p.profit for p in sym_pos)
                    all_protected = all((p.type==0 and p.sl >= p.price_open) or (p.type==1 and p.sl <= p.price_open and p.sl != 0) for p in sym_pos)
                    if pnl >= cfg["r_trigger"] and all_protected:
                         side = "BUY" if sym_pos[0].type == 0 else "SELL"
                         res = mt5.order_send({
                             "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot_reinf"],
                             "type": 0 if side=="BUY" else 1, "price": tick.ask if side=="BUY" else tick.bid,
                             "sl": sym_pos[0].sl, "magic": MAGIC, "comment": "RAIN_BULLET", "type_filling": mt5.ORDER_FILLING_IOC
                         })
                         if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            add_log_dash(f"� REFUERZO {sym}")
                            send_telegram(f"🔥 *REFUERZO: {sym}*\n*Lote:* +{cfg['lot_reinf']}\n*Total Balas:* {len(sym_pos)+1}")

                if len(sym_pos) == 0:
                    dist_h = (h_h - tick.bid)/s_i.point if h_h else 999
                    dist_l = (tick.bid - h_l)/s_i.point if h_l else 999
                    s_d["status"] = f"🔎 {('H' if dist_h < dist_l else 'L')} {min(dist_h, dist_l):.1f}"
                else:
                    s_d["status"] = f"🚀 WAR {len(sym_pos)}B | {sum(p.profit for p in sym_pos):.2f}"

            time.sleep(1)
        except Exception:
            time.sleep(1)

def draw_dashboard():
    while STATE["is_running"]:
        os.system('cls' if os.name == 'nt' else 'clear')
        acc = mt5.account_info()
        if not acc: continue
        print(f"{Fore.CYAN}{'═'*115}")
        print(f"{Fore.RED}{Style.BRIGHT} 🦅 {BRANDING} | {VERSION} | JEFE: DIEGO (MODO RECUPERACIÓN)")
        print(f"{Fore.WHITE} BALANCE: ${Fore.GREEN}{acc.balance:.2f} {Fore.WHITE}| EQUITY: ${Fore.CYAN}{acc.equity:.2f} {Fore.WHITE}| PnL: {Fore.YELLOW}${acc.profit:.2f}")
        print(f"{Fore.CYAN}{'─'*115}")
        print(f"{Fore.WHITE} {'ACTIVO':<10} | {'SPR':<4} | {'H1 HIGH':<10} | {'H1 LOW':<10} | {'BALAS':<4} | {'PnL' :<10} | {'STATUS'}")
        print(f"{Fore.CYAN}{'─'*115}")
        for sym in STATE["active_symbols"]:
            d = STATE["symbols_data"][sym]
            pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
            h1h, h1l = get_h1_liquidity(sym)
            print(f" {sym:<10} | {d['spread']:<4} | {h1h if h1h else 0:<10.5f} | {h1l if h1l else 0:<10.5f} | {d['pos']}/{MAX_BULLETS:<2} | {pnl_col:<10} | {d['status']}")
        print(f"{Fore.CYAN}{'─'*115}")
        for line in STATE["last_logs"]: print(f" > {line}")
        print(f"{Fore.CYAN}{'═'*115}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
