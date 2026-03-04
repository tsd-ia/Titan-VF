import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import threading
import concurrent.futures
from datetime import datetime
from colorama import Fore, Style, init as colorama_init
import requests

# --- CONFIGURACIÓN TITAN v48.0.700 (MODO FLASH SCALPER) ---
VERSION = "v48.0.700"
BRANDING = "⚡️ TITAN FLASH: IMPULSE HUNTER"
SYMBOLS = ["XAUUSDm", "BTCUSDm"] # Oro y BTC (Activos de alta velocidad)
colorama_init(autoreset=True)

# GESTIÓN DE RIESGO CRÍTICA (Balance < $15)
LOT_SIZE = 0.01
MAX_BULLETS = 6            # Comandante: Volvemos a las 6, pero con precisión quirúrgica
MAGIC = 700700              
MIN_PROFIT_TRIGGER = 1.00  # Volvemos a $1.00 para pagar el riesgo de 6 balas

# --- CONFIGURACIÓN DE COMBATE v48.7 ---
MODO_DIRECCION = "AUTO"  # Opciones: "AUTO", "BUY", "SELL" (Usted manda aquí)
MAX_TRADE_TIME = 120    # Segundos máximos para una jugada (Scalping puro)



STATE = {
    "is_running": True,
    "active_symbols": [],
    "symbols_data": {},
    "last_logs": ["⚡️ MODO FLASH ACTIVADO | ESPERANDO SEÑAL"],
    "last_heartbeat": 0,
    "processed_candles": {}, # Evita spam (1 señal por vela)
    "velocity_buffer": {}    # Mide la intensidad de ticks
}

# --- TELEGRAM ---
TELEGRAM_TOKEN = '8217691336:AAFWduUGkO_f-QRF6MN338HY-MA46CjzHMg'
TELEGRAM_CHAT_ID = '8339882349'

def send_telegram(msg):
    def _send():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": f"⚡️ TITAN FLASH {VERSION}\n{msg}", "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=8)
        except Exception: pass
    threading.Thread(target=_send, daemon=True).start()

def add_log_dash(msg):
    STATE["last_logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(STATE["last_logs"]) > 6: STATE["last_logs"].pop(0)

# Memoria de rastro para el Trailing Stop de PNL
FLASH_TRAIL = {
    "active": False,
    "high_water_mark": 0.0,
    "lock_profit": 0.0
}

def _execute_parallel_close(p):
    """Auxiliar para cerrar posiciones en hilos paralelos"""
    tick = mt5.symbol_info_tick(p.symbol)
    if not tick: return
    mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL, "position": p.ticket, "symbol": p.symbol, "volume": p.volume,
        "type": mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "price": tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask,
        "magic": MAGIC, "comment": "FLASH_PARA_EXIT", "type_filling": mt5.ORDER_FILLING_IOC
    })

def manage_flash_trailing(positions):
    """
    Gestión 'Cuchillo Pro' + Kill Switch por Tiempo.
    """
    if not positions: return False
    
    total_pnl = sum(p.profit for p in positions)
    
    # 0. KILL SWITCH POR TIEMPO: Scalping es rápido o no es.
    entry_time = min(p.time_update for p in positions) # Usamos actualización para ver vida real
    elapsed = (time.time() - entry_time)
    
    if elapsed > MAX_TRADE_TIME:
        add_log_dash(f"⏱️ TIEMPO AGOTADO ({elapsed:.0f}s): Liquidando ráfaga.")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(positions)) as executor:
            executor.map(_execute_parallel_close, positions)
        return True

    # 1. ESCUDO INDIVIDUAL: -$2.00 por bala
    for p in positions:
        if p.profit <= -2.00:
            add_log_dash(f"🛡️ SL INDIVIDUAL: {p.symbol} | ${p.profit:.2f}")
            _execute_parallel_close(p)
            return True

    # 2. GESTIÓN DE CESTA (Cazador)
    if total_pnl < 3.00: current_gap = 0.40 
    elif total_pnl < 10.00: current_gap = 1.00 
    else: current_gap = total_pnl * 0.20 

    if not FLASH_TRAIL["active"] and total_pnl >= MIN_PROFIT_TRIGGER:
        FLASH_TRAIL["active"] = True
        FLASH_TRAIL["high_water_mark"] = total_pnl
        FLASH_TRAIL["lock_profit"] = total_pnl - current_gap
        add_log_dash(f"🎯 CAZADOR ACTIVADO: ${total_pnl:.2f}")

    if FLASH_TRAIL["active"]:
        if total_pnl > FLASH_TRAIL["high_water_mark"]:
            FLASH_TRAIL["high_water_mark"] = total_pnl
            FLASH_TRAIL["lock_profit"] = total_pnl - current_gap
        
        if total_pnl <= FLASH_TRAIL["lock_profit"]:
            add_log_dash(f"🔪 CUCHILLO ASEGURADO: ${total_pnl:.2f}")
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(positions)) as executor:
                executor.map(_execute_parallel_close, positions)
            
            # Reset memoria
            FLASH_TRAIL["active"] = False
            FLASH_TRAIL["high_water_mark"] = 0.0
            FLASH_TRAIL["lock_profit"] = 0.0
            return True
    return False







