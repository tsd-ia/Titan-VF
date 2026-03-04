import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init as colorama_init

# --- CONFIGURACIÓN TITAN v47.9.451 (M15 BUGFIX) ---
VERSION = "v47.9.451"
BRANDING = "🦅 TITAN ICT: M15 RANGE + SOLID M1"
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

def get_m15_range(sym):
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 1, 1)
    if rates is not None and len(rates) > 0:
        return rates[0]['high'], rates[0]['low']
    return None, None

def get_ema(sym, timeframe, period):
    rates = mt5.copy_rates_from_pos(sym, timeframe, 0, period + 2)
    if rates is None or len(rates) < period: return None
    closes = np.array([r['close'] for r in rates])
    alpha = 2 / (period + 1)
    ema = closes[0]
    for c in closes[1:]: ema = (c * alpha) + (ema * (1 - alpha))
    return ema

def get_rsi(sym, timeframe, period):
    rates = mt5.copy_rates_from_pos(sym, timeframe, 0, period + 20)
    if rates is None or len(rates) < period + 1: return 50
    closes = np.array([r['close'] for r in rates])
    diff = np.diff(closes)
    gains = diff[diff > 0]
    losses = -diff[diff < 0]
    avg_gain = np.mean(gains[-period:]) if len(gains) >= period else 0.0001
    avg_loss = np.mean(losses[-period:]) if len(losses) >= period else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

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
                add_log_dash("💓 CEREBRO OK - ESCANEANDO MICRO-RANGO M15...")
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
                msg += f"━━━━━━━━━━━━━━━\n*Balance:* ${acc.balance:.2f} | *Equity:* ${acc.equity:.2f}\n*PnL Total:* ${acc.profit:+.2f}"
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
                
                # --- LÓGICA DE ENTRADA IMPULSE DISPLACEMENT (M15 BASED) ---
                if len(sym_pos) == 0 and len(cur) < MAX_TOTAL_SYMBOLS:
                    m15_h, m15_l = get_m15_range(sym)
                    if not m15_h or not m15_l: continue
                    
                    # FILTROS TÉCNICOS RAPIDOS
                    ema21 = get_ema(sym, mt5.TIMEFRAME_M1, 21)
                    ema50 = get_ema(sym, mt5.TIMEFRAME_M1, 50)
                    
                    rates_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
                    if rates_m1 is not None and len(rates_m1) >= 2:
                        last_c = rates_m1[-2] # La vela que acaba de cerrar
                        
                        # CALCULO DE "CUERPO SÓLIDO" (Body Ratio)
                        candle_range = abs(last_c['high'] - last_c['low'])
                        body_size = abs(last_c['close'] - last_c['open'])
                        body_ratio = (body_size / candle_range) if candle_range > 0 else 0
                        
                        # GATILLO BUY: Cierre > Techo + Cuerpo Sólido (>70%) + EMA Slope
                        trigger_buy = (last_c['close'] > m15_h) and (body_ratio > 0.7) and (ema21 > ema50) and (tick.ask > ema21)
                        
                        # GATILLO SELL: Cierre < Suelo + Cuerpo Sólido (>70%) + EMA Slope
                        trigger_sell = (last_c['close'] < m15_l) and (body_ratio > 0.7) and (ema21 < ema50) and (tick.bid < ema21)

                        if trigger_buy:
                            pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                            sl = tick.bid - pts_sl
                            res = mt5.order_send({
                                "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                "type": 0, "price": tick.ask, "sl": float(round(sl, s_i.digits)), 
                                "magic": MAGIC, "comment": "TITAN_V440_BUY", "type_filling": mt5.ORDER_FILLING_IOC
                            })
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                add_log_dash(f"🚀 IMPULSE BUY {sym}")
                                send_telegram(f"� *IMPULSE BUY: {sym}*\n*Filtro:* 1-M1 Solid Candle (Body: {body_ratio:.1%})\n*EMA:* Trend Up Confirmada.")
                        
                        elif trigger_sell:
                            pts_sl = (cfg["sl_usd"] / (s_i.trade_tick_value / s_i.point)) / cfg["lot"]
                            sl = tick.bid + pts_sl
                            res = mt5.order_send({
                                "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": cfg["lot"],
                                "type": 1, "price": tick.bid, "sl": float(round(sl, s_i.digits)), 
                                "magic": MAGIC, "comment": "TITAN_V440_SELL", "type_filling": mt5.ORDER_FILLING_IOC
                            })
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                add_log_dash(f"🚀 IMPULSE SELL {sym}")
                                send_telegram(f"� *IMPULSE SELL: {sym}*\n*Filtro:* 1-M1 Solid Candle (Body: {body_ratio:.1%})\n*EMA:* Trend Down Confirmada.")
                        else:
                            # Feedback en dashboard
                            if tick.bid >= m15_h: s_d["status"] = f"⏳ WAIT SOLID M1 (B:{body_ratio:.1%})"
                            elif tick.bid <= m15_l: s_d["status"] = f"⏳ WAIT SOLID M1 (B:{body_ratio:.1%})"
                            else:
                                dist_h = (m15_h - tick.bid)/s_i.point
                                dist_l = (tick.bid - m15_l)/s_i.point
                                s_d["status"] = f"🔎 {('H' if dist_h < dist_l else 'L')} {min(dist_h, dist_l):.1f}"

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
                    m15_h, m15_l = get_m15_range(sym)
                    if m15_h:
                        dist_h = (m15_h - tick.bid)/s_i.point
                        dist_l = (tick.bid - m15_l)/s_i.point
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
        print(f"{Fore.WHITE} {'ACTIVO':<10} | {'SPR':<4} | {'M15 HIGH':<10} | {'M15 LOW':<10} | {'BALAS':<4} | {'PnL' :<10} | {'STATUS'}")
        print(f"{Fore.CYAN}{'─'*115}")
        for sym in STATE["active_symbols"]:
            d = STATE["symbols_data"][sym]
            pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
            m15h, m15l = get_m15_range(sym)
            print(f" {sym:<10} | {d['spread']:<4} | {m15h if m15h else 0:<10.5f} | {m15l if m15l else 0:<10.5f} | {d['pos']}/{MAX_BULLETS:<2} | {pnl_col:<10} | {d['status']}")
        print(f"{Fore.CYAN}{'─'*115}")
        for line in STATE["last_logs"]: print(f" > {line}")
        print(f"{Fore.CYAN}{'═'*115}")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
