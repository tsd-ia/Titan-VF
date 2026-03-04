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
MAX_BULLETS = 6            # User request: 6 simultáneas
MAGIC = 700700              
MIN_PROFIT_TRIGGER = 1.00  # Objetivo: $1 USD neto total por señal

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
    Gestión 'Cuchillo Pro': 
    - SL Individual: -$2.00 por bala (No cierra la ráfaga completa).
    - Trailing Cesta: Sigue funcionando para las que queden vivas.
    """
    # 1. ESCUDO INDIVIDUAL: Si una bala llega a -$2.00, se liquida sola
    for p in positions:
        if p.profit <= -2.00:
            add_log_dash(f"🛡️ SL INDIVIDUAL: Cerrando {p.symbol} ticket {p.ticket} | Loss: ${p.profit:.2f}")
            _execute_parallel_close(p)
            return True # Retornamos para que el ciclo principal refresque la lista de posiciones

    # 2. GESTIÓN DE CESTA (Solo con las que quedan)
    total_pnl = sum(p.profit for p in positions)
    
    # HOLGURA ADAPTATIVA
    if total_pnl < 3.00:
        current_gap = 0.40 
    elif total_pnl < 10.00:
        current_gap = 1.00 
    else:
        current_gap = total_pnl * 0.20 

    # 3. ACTIVACIÓN: Modo Cazador
    if not FLASH_TRAIL["active"] and total_pnl >= MIN_PROFIT_TRIGGER:
        FLASH_TRAIL["active"] = True
        FLASH_TRAIL["high_water_mark"] = total_pnl
        FLASH_TRAIL["lock_profit"] = total_pnl - current_gap
        add_log_dash(f"🎯 CAZADOR ACTIVADO: ${total_pnl:.2f} | GAP: ${current_gap:.2f}")

    # 4. SEGUIMIENTO
    if FLASH_TRAIL["active"]:
        if total_pnl > FLASH_TRAIL["high_water_mark"]:
            FLASH_TRAIL["high_water_mark"] = total_pnl
            FLASH_TRAIL["lock_profit"] = total_pnl - current_gap
        
        # 5. CIERRE CESTA: Si el PnL cae por debajo del Lock, liquidamos lo que quede
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
    Lógica de 95% Acertividad Sugerida: 
    1. Filtro Tendencia (EMA 50).
    2. Sweep (Barrido) + Confirmación de Re-ingreso.
    3. Tick Velocity > Umbral.
    """
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 60)
    if rates is None or len(rates) < 60: return None
    
    # 0. FILTRO DE TENDENCIA (EMA 50)
    df = pd.DataFrame(rates)
    ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
    last_close = df['close'].iloc[-1]
    
    current_candle = rates[-1]
    last_candle = rates[-2]
    
    candle_id = current_candle['time']
    if STATE["processed_candles"].get(sym) == candle_id: return None

    # Datos básicos
    high_last = last_candle['high']
    low_last = last_candle['low']
    close_now = current_candle['close']
    open_now = current_candle['open']
    
    # 1. SWEEP (¿Barrió el máximo o mínimo anterior?)
    swept_low = current_candle['low'] < low_last
    swept_high = current_candle['high'] > high_last
    
    # 2. VOLATILIDAD (¿Es una vela con cuerpo suficiente para valer la pena?)
    c_range = abs(current_candle['high'] - current_candle['low'])
    body_size = abs(close_now - open_now)
    body_ratio = (body_size / c_range * 100) if c_range > 0 else 0
    
    # 3. VELOCITY (Intensidad del impulso)
    velocity = calculate_velocity(sym, close_now)
    v_trigger = 0.05 if "XAU" in sym.upper() else 10.0 

    # GATILLO COMPRA: Filtro Alcista (Solo Oro) + Sweep Low + Re-entry
    trend_ok = True
    if "XAU" in sym.upper():
        trend_ok = (last_close > ema50) # Solo compramos ORO si es alcista
        
    if trend_ok and swept_low and close_now > low_last and close_now > open_now and body_ratio > 65 and velocity > v_trigger:
        STATE["processed_candles"][sym] = candle_id
        return mt5.ORDER_TYPE_BUY
        
    # GATILLO VENTA: Filtro Bajista (Solo Oro) + Sweep High + Re-entry
    trend_ok_sell = True
    if "XAU" in sym.upper():
        trend_ok_sell = (last_close < ema50) # Solo vendemos ORO si es bajista
        
    if trend_ok_sell and swept_high and close_now < high_last and close_now < open_now and body_ratio > 65 and velocity > v_trigger:
        STATE["processed_candles"][sym] = candle_id
        return mt5.ORDER_TYPE_SELL

        
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