def calculate_velocity(sym, current_price):
    """
    Mide cuántos puntos se ha movido el precio en los últimos ticks.
    """
    if sym not in STATE["velocity_buffer"]:
        STATE["velocity_buffer"][sym] = []
    
    STATE["velocity_buffer"][sym].append((time.time(), current_price))
    
    # Mantener solo los últimos 3 segundos
    STATE["velocity_buffer"][sym] = [x for x in STATE["velocity_buffer"][sym] if time.time() - x[0] < 3]
    
    if len(STATE["velocity_buffer"][sym]) < 2: return 0
    
    # Delta de precio en la ventana de tiempo
    price_delta = abs(STATE["velocity_buffer"][sym][-1][1] - STATE["velocity_buffer"][sym][0][1])
    return price_delta

def check_flash_signal(sym):
    """
    LÓGICA BREAKOUT HUNTER (v48.7):
    Si rompe el techo con fuerza -> COMPRAMOS.
    Si rompe el suelo con fuerza -> VENDEMOS.
    """
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 5)
    if rates is None or len(rates) < 5: return None
    
    current_candle = rates[-1]
    last_candle = rates[-2]
    candle_id = current_candle['time']
    if STATE["processed_candles"].get(sym) == candle_id: return None

    high_last = last_candle['high']
    low_last = last_candle['low']
    close_now = current_candle['close']
    
    velocity = calculate_velocity(sym, close_now)
    # v_trigger mayor para BTC para filtrar ruido
    v_trigger = 0.05 if "XAU" in sym.upper() else 25.0 

    if MODO_DIRECCION in ["AUTO", "BUY"]:
        if close_now > high_last and velocity > v_trigger:
            add_log_dash(f"🚀 BREAKOUT ALCISTA: {sym} | Vel: {velocity:.2f}")
            STATE["processed_candles"][sym] = candle_id
            return mt5.ORDER_TYPE_BUY

    if MODO_DIRECCION in ["AUTO", "SELL"]:
        if close_now < low_last and velocity > v_trigger:
            add_log_dash(f"🩸 BREAKOUT BAJISTA: {sym} | Vel: {velocity:.2f}")
            STATE["processed_candles"][sym] = candle_id
            return mt5.ORDER_TYPE_SELL
        
    return None



        
    return None





def main_loop():
    if not mt5.initialize(): 
        print("❌ Error inicializando MT5")
        return
        
    threading.Thread(target=draw_dashboard, daemon=True).start()
    
    # Selección de símbolos
    for s in SYMBOLS:
        if mt5.symbol_select(s, True):
            STATE["active_symbols"].append(s)
            STATE["symbols_data"][s] = {"pnl":0, "pos":0, "spread":0, "v":0, "status":"WAITING"}
        else:
            print(f"⚠️ Símbolo {s} no disponible.")

    while STATE["is_running"]:
        try:
            acc = mt5.account_info()
            if not acc: 
                time.sleep(1)
                continue
                
            positions = mt5.positions_get()
            titan_pos = [p for p in positions if p.magic == MAGIC] if positions else []
            
            # Gestión de salida relámpago
            if titan_pos:
                manage_flash_trailing(titan_pos)
            
            # Escaneo de señales por símbolo
            for sym in STATE["active_symbols"]:
                s_i = mt5.symbol_info(sym)
                tick = mt5.symbol_info_tick(sym)
                if not s_i or not tick: continue
                
                s_d = STATE["symbols_data"][sym]
                sym_pos = [p for p in titan_pos if p.symbol == sym]
                current_pnl = sum(p.profit for p in sym_pos)
                s_d.update({
                    "pos": len(sym_pos), 
                    "pnl": current_pnl, 
                    "spread": s_i.spread,
                    "v": calculate_velocity(sym, tick.bid)
                })

                if not sym_pos: # Solo buscamos señal si no hay posiciones abiertas para ese símbolo
                    signal = check_flash_signal(sym)
                    if signal is not None:
                        price = tick.ask if signal == mt5.ORDER_TYPE_BUY else tick.bid
                        add_log_dash(f"🚀 FLASH TRIGGER: {sym} ({'BUY' if signal == 0 else 'SELL'})")
                        send_telegram(f"⚡️ *GATILLO FLASH {sym}* | Impulso Detectado | Velocity: {s_d['v']:.2f}")
                        
                        # Disparo de ráfaga controlada
                        for i in range(MAX_BULLETS):
                            request = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "symbol": sym,
                                "volume": LOT_SIZE,
                                "type": signal,
                                "price": price,
                                "magic": MAGIC,
                                "comment": f"FLASH_B{i+1}",
                                "type_time": mt5.ORDER_TIME_GTC,
                                "type_filling": mt5.ORDER_FILLING_IOC,
                            }
                            res = mt5.order_send(request)
                            if res.retcode != mt5.TRADE_RETCODE_DONE:
                                add_log_dash(f"❌ Error Bullet {i+1}: {res.comment}")
                        
                        time.sleep(2) # Pausa de seguridad post-disparo
                else:
                    s_d["status"] = f"🔥 IN WAR | ${current_pnl:.2f}"

            time.sleep(0.1) # Ciclo de alta frecuencia (100ms)
        except Exception as e:
            add_log_dash(f"⚠️ Loop Error: {str(e)}")
            time.sleep(1)

def draw_dashboard():
    while STATE["is_running"]:
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
            acc = mt5.account_info()
            if not acc: continue
            
            print(f"{Fore.CYAN}{'═'*115}")
            print(f"{Fore.YELLOW}{Style.BRIGHT} ⚡️ {BRANDING} | {VERSION} | JEFE: DIEGO")
            print(f"{Fore.WHITE} BALANCE: ${Fore.GREEN}{acc.balance:.2f} {Fore.WHITE}| EQUITY: ${Fore.CYAN}{acc.equity:.2f} {Fore.WHITE}| MARGEN: {Fore.YELLOW}{acc.margin_level:.1f}%")
            print(f"{Fore.CYAN}{'─'*115}")
            print(f"{Fore.WHITE} {'ACTIVO':<10} | {'SPR':<4} | {'VEL':<5} | {'PnL' :<10} | {'STATUS'}")
            print(f"{Fore.CYAN}{'─'*115}")
            for sym in STATE["active_symbols"]:
                d = STATE["symbols_data"][sym]
                pnl_col = f"{Fore.GREEN if d['pnl']>=0 else Fore.RED}${d['pnl']:+7.2f}{Style.RESET_ALL}"
                v_col = Fore.CYAN if d['v'] > 0.05 else Fore.WHITE
                print(f" {sym:<10} | {d['spread']:<4} | {v_col}{d['v']:>5.2f}{Style.RESET_ALL} | {pnl_col:<10} | {d['status']}")
            print(f"{Fore.CYAN}{'─'*115}")
            for l in STATE["last_logs"]: print(f" > {l}")
            print(f"{Fore.CYAN}{'═'*115}")
            print(f"{Fore.WHITE} PROTOCOLO: Una señal por vela M1 | Objetivo $1.00 USD neto por ráfaga.")
        except Exception: pass
        time.sleep(0.5)

if __name__ == "__main__":
    main_loop()
