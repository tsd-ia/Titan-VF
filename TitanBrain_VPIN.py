import sys, io
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except:
    pass

from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
import threading
import time
import os
import random
import math # NEW IMPORT FOR JSON
from datetime import datetime, timedelta
from collections import deque
import requests # NEW FOR NTFY
import subprocess # NEW FOR PORT CLEANUP

# --- UPGRADE: FASTAPI (v7.58 DEEP SCALPER) ---
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    from fastapi import FastAPI, Request, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    pass # Se instalarán en el siguiente ciclo

try:
    import MetaTrader5 as mt5
    import pandas as pd
    import numpy as np
    from tensorflow.keras.models import load_model
    from sklearn.preprocessing import MinMaxScaler
except ImportError as e:
    print(f"❌ ERROR LIBRERÍAS IA: {e}")

# --- FUNCIÓN DE LIMPIEZA DE PUERTO (ANTI-SQUATTER) ---
def kill_port_process(port):
    try:
        # Buscar el PID que usa el puerto usando netstat (Windows)
        cmd = f'netstat -ano | findstr :{port}'
        res = subprocess.check_output(cmd, shell=True).decode()
        for line in res.strip().split('\n'):
            if 'LISTENING' in line:
                pid = line.strip().split()[-1]
                if pid != "0":
                    print(f"🧹 LIMPIEZA: Matando proceso fantasma en puerto {port} (PID: {pid})...")
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                    time.sleep(1) # Esperar a que el puerto se libere
    except Exception:
        pass 

def kill_previous_instances():
    """ Mata cualquier proceso de Python que esté ejecutando este script específico """
    try:
        import psutil
        current_pid = os.getpid()
        # v18.9.114: Búsqueda agresiva por línea de comandos
        purged = 0
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                # v18.9.117: Solo matar instancias de BRAIN. (Bat limpia el resto)
                cmd = proc.info.get('cmdline', [])
                if cmd and any('TitanBrain_VPIN' in s for s in cmd):
                    pid = proc.info['pid']
                    if pid != current_pid:


                        # No matar al padre (Runner)
                        try:
                            parent = psutil.Process(current_pid).parent()
                            if parent and pid == parent.pid: continue
                        except: pass
                        
                        proc.kill()
                        purged += 1
            except: continue
        if purged > 0:
            print(f"🧹 PURGA COMPLETA: {purged} instancias eliminadas.")
    except Exception as e:
        print(f"⚠️ Error en Purga: {e}")


# EJECUTAR LIMPIEZA INMEDIATA
print("🧹 [CONSOLE] LIMPIANDO PROCESOS FANTASMA...")
kill_port_process(8000)
kill_previous_instances() # v15.20: Limpieza profunda de procesos huérfanos
print("✅ LIMPIEZA COMPLETA.")

# ================= CONFIG =================
PORT = 8000
# LISTA DE ACTIVOS MONITORIZADOS (RADAR MÚLTIPLE v7.8)
# CEREBRO DUAL: Configurado para ORO y BTC independientes
SYMBOLS = ["XAUUSDm", "BTCUSDm"]

# REPARACIÓN DE RUTA (Basada en LOGS del Robot)
MQL5_FILES_PATH = r"C:\Users\dfa21\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06\MQL5\Files"
MODEL_FILE_PATH = os.path.join(MQL5_FILES_PATH, 'modelo_lstm_titan.h5') 
MODEL_BTC_FILE_PATH = os.path.join(MQL5_FILES_PATH, 'modelo_lstm_btc.h5') # v18.9.98: Cerebro BTC
CMD_FILE_PATH = os.path.join(MQL5_FILES_PATH, 'titan_command.txt')
HISTORY_FILE_PATH = os.path.join(MQL5_FILES_PATH, 'titan_history.json')
SETTINGS_FILE_PATH = os.path.join(MQL5_FILES_PATH, 'titan_settings.json')
AUTOPILOT_FILE_PATH = os.path.join(MQL5_FILES_PATH, 'titan_autopilot.txt')
MISSION_FILE_PATH = os.path.join(MQL5_FILES_PATH, 'titan_mission.json')

# --- CONFIGURACIÓN DE PARALELIZACIÓN (OCTOPUS 2.0) ---
from concurrent.futures import ThreadPoolExecutor
executor_octopus = ThreadPoolExecutor(max_workers=len(SYMBOLS) + 2)

def global_health_check():
    print("🩺 [CONSOLE] EJECUTANDO HEALTH CHECK...")
    """ Verifica la alineación de la IA y el set de features (v18.9.84) """
    try:
        if modelo_lstm:
            # 1. Verificar dimension del modelo vs features
            req_dim = modelo_lstm.input_shape[-1]
            actual_dim = len(MASTER_FEATURES)
            if req_dim != actual_dim:
                print(f"⚠️ IA ORO: Modelo espera {req_dim} features.")
            
            # 2. Verificar existencia de scalers críticos
            gold_scaler = os.path.exists(SCALER_PATH_TEMPLATE.format("XAUUSDm"))
            if not gold_scaler:
                print("🚨 CRÍTICO: No se encuentra el Scaler de Oro (XAUUSDm). La IA operará en modo ciego.")
            else:
                print("✅ IA ALINEADA: Set maestro de 9 dimensiones listo.")
    except Exception as e:
        print(f"⚠️ Error en Health Check: {e}")

# --- CONFIGURACIÓN DE GESTIÓN ---
MAX_BULLETS = 3  # v18.9.94: 3 balas - bala 2 y 3 solo si anterior positiva
MAX_DAILY_LOSS = 0.85 # -85% equidad = Stop loss global (Sobrevivencia = Mínimo $15.0)9
MAX_SESSION_LOSS = -8.0  # v18.9.93: Máximo -$8 por sesión
MIN_EQUITY_TO_TRADE = 10.0  # v18.9.93: GUARDIA MÍNIMA - Si equity < $10, bot se congela
LAST_ENTRY_PRICE = {} # Memoria de precio para evitar apilar en el mismo punto
LAST_HEARTBEAT = {} 
LAST_SIGNALS = {} # Memoria para no repetir órdenes (RSI extremo)
LAST_ENTRY = {}   # Memoria de tiempo para RE-ENTRADAS
LAST_INSTINTO_LOG = {} # NEW v7.43
MARKET_CLOSED_UNTIL = {} # Memoria temporal para Mercados Cerrados (Error 10044)
LAST_PROBS = {}   # Memoria de probabilidades IA para Dashboard
CONSECUTIVE_LOSSES = {} # {symbol: count}
COOL_DOWN_UNTIL = {}     # {symbol: timestamp}
LAST_STABLE_SIG = {}     # {symbol: (signal, first_seen_ts)}
CONRARY_COUNT = {}      # NEW v7.61 - estabilidad anti-ruido
LAST_OLLAMA_CALL = {}   # v18.9.95: Throttling Ollama (10m cooldown)
LAST_OLLAMA_CACHE = {}  # v18.9.101: Cognitive Cache (RSI, BB, Sig -> Res)
TICK_FREQUENZ = {}      # v18.9.103: Monitor de frecuencia de ticks
LAST_CLOSE_TS = {}  # Memoria anti-reentrada (v6.4)
LAST_STABLE_SIG = {} # Memoria de estabilidad (v7.72)
LAST_NOTIF_CONF = {} # Memoria de alertas v7.15
LAST_NOTIF_TIME = {} # Memoria de tiempo alertas v7.15
LAST_CLOSE_PRICE = {} 
LAST_CLOSE_DIR = {} 
LAST_CLOSE_REASON = {} # v18.9.106: Para re-entrada inmediata
LAST_CLOSE_TYPE_REAL = {} # v18.9.106: BUY/SELL real de la posicion cerrada
GLOBAL_ADVICE = {} # NEW v7.99: Para sincronizar Cerebro y PACMAN
MIRROR_MODE = False # v18.9.32: BLOQUEADO EN FALSE PERMANENTE (Causa de pérdidas críticas)

BURST_DELAY = 0.1          
PACMAN_DELAY = 1           # Cosecha cada 1s (v7.04 SPEED)
SMOOTH_CONF = {} # NEW v8.2: Memoria de suavizado de confianza
# v18.9.94: Variables consolidadas arriba
# MAX_DAILY_LOSS ya definido

# --- v15.6 VANGUARDIA (TITANIUM SHIELD) ---
# MAX_BULLETS ya definido arriba (3 para recuperación)
MIN_MARGIN_LEVEL = 30.0    # Aggresión máxima para recuperación
MAX_SKEW_SPREAD = 2500      # Ajustado para BTC Fin de Semana
MAX_EXPLORATION_SPREAD = 3000 # Ajustado para BTC Fin de Semana
VANGUARDIA_LOCK = False    

# --- v18.9.78: MEMORIA DE ACCIÓN ---
LAST_CLOSE_TYPE = {} # {symbol: "BUY"/"SELL"}
COOLDOWN_AFTER_CLOSE = 15  # v15.30: Reducido para scalping rápido (antes 90s)
LAST_CLOSE_TIME = {}       # Memoria para el cooldown

# --- CONFIGURACIÓN DE FIREBASE (SENTINEL v7.0) ---
FIREBASE_URL = "https://titan-sentinel-default-rtdb.firebaseio.com"
FIREBASE_PATH = "live"

# --- CONFIGURACIÓN DE OLLAMA (CEREBRO LOCAL & NUBE) ---
OLLAMA_URL = "http://localhost:11434/api/generate"
# Fallback Dinámico: IA Nube (Rápida) -> IA Nube (Súper) -> Local
OLLAMA_MODELS = ["gpt-oss:20b-cloud", "gpt-oss:120b-cloud", "deepseek-coder:1.3b"]
OLLAMA_FAIL_COUNT = 0

def call_ollama(prompt):
    """ Consulta al Cerebro (Sincronización v18.9.123) """

    global OLLAMA_FAIL_COUNT
    for i, model in enumerate(OLLAMA_MODELS):
        try:
            payload = {"model": model, "prompt": prompt, "stream": False}
            res = requests.post(OLLAMA_URL, json=payload, timeout=4)
            if res.status_code == 200:
                response_text = res.json().get("response", "EMPTY")
                if "ERROR" not in response_text.upper():
                    if i > 0 and OLLAMA_FAIL_COUNT % 5 == 0:
                        log(f"⚠️ IA NUBE AGOTADA: Usando {model}. (70% cuota estimada)")
                        # Inyectar alerta en Telegram
                        threading.Thread(target=requests.get, args=(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage?chat_id={os.getenv('TELEGRAM_CHAT_ID')}&text=🛡️ TITAN: IA PRINCIPAL AGOTADA. Iniciando Modo Supervivencia con {model}.",)).start()
                    OLLAMA_FAIL_COUNT = 0
                    return response_text, model
            OLLAMA_FAIL_COUNT += 1
            log(f"⚠️ IA {model} falló o sin cuota. Probando siguiente...")
        except:
            continue
    return "IA en espera... (Quota/Error)", "FALLBACK_FAILED"

def get_human_advice(sig, conf, sym):
    """ Convierte señales técnicas en lenguaje humano y estima ganancia """
    now_str = datetime.now().strftime("%H:%M:%S")
    if sig == "HOLD" or conf < 0.60:
        return f"⌛ [{now_str}] VIGILANCIA: Mercado en calma. Esperando señal..."
    
    # Estimación de ganancia basada en ATR y lotaje 0.01
    try:
        s_info = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        if not s_info or not tick: return f"VIGILANCIA TÁCTICA ACTIVA EN {sym}"
        
        # Factor de profit estimado (Lot 0.01)
        profit_factor = 1.0 if "XAU" in sym or "Gold" in sym else 0.1
        # En Oro, 1 USD move = 1 USD profit con 0.01.
        est_val = max(1.15, (tick.ask - tick.bid) * 10 * profit_factor)
        
        timing = "1-3 minutos" if "XAU" in sym or "US30" in sym else "5-10 minutos"
        
        if sig == "BUY":
            return f"🚀 [{now_str}] OPORTUNIDAD COMPRA ({sym}): Meta est. ${est_val:.2f} | {timing}."
        elif sig == "SELL":
            return f"📉 [{now_str}] OPORTUNIDAD VENTA ({sym}): Meta est. ${est_val:.2f} | {timing}."
    except:
        pass
    return f"🛡️ [{now_str}] SENTINEL: {sig} detectado ({conf*100:.0f}%)"

def push_firebase(data):
    """ Sincroniza el Cerebro con el Dashboard Sentinel v7.0 """
    def _push():
        try:
            # v18.9.65: Sanitización de datos para evitar errores de serialización
            url = f"{FIREBASE_URL}/{FIREBASE_PATH}.json"
            data["last_update"] = datetime.now().strftime("%H:%M:%S")
            # Forzar conversión a tipos nativos para que requests.put no falle
            clean_data = json.loads(json.dumps(data, cls=NumpyEncoder))
            # v18.9.100: CAMBIO A PATCH para no borrar el nodo /commands enviado por la WEB
            res = requests.patch(url, json=clean_data, timeout=5)
            if res.status_code not in [200, 201, 204]:
                print(f"⚠️ Firebase Error: {res.status_code}")
        except Exception as e:
            # print(f"⚠️ Firebase Crash: {e}")
            pass
    threading.Thread(target=_push, daemon=True).start()

def firebase_command_poller():
    """ v18.9.97: Puente de Mandos desde la WEB vía Firebase """
    global STATE
    url = f"{FIREBASE_URL}/live/commands.json"
    log("📡 PUENTE DE MANDOS WEB ACTIVADO")
    while True:
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                cmds = res.json()
                if cmds:
                    with state_lock:
                        if "oro_brain_on" in cmds:
                            val = bool(cmds["oro_brain_on"])
                            if val != STATE.get("oro_brain_on"):
                                STATE["oro_brain_on"] = val
                                log(f"🧠 MANDO WEB: Cerebro ORO {'ACTIVADO' if val else 'DESACTIVADO'}")
                        if "btc_brain_on" in cmds:
                            val = bool(cmds["btc_brain_on"])
                            if val != STATE.get("btc_brain_on"):
                                STATE["btc_brain_on"] = val
                                log(f"🧠 MANDO WEB: Cerebro BTC {'ACTIVADO' if val else 'DESACTIVADO'}")
                        if "auto_mode" in cmds:
                            val = bool(cmds["auto_mode"])
                            if val != STATE.get("auto_mode", False):
                                STATE["auto_mode"] = val
                                log(f"🔫 MANDO WEB: Autonomous Fire {'ON' if val else 'OFF'}")
                        if "start_mission" in cmds and cmds["start_mission"]:
                            log("🎯 MANDO WEB: FORCING START MISSION!")
                            start_mission(target_profit=500.0)
                            requests.patch(url, json={"start_mission": False})
                        if "panic" in cmds and cmds["panic"]:
                            log("🚨 MANDO WEB: ¡BOTÓN DE PÁNICO ACTIVADO!")
                            stop_mission()
                            # Resetear pánico en firebase para no loopear
                            requests.patch(url, json={"panic": False})
            time.sleep(1)
        except:
            time.sleep(2)

# --- ESTADO DE MISIÓN (Persistente) ---
mission_state = {
    "active": False,
    "symbol": None,
    "start_equity": 0.0,
    "start_time": 0,
    "target": 500.0,
    "max_profit": -9999.0  # Movido aquí para persistencia v15.20
}

# Configuración Dinámica (Lote) - v18.9.115: REGLA DE ORO SL $25
ASSET_CONFIG = {
    "XAUUSDm": {"lot": 0.01, "sl": 2500, "tp": 999999}, # $25 stop individual
    "BTCUSDm": {"lot": 0.01, "sl": 250000, "tp": 15000}, # Usuario: 0.01 LOT | MODO BUNKER
    "GBPUSDm": {"lot": 0.02, "sl": 1250, "tp": 1000},
    "EURUSDm": {"lot": 0.02, "sl": 1250, "tp": 1000},
    "US30m": {"lot": 0.02, "sl": 12500, "tp": 10000},
    "NAS100m": {"lot": 0.02, "sl": 12500, "tp": 10000}
}
DEFAULT_CONFIG = {"lot": 0.01, "sl": 1000, "tp": 250}


TIMEFRAME = mt5.TIMEFRAME_M1
LOOKBACK_PERIOD = 120  # SYNC v5.5 Sniper

# --- v15.23: CALENDARIO DE MERCADO ORO (XAUUSDm) ---
# Horarios CME para Metales (Gold) ajustados a Chile (UTC-3/UTC-4)
# Formato: (Mes, Dia, Descripcion, Tipo, HoraCierreChile_24h)
MARKET_HOLIDAYS_2026 = [
    (1, 1, "Año Nuevo", "CLOSED", 0),
    (1, 19, "MLK Day", "EARLY", 15),
    (2, 16, "Presidents' Day", "EARLY", 15),
    (4, 3, "Viernes Santo", "CLOSED", 0),
    (5, 25, "Memorial Day", "EARLY", 13),
    (6, 19, "Juneteenth", "EARLY", 13),
    (7, 3, "Independencia (Obs)", "EARLY", 13),
    (9, 7, "Labor Day", "EARLY", 13),
    (11, 26, "Thanksgiving", "CLOSED", 0),
    (11, 27, "Post-Thanksgiving", "EARLY", 14),
    (12, 24, "Nochebuena", "EARLY", 14),
    (12, 25, "Navidad", "CLOSED", 0)
]

def get_market_warning():
    try:
        now = datetime.now() # Hora Local Chile
        day, month, weekday = now.day, now.month, now.weekday()
        
        # 1. Cierres de Fin de Semana
        if weekday == 4: # Viernes
            if now.hour >= 17: return "⚠️ CIERRE SEMANAL: 19:00 (Chile)"
        elif weekday == 5: return "🛑 MERCADO CERRADO (Sábado)"
        elif weekday == 6: 
            return "🛑 MERCADO CERRADO (Abre 20:00 Chile)" if now.hour < 18 else "🌅 SESIÓN ASIÁTICA ABIERTA"

        # 2. Pausa Diaria (19:00 - 20:00 Chile)
        if now.hour == 19: return "☕ PAUSA DIARIA: Mercado cerrado hasta 20:00"

        # 3. Feriados
        for m, d, desc, t, h in MARKET_HOLIDAYS_2026:
            if month == m and day == d:
                if now.hour < 20:
                    if t == "CLOSED": return f"🛑 FERIADO: {desc} (Abre 20:00 Chile)"
                    if now.hour >= h: return f"🛑 CERRADO: {desc} (Abre 20:00 Chile)"
                    if now.hour >= h - 2: return f"⚠️ CIERRE PRÓXIMO: {desc} ({h}:00)"
                else: return f"🌅 REAPERTURA: {desc} (Global Session)"
            
            # Avisar próximo feriado (3 días vista)
            try:
                holiday_date = datetime(now.year, m, d)
                diff = (holiday_date - now.replace(hour=0, minute=0, second=0, microsecond=0)).days
                if 0 < diff <= 3: return f"📅 FERIADO PRÓXIMO: {desc} ({d}/{m})"
            except: pass
    except: pass
    
    return None

def is_market_closed(symbol):
    """ v18.9.95: Sensor de Cierre Real para evitar reintentos inútiles """
    if "BTC" in symbol: return False # Cripto 24/7
    
    now = datetime.now()
    weekday = now.weekday()
    # Viernes después de las 19:00 (Chile)
    if weekday == 4 and now.hour >= 19: return True
    # Sábado
    if weekday == 5: return True
    # Domingo antes de las 20:00 (Chile)
    if weekday == 6 and now.hour < 20: return True
    # Pausa Diaria 19:00 - 20:00
    if now.hour == 19: return True
    
    return False
    

# Extended State for Brain
# --- GLOBALES DE CONTROL ---
LAST_MISSION_TIME = 0  # Control de enfriamiento global
STATE = {
    "bullets": 0,
    "pnl": 0.0,
    "last_fire": 0,
    "active_pairs": [],
    "market_warning": "OPEN 🟢",
    "last_ollama_res": "Ollama Sentinel Active",
    "price_history": [],
    "oro_brain_on": True,   # v18.9.95: Control Manual vía Web
    "btc_brain_on": True,    # v18.9.95: Control Manual vía Web
    "auto_mode": False,      # v18.9.99: Control de Autofuego por Defecto OFF
    "start_mission": False
}

LOG_BUFFER = deque(maxlen=10)
MISSION_HISTORY = deque(maxlen=1000) # v15.47: Fix Critical
MISSION_LATENCIES = [] # v15.43: Rastro de ms para auditoría real
LAST_LATENCY = 0.0      # v15.45: Memoria para bloqueo preventivo
LAST_LATENCY_UPDATE = 0 # v15.48: Control de frescura del ping
state_lock = threading.RLock()

def load_history():
    try:
        if os.path.exists(HISTORY_FILE_PATH):
            with open(HISTORY_FILE_PATH, 'r') as f:
                data = json.load(f)
                MISSION_HISTORY.clear()
                MISSION_HISTORY.extend(data)
                log(f"📚 Historial recuperado: {len(data)} misiones")
    except Exception as e:
        log(f"⚠️ Error cargando historial: {e}")
        # Si el historial está corrupto, lo inicializamos vacío para evitar colapsos
        MISSION_HISTORY.clear()

def save_history():
    try:
        data = list(MISSION_HISTORY)
        content = json.dumps(data, cls=NumpyEncoder)
        atomic_write(HISTORY_FILE_PATH, content)
    except Exception as e:
        log(f"⚠️ Error guardando historial: {e}")

def save_settings():
    try:
        is_auto = STATE.get("auto_pilot", False)
        data = {
            "auto_pilot": is_auto,
            "mirror_mode": MIRROR_MODE
        }
        content = json.dumps(data, cls=NumpyEncoder)
        atomic_write(SETTINGS_FILE_PATH, content)
        
        # Guardar flag simple para el EA (MQL5)
        atomic_write(AUTOPILOT_FILE_PATH, "1" if is_auto else "0")
    except: pass

def load_settings():
    global MIRROR_MODE
    try:
        if os.path.exists(SETTINGS_FILE_PATH):
            with open(SETTINGS_FILE_PATH, 'r') as f:
                data = json.load(f)
                with state_lock:
                    STATE["auto_pilot"] = data.get("auto_pilot", False)
                    # Sincronización de Modo Espejo desde el archivo
                    MIRROR_MODE = data.get("mirror_mode", MIRROR_MODE)
                log(f"⚙️ Configuración recuperada: Auto-Pilot {'ON' if STATE['auto_pilot'] else 'OFF'} | Espejo {'ON' if MIRROR_MODE else 'OFF'}")
        
        # PERSISTENCIA DE MISIÓN
        if os.path.exists(MISSION_FILE_PATH):
            with open(MISSION_FILE_PATH, 'r') as f:
                saved_mission = json.load(f)
                if saved_mission.get("active"):
                    with state_lock:
                        mission_state.update(saved_mission)
                        STATE["max_profit"] = mission_state.get("max_profit", -9999.0)
                        STATE["pnl"] = saved_mission.get("last_pnl", 0.0)
                    log(f"🛰️ MISIÓN RECUPERADA: {mission_state['symbol'] if mission_state['symbol'] else 'GLOBAL'} | Peak: ${STATE['max_profit']:.2f}")
        # SINCRO EXTERNA (BOTÓN EN EA)
        mirror_file = os.path.join(MQL5_FILES_PATH, "titan_mirror_ctrl.txt")
        if os.path.exists(mirror_file):
            try:
                with open(mirror_file, "r") as f:
                    content = f.read().strip()
                if content in ["0", "1"]:
                    new_mode = (content == "1")
                    if new_mode != MIRROR_MODE:
                        with state_lock:
                            MIRROR_MODE = False # v11.0: MODO ESPEJO DESACTIVADO - SEGUIR TENDENCIA
                        log(f"🧠 INICIANDO OCTOPUS | MODO ESPEJO: {'ON' if MIRROR_MODE else 'OFF'}")
            except: pass
    except Exception as e:
        log(f"⚠️ Error cargando settings/misión: {e}")

def send_ntfy(message):
    def _send():
        try:
            topic = "titan_oro_dfa"
            requests.post(f"http://ntfy.sh/{topic}", 
                          data=message.encode('utf-8'),
                          headers={
                              "Title": "TITAN BRAIN ALERT", 
                              "Priority": "high",
                              "Tags": "chart_with_upwards_trend,gold"
                          }, 
                          timeout=5,
                          verify=False)
        except Exception as e:
            log(f"⚠️ NTFY Error: {e}")
    
    # --- ASINCRONÍA TOTAL PARA NO BLOQUEAR EL CEREBRO ---
    threading.Thread(target=_send, daemon=True).start()

def save_mission_state():
    try:
        content = json.dumps(mission_state, cls=NumpyEncoder)
        atomic_write(MISSION_FILE_PATH, content)
    except Exception as e:
        log(f"⚠️ Error guardando reporte misión: {e}")

# IA OBJECTS
modelo_lstm = None
modelo_lstm_btc = None # v18.9.98: Cerebro BTC
scaler_lstm = None
if 'MinMaxScaler' in globals(): scaler_lstm = MinMaxScaler(feature_range=(0, 1))

# ============ HELPERS ============
def log(msg):
    try:
        ts = time.strftime("%H:%M:%S")
        thread_name = threading.current_thread().name
        t_name = "MAIN" if thread_name == "MainThread" else thread_name[:4].upper()
        formatted_msg = f"[{ts}][{t_name}] {msg}"
        LOG_BUFFER.append(formatted_msg)
        sys.stderr.write(formatted_msg + "\n")
        sys.stderr.flush()
        
        # v18.9.112: Blindaje contra bloqueos de archivo
        try:
            with open("titan_vanguardia.log", "a", encoding="utf-8") as f:
                f.write(formatted_msg + "\n")
        except:
            pass # No morir si el archivo está bloqueado
    except:
        pass


import traceback
def global_exception_handler(exctype, value, tb):
    error_msg = f"💥 UNCAUGHT EXCEPTION: {exctype.__name__}: {value}\n{''.join(traceback.format_exception(exctype, value, tb))}"
    log(error_msg)
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler


def atomic_write(path, content):
    try: os.makedirs(os.path.dirname(path), exist_ok=True)
    except: pass
    tmp = path + ".tmp"
    for _ in range(3): # Reintentar hasta 3 veces si está bloqueado
        try:
            with open(tmp, "w") as f: f.write(content)
            if os.path.exists(path): os.remove(path)
            os.rename(tmp, path)
            return True
        except: 
            time.sleep(0.05)
    return False

def init_mt5():
    if not mt5.initialize(): 
        # v18.9.106: Reportar error real de MT5 para Diagnóstico
        print(f"❌ FALLO CRÍTICO MT5: {mt5.last_error()}")
        return False
    for s in SYMBOLS: mt5.symbol_select(s, True)
    return True

def get_equity():
    acc = mt5.account_info()
    return acc.equity if acc else 0.0

def get_adaptive_risk_params(balance, conf, rsi_val, sym):
    """ Protocolo v18.9.126: Gestión de Riesgo Adaptativa Acelerada para BTC """
    # Si es BTC, usamos un setting de agresividad especial a solicitud del Jefe
    is_btc = (sym == "BTCUSDm")
    
    if balance < 50.0:
        max_bullets = 3 if is_btc else 1
        smart_lot = 0.05 if is_btc else 0.01 
    elif balance < 100.0:
        max_bullets = 3 if is_btc else 2
        smart_lot = 0.08 if is_btc else 0.02
    else:
        max_bullets = 4 if is_btc else 3
        smart_lot = 0.10 if is_btc else 0.03
        
    return max_bullets, smart_lot


def get_bunker_sl_price(sym, lot, side, price):
    """ v18.9.115: REGLA DE ORO DEL JEFE - SL FIJO A $25 USD """
    try:
        s_info = mt5.symbol_info(sym)
        if not s_info: return 0.0
        
        # REGLA MAESTRA: $25 USD de pérdida permitida
        target_loss = 25.0
        
        # Formula: PriceDelta = Loss / (Lot * ContractSize)
        cs = s_info.trade_contract_size
        if cs <= 0: cs = 1.0 # Seguridad para no dividir por cero
        
        # Delta es el cambio en el precio que produce la pérdida deseada
        delta = target_loss / (lot * cs)
        
        if side == mt5.ORDER_TYPE_BUY or side == "BUY":
            sl_final = price - delta
        else:
            sl_final = price + delta
            
        return round(sl_final, s_info.digits)
    except Exception as e:
        log(f"⚠️ Error get_bunker_sl: {e}")
        # Fallback ultra-seguro (SL astronómico)
        return round(price - 2000.0, 2) if side in [mt5.ORDER_TYPE_BUY, "BUY"] else round(price + 2000.0, 2)


def close_ticket(pos, reason="UNK"):
    # v18.5: LEY DE PROTECCIÓN DE CAPITAL - PROHIBIDO CERRAR EN NEGATIVO
    profit = pos.profit + getattr(pos, 'swap', 0.0) + getattr(pos, 'commission', 0.0)
    
    # Solo permitimos cierre en rojo si es una instrucción de pánico o cierre de mercado (decoy HARD/MERCADO)
    is_safe_close = profit > 0.01 or "HARD" in reason or "MERCADO" in reason or "PANIC" in reason
    
    if not is_safe_close:
        # log(f"🛡️ BLOQUEO DE CIERRE: Se intentó cerrar {pos.symbol} en negativo (${profit:.2f}). ABORTADO.")
        return None

    tick = mt5.symbol_info_tick(pos.symbol)
    if not tick: return None
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": pos.ticket,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "price": price,
        "magic": pos.magic,
        "comment": f"TITAN-CLOSE: {reason}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    # v15.43: Cronometraje de latencia para reporte final
    start_lat = time.perf_counter()
    res = mt5.order_send(req)
    end_lat = time.perf_counter()
    latency_ms = (end_lat - start_lat) * 1000
    MISSION_LATENCIES.append(latency_ms)
    global LAST_LATENCY, LAST_LATENCY_UPDATE
    LAST_LATENCY = latency_ms # Actualizar memoria global
    LAST_LATENCY_UPDATE = time.time() # Marcar frescura

    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"✅ CIERRE EXITOSO #{pos.ticket} [{reason}]: Profit {pos.profit:.2f} | {latency_ms:.1f}ms")
        
        # --- NOTIFICACIÓN TELEGRAM (CADA CIERRE) ---
        try:
            tg_token = os.getenv('TELEGRAM_TOKEN', '8217691336:AAFWduUGkO_f-QRF6MN338HY-MA46CjzHMg')
            tg_chat = os.getenv('TELEGRAM_CHAT_ID', '8339882349')
            if tg_token and tg_chat:
                emo = "🟩 WIN" if profit > 0 else "🟥 LOSS"
                msg = f"TITAN {emo}\nActivo: {pos.symbol}\nProfit: ${profit:.2f}\nRazón: {reason}\nEquidad: ${mt5.account_info().equity:.2f}"
                requests.get(f"https://api.telegram.org/bot{tg_token}/sendMessage?chat_id={tg_chat}&text={msg}", timeout=2)
        except: pass
        
        # ACTUALIZAR MEMORIA TÁCTICA (v7.46: Detectar WIN/LOSS real)
        LAST_CLOSE_TS[pos.symbol] = time.time()
        # Si el profit individual es positivo, es WIN. Si no, es LOSS.
        if pos.profit > 0:
            LAST_CLOSE_DIR[pos.symbol] = "WIN"
            CONSECUTIVE_LOSSES[pos.symbol] = 0
        else:
            LAST_CLOSE_DIR[pos.symbol] = "LOSS"
            # Guardar el tipo de operación que falló (SELL/BUY)
            LAST_CLOSE_TYPE[pos.symbol] = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
            CONSECUTIVE_LOSSES[pos.symbol] = CONSECUTIVE_LOSSES.get(pos.symbol, 0) + 1
            # v18.9.78: Aumentado a 3 minutos para evitar racha destructiva
            if CONSECUTIVE_LOSSES[pos.symbol] >= 2:
                COOL_DOWN_UNTIL[pos.symbol] = time.time() + 180 
        
        log(f"✅ CIERRE EXITOSO #{pos.ticket} [{reason}]: Profit {pos.profit:.2f} | {latency_ms:.1f}ms")
        
        # Guardar razón para re-entrada inmediata v18.9.106
        LAST_CLOSE_REASON[pos.symbol] = reason
        LAST_CLOSE_TYPE_REAL[pos.symbol] = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
    else:
        log(f"⚠️ Error cerrando #{pos.ticket}: {res.comment if res else 'None'}")
    return res

def update_sl(ticket, new_sl, comment=""):
    # v18.9.30: Seguridad total - Siempre blindamos si la posición existe.
    try:
        # Obtener datos frescos para PRESERVAR EL TP y evitar errores
        pos_tuple = mt5.positions_get(ticket=ticket)
        if not pos_tuple:
            log(f"⚠️ Update SL fallido: Ticket {ticket} no encontrado")
            return False
        pos = pos_tuple[0]
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": pos.symbol,
            "sl": float(new_sl),
            "tp": pos.tp, # CRÍTICO: Mantener el TP actual
            "comment": comment
        }
        
        # CRONOMETRAJE DE EJECUCIÓN (v15.42 REAL-MONEY READY)
        start_exec = time.perf_counter()
        res = mt5.order_send(request)
        end_exec = time.perf_counter()
        latency = (end_exec - start_exec) * 1000 # ms
        MISSION_LATENCIES.append(latency) # v15.43: Registro para reporte
        global LAST_LATENCY, LAST_LATENCY_UPDATE
        LAST_LATENCY = latency # Actualizar memoria global
        LAST_LATENCY_UPDATE = time.time()
        
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            if latency > 150: log(f"⚠️ ALTA LATENCIA: {latency:.1f}ms en #{ticket}")
        else:
            log(f"❌ Error MT5 ({res.retcode}): {res.comment}")
            log(f"⚠️ Error Blindaje #{ticket} a {new_sl}: {res.comment} (Ret: {res.retcode})")
            return False
        
        log(f"🛡️ BLINDAJE EXITOSO: #{ticket} a {new_sl} ({comment})")
        return True
    except Exception as e:
        log(f"⚠️ Excepción Blindaje: {e}")
        return False

def send_signal(symbol, mode, force=False, custom_tp=None):
    # v18.9.35: DESBLOQUEO INTELIGENTE - Solo bloquear si NO es una señal de alta confianza (>95%)
    # Esto permite que el bot haga Hedging o Rescate incluso en modo Vanguardia.
    adv = GLOBAL_ADVICE.get(symbol, {"conf": 0.0})
    is_high_conf = adv.get("conf", 0.0) >= 0.95
    
    if VANGUARDIA_LOCK and len(mt5.positions_get() or []) > 0 and not is_high_conf: 
        return
    if not hasattr(send_signal, "last_ts"): send_signal.last_ts = {}

    fname = os.path.join(MQL5_FILES_PATH, f"titan_signal_{symbol}.txt")
    cfg = ASSET_CONFIG.get(symbol, DEFAULT_CONFIG)
    
    ts = int(time.time())
    
    # TRUCO DE METRALLETA:
    # Si estamos forzando (Stacking), el timestamp DEBE ser distinto al anterior
    # para que el EA no lo descarte como "ya leído".
    if force:
        last = send_signal.last_ts.get(symbol, 0)
        ts = max(ts, last + 1)
    
    send_signal.last_ts[symbol] = ts # Guardar último generado
    
    # Intentar leer estado actual para preservar timestamp si no cambia
    try:
        if os.path.exists(fname):
            with open(fname, "r") as f:
                parts = f.read().strip().split('|')
                if len(parts) >= 5:
                    old_mode = parts[0]
                    old_lot = parts[1]
                    old_ts = int(parts[4])
                    
                    # MANTENER TIMESTAMP SOLO SI ES LO MISMO Y NO FORZAMOS
                    if not force and old_mode == mode and float(old_lot) == float(cfg['lot']):
                        ts = old_ts 
    except: pass

    tp_to_use = custom_tp if custom_tp is not None else cfg['tp']
    # v7.97: Decoy TP para evitar que el EA cierre en la entrada (0.0)
    if tp_to_use == 0 or tp_to_use is None: tp_to_use = 999999 
    sl_to_use = cfg['sl']

    # --- v15.0: AUTO-SURVIVAL LOT (Protección de Margen Proporcional) ---
    lot_to_use = cfg['lot']
    try:
        acc = mt5.account_info()
        if acc:
            # 0.03 necesita ~$110 (Seguro), 0.02 necesita ~$75, 0.01 necesita ~$35
            free = acc.margin_free
            if lot_to_use >= 0.03 and free < 110.0:
                lot_to_use = 0.02
                if free < 75.0: lot_to_use = 0.01
            elif lot_to_use >= 0.02 and free < 75.0:
                lot_to_use = 0.01
            elif free < 35.0:
                lot_to_use = 0.01 # Mínimo absoluto
            
            if lot_to_use < cfg['lot'] and ts % 15 < 1:
                log(f"🛡️ VANGUARDIA MARGEN: Lote {cfg['lot']} -> {lot_to_use} (Libre: ${free:.2f})")
    except: pass

    # --- ESCUDO ELÁSTICO v15.27 (ANTI-LATIGAZO) ---
    # Si detectamos spread alto, el SL debe ser MUCHO más amplio para no ser barridos.
    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            spread_pts = (tick.ask - tick.bid) / mt5.symbol_info(symbol).point
            if spread_pts > 100: # Ruido detectado
                sl_to_use = int(sl_to_use * 5.0) # v15.28: Multiplicador 5x (Aguante total 15,000 pts)
                log(f"🛡️ ESCUDO ELÁSTICO: SL ampliado 5x por Volatilidad/Spread ({spread_pts:.1f} pts)")
    except: pass

    # --- LÓGICA DE LOTE DINÁMICO v15.15 (SAFE-CALC) ---
    tick = mt5.symbol_info_tick(symbol)
    s_info = mt5.symbol_info(symbol)
    spread = 0
    if tick and s_info:
        spread = (tick.ask - tick.bid) / s_info.point
    
    # v15.46: LEY DE LA VELOCIDAD (Protección por Latencia)
    if LAST_LATENCY > 250:
        log(f"📡 BLOQUEO TOTAL: Latencia extrema ({LAST_LATENCY:.0f}ms). No se opera.")
        return 
    elif LAST_LATENCY > 100 and "BTC" not in symbol:  # BTC tiene latencia alta normal
        lot_to_use = 0.01
        log(f"\u26a0\ufe0f MODO SEGURO: Latencia alta ({LAST_LATENCY:.0f}ms). Bajando lote a 0.01.")
    
    final_lot = lot_to_use
    # v15.55: SE ELIMINA BLOQUEO DURO DE SPREAD.
    # Confiamos plenamente en el ESCUDO ELÁSTICO (SL Dinámico) restaurado.
    
    # v18.9.92: CALIBRACIÓN CORRECTA POR ACTIVO
    # Cada activo usa su propio spread actual (ya calculado arriba)
    # BTC tiene spreads normales de 200-500pts en fin de semana, umbral en 2000pts
    if "BTC" in symbol:
        skew_limit = 2000  # BTC: solo reducir si spread es anormal (>2000pts)
    else:
        skew_limit = 350   # Forex/Indices: umbral normal
    
    if spread > skew_limit:
        final_lot = 0.01
        log(f"\u26a0\ufe0f PROTECCIÓN SPREAD NUCLEAR ({spread:.1f} pts > {skew_limit}): Usando 0.01")
    else:
        final_lot = cfg['lot']  # Respetar lote configurado por el usuario
    payload = f"{mode}|{final_lot}|{sl_to_use}|{tp_to_use}|{ts}"
    if "EXPLORACIÓN" in mode or "EXPLORACIÓN" in str(force): # Inyeccion dinamica lote exploracion
        final_lot = 0.01
        payload = f"{mode}|{final_lot}|{sl_to_use}|{tp_to_use}|{ts}"

    if not atomic_write(fname, payload):
        try:
             with open(fname, "w") as f: f.write(payload)
        except: pass

def cargar_modelo_lstm():
    global modelo_lstm, modelo_lstm_btc
    if 'load_model' not in globals(): return False
    
    # 1. Cargar Cerebro ORO (Legacy/Main)
    if os.path.exists(MODEL_FILE_PATH):
        try:
            modelo_lstm = load_model(MODEL_FILE_PATH)
            log("✅ Modelo ORO Cargado")
        except: pass
    
    # 2. Cargar Cerebro BTC (v18.9.98)
    if os.path.exists(MODEL_BTC_FILE_PATH):
        try:
            modelo_lstm_btc = load_model(MODEL_BTC_FILE_PATH)
            log("✅ Modelo BTC Cargado")
        except: pass
    
    return True

def obtener_datos(symbol, num_ticks):
    # VELOCIDAD MÁXIMA: Analizar la vela actual (0) en formación
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, num_ticks)
    if rates is None or len(rates) == 0: return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    # Retornamos todo (O/H/L/C) para ATR
    return df

import joblib
import ta

SCALER_PATH_TEMPLATE = os.path.join(MQL5_FILES_PATH, 'scaler_{}.pkl')

def calculate_features(df):
    """ Calcula el set maestro de 9 dimensiones para la IA Titan """
    df = df.copy()
    
    # Eje 1: Anatomía (3)
    df['wick_up'] = (df['high'] - np.maximum(df['open'], df['close'])) / (df['close'] + 1e-9)
    df['wick_dn'] = (np.minimum(df['open'], df['close']) - df['low']) / (df['close'] + 1e-9)
    df['body_size'] = np.abs(df['close'] - df['open']) / (df['close'] + 1e-9)
    
    # Eje 2: Momentum (2)
    df['log_ret'] = np.log(df['close'] / (df['close'].shift(1) + 1e-9)).fillna(0)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14).fillna(50)
    
    # Eje 3: Volatilidad y Estructura (4)
    # v18.9.86: Normalización Universal de Magnitud (Fijar escala de ORO como base)
    df['atr_rel'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14) / (df['close'] + 1e-9)
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_pct'] = (df['close'] - bb.bollinger_lband()) / (bb.bollinger_hband() - bb.bollinger_lband() + 1e-9)
    df['vol_rel'] = df['tick_volume'] / (df['tick_volume'].rolling(20).mean() + 1e-9)
    
    # MACD Normalizado: De lo contrario, BTC (60k) satura el modelo entrenado en Oro (2k)
    macd = ta.trend.MACD(close=df['close'])
    df['macd_diff'] = (macd.macd_diff().fillna(0) / (df['close'] + 1e-9)) * 2600.0

    # Features Extra para compatibilidad (v18.9.82)
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14).fillna(25)
    df['bb_width'] = (bb.bollinger_hband() - bb.bollinger_lband()) / (bb.bollinger_mavg() + 1e-9)
    df['dist_ema20'] = (df['close'] - df['close'].ewm(span=20).mean()) / (df['close'] + 1e-9)

    df.dropna(inplace=True)
    df.replace([np.inf, -np.inf], 0, inplace=True)
    return df

# Orden Maestro de Entrenamiento (9-D)
MASTER_FEATURES = ['log_ret', 'rsi', 'atr_rel', 'bb_pct', 'macd_diff', 'wick_up', 'wick_dn', 'body_size', 'vol_rel']

# El sistema ahora usa detección dinámica de columnas por scaler (v18.9.82)

def predecir(symbol):
    global modelo_lstm, modelo_lstm_btc
    
    # Seleccionar modelo por activo
    modelo = modelo_lstm_btc if "BTC" in symbol else modelo_lstm
    if modelo is None: return "NONE", 0.0, 0, 0.5, 0.0
    
    try:
        # 1. Cargar Scaler
        scaler_path = SCALER_PATH_TEMPLATE.format(symbol)
        if not os.path.exists(scaler_path):
            scaler_path = SCALER_PATH_TEMPLATE.format("XAUUSDm")
        
        scaler = joblib.load(scaler_path)
        
        # 2. Verificar compatibilidad con el Modelo (9-D)
        n_scaler = getattr(scaler, "n_features_in_", 0)
        if n_scaler != 9:
            scaler = joblib.load(SCALER_PATH_TEMPLATE.format("XAUUSDm"))
        
        # 3. Datos y Features
        df = obtener_datos(symbol, 350)
        if df.empty or len(df) < LOOKBACK_PERIOD + 10: return "NONE", 0.0, 0, 0.5, 0.0
        
        df = calculate_features(df)
        if len(df) < LOOKBACK_PERIOD: return "NONE", 0.0, 0, 0.5, 0.0

        # 4. Inferencia Protegida
        last_features = df[MASTER_FEATURES].tail(LOOKBACK_PERIOD)
        scaled_X = scaler.transform(last_features)
        X_final = scaled_X.reshape(1, LOOKBACK_PERIOD, 9)
        
        try:
            preds = modelo_lstm.predict(X_final, verbose=0)
            prob = float(preds[0][0])
        except Exception as tf_err:
            # v18.9.91: MODO TECNICO PURO (Fallback para BTC/US30 cuando IA falla)
            log(f"🔧 IA FALLBACK TECNICO ({symbol}): {str(tf_err)[:40]}")
            return _technical_fallback(symbol, df)

        # 5. Interpretación
        conf = abs(prob - 0.5) * 2
        sig = "BUY" if prob > 0.55 else ("SELL" if prob < 0.45 else "HOLD")
        
        if conf > 0.88: conf = min(0.99, conf * 1.05)
        
        return sig, conf, df['rsi'].iloc[-1], prob, 0.0

    except Exception as e:
        log(f"🧠 Predict Err {symbol}: {e}")
        # v18.9.91: Siempre intentar fallback técnico en lugar de retornar NONE
        try:
            df = obtener_datos(symbol, 150)
            if not df.empty:
                df = calculate_features(df)
                return _technical_fallback(symbol, df)
        except:
            pass
        return "NONE", 0.0, 0, 0.5, 0.0

def _technical_fallback(symbol, df):
    """ v18.9.91: Señal 100% técnica cuando la IA no puede predecir """
    try:
        rsi = df['rsi'].iloc[-1]
        bb_pct = df['bb_pct'].iloc[-1]
        macd = df['macd_diff'].iloc[-1]
        log_ret = df['log_ret'].iloc[-1]
        
        score = 0.0
        # RSI extremos
        if rsi < 35: score += 0.30  # Sobreventa = Compra
        elif rsi > 65: score -= 0.30  # Sobrecompra = Venta
        # Posición en Bollinger
        if bb_pct < 0.20: score += 0.25  # Piso Bollinger
        elif bb_pct > 0.80: score -= 0.25  # Techo Bollinger
        # MACD
        if macd > 0: score += 0.15
        else: score -= 0.15
        # Momentum reciente
        if log_ret > 0: score += 0.10
        else: score -= 0.10
        
        conf = min(abs(score) * 1.2, 0.88)  # Max 88% en modo técnico
        sig = "BUY" if score > 0.20 else ("SELL" if score < -0.20 else "HOLD")
        prob = 0.5 + (score * 0.4)  # Mapear a probabilidad
        
        return sig, conf, rsi, prob, 0.0
    except:
        return "NONE", 0.0, 50, 0.5, 0.0


# ============ DASHBOARD ============
def print_dashboard(report_list, elapsed_str="00:00:00"):
    # Construir todo en buffer y escribir de un golpe (CERO parpadeo)
    K = "\033[K"  # Limpiar resto de cada linea
    lines = []
    
    with state_lock:
        active = mission_state.get("active", False)
        if active:
            st_line = f" ESTADO:  🟢 ACTIVA ({mission_state.get('symbol', 'MIX')}) | ⏱️ {elapsed_str}"
        elif STATE.get("auto_pilot", False):
            st_line = f" ESTADO:  🚁 STANDBY (AUTO) | ⏱️ 00:00:00"
        else:
            st_line = f" ESTADO:   READY 🛰️ | ⏱️ 00:00:00"
        
        # v18.9.87: VIGILIA DE MARGEN (Fix 0.0% weekend)
        acc = mt5.account_info()
        margin_pct = acc.margin_level if (acc and acc.margin_level > 0) else 2000.0
        conn_status = "🟢 OK"
        if margin_pct < 40: conn_status = f"☢️ MARGEN CRÍTICO ({margin_pct:.1f}%)"
        elif margin_pct < 100: conn_status = f"⚠️ MARGEN BAJO ({margin_pct:.1f}%)"
        elif LAST_LATENCY > 200: conn_status = f"🔴 LAG ({LAST_LATENCY:.0f}ms)"
        
        st_line += f" | 📡 {conn_status}"
        pnl = STATE.get("pnl", 0.0)
        if not isinstance(pnl, (int, float)): pnl = 0.0
        
        target = mission_state.get("target", 0.0)
        if not isinstance(target, (int, float)): target = 0.0
        
        eq = float(mission_state.get("start_equity", 0.0)) + pnl
        
        try:
            max_p = float(STATE.get("max_profit", pnl))
        except:
            max_p = pnl
    
    # Validar que pnl sea float para evitar crashes en el f-string
    if not isinstance(pnl, (int, float)) or math.isnan(pnl): pnl = 0.0
    if not isinstance(max_p, (int, float)) or math.isnan(max_p): max_p = 0.0
    
    limit_drop = abs(MAX_SESSION_LOSS)

    lines.append("="*75)
    lines.append(f" 🛡️ TITAN VANGUARDIA v18.9.27 | VIGILIA EXTREMA | PORT: {PORT}")
    lines.append("="*75)
    lines.append(st_line)
    # v18.9.113: FIX ATRIBUTO SYMBOL
    target_tick_sym = "XAUUSDm"
    tick = mt5.symbol_info_tick(target_tick_sym)
    if not tick or (time.time() - tick.time > 60):
        target_tick_sym = "BTCUSDm"
        tick = mt5.symbol_info_tick(target_tick_sym)
    
    current_spread = tick.ask - tick.bid if tick else 0.0
    s_info_disp = mt5.symbol_info(target_tick_sym) if tick else None
    spread_pts = 0
    if tick and s_info_disp and hasattr(s_info_disp, 'point') and s_info_disp.point > 0:
        spread_pts = current_spread / s_info_disp.point



    
    # Contar racha en MISSION_HISTORY
    wins_today = sum(1 for m in list(MISSION_HISTORY)[-20:] if m.get('type') == 'WIN')

    lines.append(f" PnL:     ${pnl:.2f} / Meta: ${target:.0f} | RACHA: 🔥 {wins_today}")
    lines.append(f" TRAIL:   Max ${max_p:.2f} (Lim Drop: ${limit_drop:.2f})")
    lines.append(f" BALAS:   {STATE['bullets']} / {MAX_BULLETS} | SPREAD: ⚡ {spread_pts:.0f}")
    
    # v15.63: VELOCIDAD DEL DINERO & TICKS
    # Calcular volatilidad simple (High - Low de ultimos 20 ticks guardados)
    ph = STATE.get("price_history", [])
    vol_usd_min = "CALC..."
    tick_speed = 0.0
    if len(ph) > 10:
        range_p = max(ph) - min(ph)
        # 1.0 de precio = 100 puntos = $1.00 USD PnL con 0.01
        vol_usd = range_p * 1.0 
        vol_usd_min = f"${vol_usd*12:.2f}/m" # Factor 12 para estimación minuto
        
        # Calcular Ticks/seg si es posible
        ts_list = STATE.get("price_timestamps", [])
        if len(ts_list) > 2:
            time_span = ts_list[-1] - ts_list[0]
            if time_span > 0:
                tick_speed = len(ts_list) / time_span

    lines.append(f" EQUIDAD: ${eq:.2f} | VELOCIDAD: 💸 {vol_usd_min} | TICKS: 📈 {tick_speed:.1f}/s")
    
    # --- v15.25: CALENDARIO SIEMPRE VISIBLE ---
    m_warn = get_market_warning()
    market_line = m_warn if m_warn else "🟢 MERCADO ABIERTO (Sesión Normal)"
    lines.append(f" MARKET:  {market_line}")

    lines.append("-" * 75)
    lines.append(f" {'ACTIVO':<10} | {'SEÑAL':<8} | {'CONF.':<8} | {'IA':<5} | {'RSI':<5} | {'LOTE':<6} | {'ESTADO'}")
    lines.append("-" * 75)
    
    for i in report_list:
        lot = ASSET_CONFIG.get(i['symbol'], DEFAULT_CONFIG)["lot"]
        symbol = i['symbol']
        signal = i['signal']
        confidence = i['confidence']
        ai_prob = i.get('ai', 0.5)
        rsi_val = i.get('rsi', 50)
        last_ia = int(ai_prob * 100)
        active_mission = STATE.get("active", False) # v16.0
        
        display_sig = signal
        if confidence < 0.01 or signal == "WAIT":
             display_sig = "HOLD"
        
        # v16.0: Visibilidad de señal en READY
        if not mission_state.get("active", False) and display_sig != "HOLD":
             display_sig = f"READY:{display_sig}"

        try:
            from colorama import Fore, Style
            sig_col = Fore.GREEN if "BUY" in display_sig else (Fore.RED if "SELL" in display_sig else Fore.YELLOW)
            reset_style = Style.RESET_ALL
        except ImportError:
            sig_col = ""
            reset_style = ""
        
        estado_icon = "🚀" if display_sig in ["BUY", "SELL"] else "💤"
        if "HOLD" in display_sig: estado_icon = "✊"

        # Safe int/float conversion for dashboard
        try:
            rsi_display = int(rsi_val) if (rsi_val is not None and not math.isnan(rsi_val)) else 50
        except:
            rsi_display = 50

        lines.append(f" {symbol:<10} | {sig_col}{display_sig:<8}{reset_style} | {confidence:>5.1%}   | {last_ia:>3}%  | {rsi_display:>3}   | {str(lot):<6} | {estado_icon}")
    
    lines.append("-" * 75)
    for l in LOG_BUFFER:
        lines.append(f" > {l}")
    lines.append("="*75)
    
    # Escribir TODO de un golpe: cursor home + cada linea con clear-to-end + limpiar abajo
    try:
        output = "\033[H" + "\n".join(line + K for line in lines) + "\n\033[J"
        sys.stdout.write(output)
        sys.stdout.flush()
    except:
        pass

# ============ CORE LOOP ============
# --- GENERACIÓN DE REPORTE CON FIX DE TIMEZONE ---
def generate_report(start_ts):
    """ Genera un reporte detallado al finalizar la misión hackeando el historial de MT5 """
    try:
        if not start_ts: return
        now_ts = time.time()
        # Usar timestamps directos para evitar líos de Timezone (UTC vs Local)
        deals = mt5.history_deals_get(int(start_ts - 10), int(now_ts + 60))
        
        now = datetime.now()
        total_pnl, sum_wins, sum_losses = 0.0, 0.0, 0.0
        wins, losses, count = 0, 0, 0
        best_trade, worst_trade = 0.0, 0.0
        
        # v18.9.21: RECUENTO DE AUTORÍA (Bot vs Humano)
        bot_closes = 0
        manual_closes = 0
        sl_tp_closes = 0 # Cierres por SL/TP físicos del EA

        # Por Símbolo
        stats_sym = {}

        log(f"📊 REPORTE DE MISIÓN FINALIZADA")
        
        if deals is None:
            log("❌ Error al obtener historial de MT5")
            return

        if len(deals) == 0:
            log("⚠️ No se encontraron operaciones CERRADAS para el reporte.")
            return
        
        for d in deals:
            # FILTRO DE TIEMPO CON TOLERANCIA (Timezone Fix)
            # Solo trades que empezaron DESPUÉS de la misión (con 5s de margen)
            if d.time < (start_ts - 5): continue 
            
            # entry: 0=IN (Abriendo), 1=OUT (Cerrando), 2=INOUT (Reversa)
            if d.entry == 0: continue 

            profit = d.profit + d.swap + d.commission
            # Filtrar depósitos (balance operations)
            if d.symbol == "": continue 

            count += 1
            total_pnl += profit
            
            # Global Stats
            if profit >= 0:
                wins += 1
                sum_wins += profit
                if wins == 1 or profit > best_trade: best_trade = profit
            else:
                losses += 1
                sum_losses += profit
                if losses == 1 or profit < worst_trade: worst_trade = profit

            # Symbol Stats
            sym = d.symbol
            if sym not in stats_sym: stats_sym[sym] = {'pnl':0.0, 'count':0}
            stats_sym[sym]['pnl'] += profit
            stats_sym[sym]['count'] += 1

            # v18.9.21: Auditoría de Razón de Cierre
            # reason 0: CLIENT (Manual), 3: EXPERT (Bot), 4: SL, 5: TP
            d_reason = getattr(d, 'reason', -1)
            if d_reason == 3: bot_closes += 1
            elif d_reason == 0: manual_closes += 1
            elif d_reason in [4, 5]: sl_tp_closes += 1

        if count == 0:
            log("⚠️ Sesión finalizada sin operaciones cerradas.")
            best_trade = 0.0
            worst_trade = 0.0

        # Cálculos Finales
        avg_win = sum_wins / wins if wins > 0 else 0.0
        avg_loss = sum_losses / losses if losses > 0 else 0.0
        win_rate = (wins / count * 100) if count > 0 else 0.0
        
        # --- v15.43: AUDITORÍA DE LATENCIA ---
        avg_lat = sum(MISSION_LATENCIES) / len(MISSION_LATENCIES) if MISSION_LATENCIES else 0.0
        max_lat = max(MISSION_LATENCIES) if MISSION_LATENCIES else 0.0

        # --- REGISTRAR RESUMEN EN LOG ---
        dur_msg = str(timedelta(seconds=int(time.time() - start_ts)))
        log(f"🏁 MISIÓN: PnL ${total_pnl:.2f} | Trades: {count} | WR: {win_rate:.1f}% | Dur: {dur_msg}")
        log(f"🎮 MANDO: BOT {bot_closes} | COMANDANTE {manual_closes} | SL/TP {sl_tp_closes}")
        log(f"📡 LATENCIA: Avg {avg_lat:.1f}ms | Max {max_lat:.1f}ms (Broker Audit)")
        
        for s, data in stats_sym.items():
            log(f"  • {s}: ${data['pnl']:.2f} ({data['count']} ops)")
        
        # --- GUARDAR HISTORIAL DETALLADO ---
        duration_str = str(timedelta(seconds=int(time.time() - start_ts)))
        item = {
            "symbol": "MISION", # v15.33: Literal corregido (fijado "MISION")
            "type": "WIN" if total_pnl >= 0 else "LOSS",
            "profit": total_pnl,
            "win_rate": win_rate,
            "trades": count,
            "time": now.strftime("%d/%m %H:%M"), # Formato COMPATIBLE APK RESUMEN
            # Nuevos campos para App Detallada
            "duration": duration_str,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "bot_ratio": f"{bot_closes}/{count}" if count > 0 else "0/0",
            "manual_trades": manual_closes
        }
        MISSION_HISTORY.append(item)
        save_history() # Atómico v15.11
    except Exception as e:
        log(f"❌ Error Reporte: {e}")

def start_mission(symbol="ORO/VANGUARDIA", target_profit=50.0):
    # --- RESET ATÓMICO v15.37 ---
    global mission_state, MISSION_LATENCIES
    MISSION_LATENCIES = [] # v15.43: Limpiar rastro de ms al iniciar
    log("🔄 PREPARANDO MESA: Reiniciando misión...")
    # Limpieza visual suave (ANSI) en lugar de os.system que bloquea
    print("\033[H\033[J", end="")


    # Borrar archivo físico para evitar resurrecciones de PnL
    if os.path.exists(MISSION_FILE_PATH):
        try: os.remove(MISSION_FILE_PATH)
        except: pass

    # Asegurar que las posiciones se liquidaron antes de capturar equidad
    time.sleep(0.5) 
    
    with state_lock:
        # v15.33: NO usar .clear() para no romper el hilo principal
        equity_base = float(get_equity())
        mission_state["active"] = True
        mission_state["symbol"] = symbol
        mission_state["start_equity"] = equity_base
        mission_state["start_time"] = time.time()
        mission_state["target"] = float(target_profit)
        mission_state["target_profit"] = float(target_profit)
        mission_state["max_profit"] = 0.0
        mission_state["last_pnl"] = 0.0
        
        # Resetear variables de estado global
        STATE["pnl"] = 0.0
        STATE["daily_profit"] = 0.0
        STATE["max_profit"] = 0.0
        STATE["bullets"] = 0
        
    save_mission_state()
    log(f"🚀 MISIÓN INICIADA: {symbol if symbol else 'GLOBAL'} | Meta: ${target_profit} | Base: ${equity_base:.2f}")

def stop_mission():
    with state_lock:
        mission_state["active"] = False
        mission_state["symbol"] = None
        mission_state["start_time"] = 0
        mission_state["start_equity"] = 0.0
        mission_state["max_profit"] = 0.0
        mission_state["last_pnl"] = 0.0
        STATE["pnl"] = 0.0
        STATE["daily_profit"] = 0.0 # v18.9.25: Limpieza profunda para evitar "mareos"
        STATE["max_profit"] = 0.0
        STATE["bullets"] = 0
    save_mission_state()
    
    # --- 🛡️ PROTOCOLO DE CIERRE TOTAL (HARD QUIT) ---
    # Cerramos absolutamente todo lo que esté abierto en nuestros símbolos
    positions = mt5.positions_get()
    if positions:
        for p in positions:
            if p.symbol in SYMBOLS:
                close_ticket(p, "MISSION_END")
                log(f"🛑 CIERRE FIN DE MISIÓN: {p.symbol} ({p.ticket})")
    
    # Notificar a los archivos de señal para que el EA se detenga
    for sym in SYMBOLS:
        send_signal(sym, "NONE", force=True)
        
    log("🏁 MISIÓN FINALIZADA | EA Restaurado y Posiciones Cerradas.")

def process_symbol_task(sym, active, mission_state):
    """ Tarea individual para cada activo en paralelo """
    global LAST_LATENCY_UPDATE # v15.50: Fix Scope Error
    try:
        now = time.time()
        now_dt = datetime.fromtimestamp(now)
        acc = mt5.account_info() # v18.8.1: Definición externa proactiva
        
        # v18.9.93: GUARDIA MÍNIMA DE CAPITAL - INQUEBRANTABLE
        if acc:
        # --- FAILSAFE DE SUPERVIVENCIA (Equidad Mínima) ---
            pnl = acc.equity - mission_state.get("start_equity", acc.equity)
            if acc.equity < 10.0: # MODO DE SUPERVIVENCIA EXTREMA ACTIVADO (bajado a 10.0)
                if now % 30 < 1: log(f"🚨 CUENTA CONGELADA: Equity ${acc.equity:.2f} < mínimo $10.0. Bot en pausa total.")
                time.sleep(1); return {"symbol": sym, "signal": "HOLD", "confidence": 0.0, "ai": 0.5, "rsi": 50,
                            "lot": 0.01, "state": "❄️", "profit": 0.0, "bb_pos": 0.5, "m5_trend": "⚪", "h1_trend": "NONE"}
        
        n_balas_reales = 0
        bb_pos = 0.5
        
        # --- INICIALIZACIÓN DE CONTEXTO TÉCNICO PROACTIVA (v15.9) ---
        m5_trend_dir = "NEUTRAL"
        m5_trend_label = "⚪"
        council_sig = "HOLD"
        ia_dir = "NONE"
        skip_m5_veto = False
        ia_override = False
        votos_buy = 0
        votos_sell = 0
        razones = []
        
        with state_lock:
            positions = mt5.positions_get()
            positions = positions if positions else []
            positions_count = len([p for p in positions if p.symbol == sym])
            n_balas_reales = positions_count 
        
        # --- CALCULO PREVIO DE PNL (v8.0.4) ---
        pos_list = [p for p in positions if p.symbol == sym]
        sym_pnl = sum(p.profit + getattr(p, 'swap', 0.0) + getattr(p, 'commission', 0.0) for p in pos_list)
        
        # 0. Captura de Datos
        df = obtener_datos(sym, 100)
        # --- INICIALIZACIÓN DE VARIABLES DE CICLO (v7.14) ---
        sig = "HOLD"
        conf = 0.0
        raw_prob = 0.5
        is_sniper = False
        is_inverse = False
        should_fire = False
        trigger_type = "NORMAL"
        surf_tp = None
        target_sig = "HOLD"
        contragolpe_active = False
        bb_pos = 0.5 # Valor neutro inicial
        is_oracle_signal = False # v18.9.119: Flag Maestro de Bypass

        
        # v18.8: El conteo ya se realizó al inicio de la tarea técnica.

        # 1. Obtener datos
        df = obtener_datos(sym, 100) # Changed from get_data to obtener_datos to match original
        if df.empty: return None 

        tick = mt5.symbol_info_tick(sym)
        if not tick: return None
        
        # Predecir (original location, now re-assigning after initial values)
        # This line needs to be adjusted to use the new `get_advice` or `predecir`
        # Assuming `predecir` is the function that provides these values.
        # The user's snippet implies `get_advice` but the original code uses `predecir`.
        # I will keep `predecir` as it's in the original code, but ensure `sig`, `conf`, `raw_prob` are updated.
        sig_pred, conf_pred, rsi_val_pred, raw_prob_pred, adx_val = predecir(sym)
        LAST_PROBS[sym] = raw_prob_pred
        raw_prob = raw_prob_pred  
        
        # --- ORACULO DE BINANCE (OVERRIDE MAESTRO LEAD-LAG) ---
        try:
            if os.path.exists("titan_oracle_signal.json"):
                with open("titan_oracle_signal.json", "r") as f:
                    oracle_data = json.load(f)
                    # v18.9.119: TTL aumentado a 10s para fin de semana
                    if time.time() - oracle_data["timestamp"] < 10.0:
                        if oracle_data["symbol"] == sym or sym == "BTCUSDm":
                            sig_pred = oracle_data["signal"]
                            conf_pred = 1.0 
                            is_oracle_signal = True
                            log(f"⚡ ORÁCULO ACTIVO: {sig_pred} ({oracle_data['reason']})")
        except: pass
        
        # v18.9.3: RECONEXIÓN CRÍTICA - Asignar señal de IA al ciclo
        sig = sig_pred
        conf = conf_pred
        rsi_val = rsi_val_pred 
        curr_price = tick.bid


        # --- GESTIÓN DE RIESGO ADAPTATIVA v18.9.103 (Ubicación Proactiva) ---
        balance = acc.balance if acc else 0
        current_max_bullets, smart_lot = get_adaptive_risk_params(balance, conf, rsi_val, sym)
        with state_lock:
            # Actualizamos el lote global para este símbolo para que todos los bloques lo usen
            ASSET_CONFIG[sym]["lot"] = smart_lot
        
        # TP Dinámico v11.2: SIN TP FIJO - El trailing stop del EA maneja la salida
        # INCIDENTE: TP de 2000 pts ($6) cerraba trades que podían dar $10+
        # Ahora surf_tp = None → usa cfg['tp'] = 999999 (decoy que nunca se alcanza)
        surf_tp = None  # TRAILING ONLY MODE 🔒

        # Momentum (original logic)
        # Momentum (v7.56: Vista de 5 minutos para estabilidad)
        rates_mom = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 5) 
        start_mom = rates_mom[0]['open'] if rates_mom is not None and len(rates_mom) > 0 else tick.bid
        delta = tick.bid - start_mom

        # --- CÁLCULO DE BANDAS DE BOLLINGER TÁCTICAS (20, 2) ---
        df_ta = df.copy() # Use df_ta as in original
        indicator_bb = ta.volatility.BollingerBands(close=df_ta['close'], window=20, window_dev=2)
        upper_band = indicator_bb.bollinger_hband().iloc[-1]
        lower_band = indicator_bb.bollinger_lband().iloc[-1]
        mid_band = indicator_bb.bollinger_mavg().iloc[-1] # mid_band was used in original, keep it
        bb_pos = (tick.bid - lower_band) / max(upper_band - lower_band, 0.01)
        
        # --- PROTOCOLO SNIPER v7.16.5 (Blindaje ADX) ---
        if adx_val < 30: # Evitar Sniper en tendencias fuertes (v7.16.5)
            if curr_price >= (upper_band - 0.05) and delta < -0.2:
                sig = "SELL"; conf = 0.98; is_sniper = True
                log(f"🎯 SNIPER SELL: ¡EMBOSCADA EN TECHO! {sym}")
            elif curr_price <= (lower_band + 0.05) and delta > 0.2:
                sig = "BUY"; conf = 0.98; is_sniper = True
                log(f"🎯 SNIPER BUY: ¡EMBOSCADA EN SUELO! {sym}")

        # --- DETERMINACIÓN DE SEÑAL Y BLOQUEOS ---
        pos_list = [p for p in positions if p.symbol == sym]
        curr_dir = "NONE"
        if len(pos_list) > 0:
            p0 = pos_list[0]
            curr_dir = "BUY" if p0.type in [mt5.POSITION_TYPE_BUY, mt5.ORDER_TYPE_BUY] else "SELL"
        
        # v14.0: Pre-calcular is_contrarian para filtros de seguridad
        # (Se actualizará después de la decisión final de la IA)

        # --- CONSEJO DE GUERRA v7.68 ---
        if not is_sniper:
            global LAST_INSTINTO_LOG
            
            # === RECOPILAR VOTOS DE MÚLTIPLES FUENTES ===
            votos_buy = 0
            votos_sell = 0
            razones = []
            
            # VOTO 1: IA (v11.1: PESO ESCALONADO según confianza real)
            # INCIDENTE: Con peso binario (>53% = 5.0), una señal de 53% (moneda al aire)
            # obtuvo peso máximo y causó un BUY que perdió -$50.84.
            # Ahora el peso es PROPORCIONAL a la confianza:
            if conf_pred > 0.60:
                peso_ia = 5.0   # Confianza REAL del LSTM (raro pero poderoso)
            elif conf_pred > 0.55:
                peso_ia = 3.0   # Algo de señal
            else:
                peso_ia = 1.0   # Ruido, básicamente moneda al aire
            ia_dir = "NONE"
            if sig_pred == "BUY":
                votos_buy += peso_ia
                razones.append(f"IA:BUY({conf_pred*100:.0f}%)")
                ia_dir = "BUY"
            elif sig_pred == "SELL":
                votos_sell += peso_ia
                razones.append(f"IA:SELL({conf_pred*100:.0f}%)")
                ia_dir = "SELL"
            
            # VOTO 2: Momentum 1 min (delta corto)
            rates_1m = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
            if rates_1m is not None and len(rates_1m) >= 2:
                delta_1m = rates_1m[-1]['close'] - rates_1m[-2]['close']
                if delta_1m > 0.15:
                    votos_buy += 2.0; razones.append("M1:↑")  # v11.0: +2.0 (lo que pasa AHORA)
                elif delta_1m < -0.15:
                    votos_sell += 2.0; razones.append("M1:↓")  # v11.0: +2.0
            
            # VOTO 3: Tendencia 5 min (delta largo) - v11.0: Reducido a contexto
            if delta > 0.30:
                votos_buy += 0.5; razones.append("M5:↑↑")  # v11.0: de 1.5 a 0.5
            elif delta > 0.10:
                votos_buy += 0.3; razones.append("M5:↑")
            elif delta < -0.30:
                votos_sell += 0.5; razones.append("M5:↓↓")  # v11.0: de 1.5 a 0.5
            elif delta < -0.10:
                votos_sell += 0.3; razones.append("M5:↓")
            
            # VOTO 4: Posición vs EMA20 (tendencia de fondo) - v11.0: Reducido
            ema20_val = df_ta['close'].ewm(span=20).mean().iloc[-1]
            if curr_price > ema20_val + 0.5:
                votos_buy += 1.0; razones.append("EMA:↑")  # v11.0: de 1.5 a 1.0
            elif curr_price < ema20_val - 0.5:
                votos_sell += 1.0; razones.append("EMA:↓")  # v11.0: de 1.5 a 1.0
            
            # VOTO 5: RSI (zonas extremas = reversión probable)
            if rsi_val < 35:
                votos_buy += 1; razones.append("RSI:sobreventa")
            elif rsi_val > 65:
                votos_sell += 1; razones.append("RSI:sobrecompra")
            
            # VOTO 6: Posición en Bollinger (v18.7.2: REVERSIÓN EXTREMA) 
            # Permitimos votos de reversión en extremos sin importar la tendencia M5
            # para alimentar el 'Modo Contragolpe' del usuario.
            if bb_pos > 0.82: 
                votos_sell += 1.2; razones.append("BB:TECHO_LOCO")
            elif bb_pos < 0.18:
                votos_buy += 1.2; razones.append("BB:PISO_LOCO")
            
            # VOTO 7: TENDENCIA M5 (Peso Adaptativo v7.68 = 4.0!)
            rates_m5_data = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 30)
            if rates_m5_data is not None and len(rates_m5_data) >= 25:
                import pandas as pd_m5
                df_m5_v2 = pd_m5.DataFrame(rates_m5_data)
                ema9_m5 = df_m5_v2['close'].ewm(span=9).mean().iloc[-1]
                ema21_m5 = df_m5_v2['close'].ewm(span=21).mean().iloc[-1]
                m5_diff = ema9_m5 - ema21_m5
                
                m5_trend_label = "⚪"
                if m5_diff > 0.3: 
                    votos_buy += 1.0; razones.append("M5T:🟢🟢"); m5_trend_dir = "BUY"; m5_trend_label = "🟢🟢"  # v11.0: de 4.0 a 1.0
                elif m5_diff < -0.3: 
                    votos_sell += 1.0; razones.append("M5T:🔴🔴"); m5_trend_dir = "SELL"; m5_trend_label = "🔴🔴"  # v11.0: de 4.0 a 1.0
            else:
                m5_trend_label = "⚪"
            
            # VOTO 8: ESTRUCTURA DE PRECIO (M1) v7.89: Más sensible (2 velas) ---
            if len(df) >= 5:
                v_act = df.iloc[-1]['close'] - df.iloc[-1]['open']
                v_prev = df.iloc[-2]['close'] - df.iloc[-2]['open']
                
                if v_act > 0 and v_prev > 0:
                    votos_buy += 2.0; razones.append("2V:🟢")  # v11.0: estructura de precio = clave
                elif v_act < 0 and v_prev < 0:
                    votos_sell += 2.0; razones.append("2V:🔴")  # v11.0: estructura de precio = clave

            # === VETO MAESTRO JERÁRQUICO v7.70 (Agilidad Mejorada) ===
            # Regla: Si el precio está en contra de la EMA, solo permitimos el trade
            # si la vela actual YA muestra el color de la dirección (giro iniciado).
            ema20_m1 = df_ta['close'].ewm(span=20).mean().iloc[-1]
            precio_sobre_ema = curr_price > (ema20_m1 + 0.05)
            precio_bajo_ema = curr_price < (ema20_m1 - 0.05)
            
            ultima_vela_roja = df.iloc[-1]['close'] < df.iloc[-1]['open']
            ultima_vela_verde = df.iloc[-1]['close'] > df.iloc[-1]['open']

            block_council = False
            block_council_reason = ""

            # === NÚCLEO DE CÁLCULO TITAN v7.91 ===
            # Extraer tendencias macro para ponderación
            rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 10)
            h1_trend = "NONE"
            if rates_h1 is not None and len(rates_h1) > 0:
                h1_trend = "BUY" if rates_h1['close'][-1] > pd.Series(rates_h1['close']).ewm(span=20).mean().iloc[-1] else "SELL"
            
            # v17.6: REGLA DE ORO - PROHIBIDO IR CONTRA LA CORRIENTE
            # v18.9.85: EXCEPCIÓN IA (Alta Confianza > 80% Bypassea Tendencia)
            conf_ia = conf # de predecir()
            skip_current_veto = conf_ia >= 0.80
            
            if not skip_current_veto:
                if m5_trend_dir == "SELL": 
                    votos_buy = 0; razones.append("VETO:M5_BAJISTA")
                elif m5_trend_dir == "BUY": 
                    votos_sell = 0; razones.append("VETO:M5_ALCISTA")
            else:
                razones.append("IA_OVERRIDE:⚡")
            
            tot = votos_buy + votos_sell
            if not is_oracle_signal:
                if tot > 0: 
                    s_buy = votos_buy / tot
                    s_sell = votos_sell / tot
                    if s_buy > 0.58: # Umbral más alto para mayor rigor
                        sig = "BUY"; conf = min(0.5 + s_buy*0.5, 0.98)
                    elif s_sell > 0.58:
                        sig = "SELL"; conf = min(0.5 + s_sell*0.5, 0.98)
                    else: sig = "HOLD"; conf = 0.0
                else: 
                    sig = "HOLD"; conf = 0.0
            else:
                # v18.9.122: Si es señal de Oráculo, NO tocar 'sig' ni 'conf'
                pass

            
            # v15.6: Capturar señal pura de indicadores antes de influencia IA
            council_sig = sig

            # v18.9.42: Override desactivado para purga de errores. 
            ia_override = False
            # El LSTM solo actúa como un voto más, no manda sobre el sistema.

            # v18.9.47: Sincronización de IA Externa para Verificación de Conflictos
            ai_res = STATE.get('ai_results', {}).get(sym, {})
            ai_d = ai_res.get('dir', "NONE")
            ai_c = ai_res.get('conf', 0.0)
            
            # Bonus removed in v18.9.41 to show REAL AI CONFIDENCE to the user.

            # === ESTRATEGIA MIRROR v8.3 (HAY QUE MOVER ESTO!) ===
            req_conf = 0.70 # Acción rápida para la prueba inversa

            # Veto Maestro -> Ahora filtrado por el nuevo conf calculado
            if conf < req_conf:
                block_council = True; block_council_reason = f"WAIT ({conf*100:.0f}% < {req_conf*100:.0f}%)"
            
            # VETOS DE M5/H1: Solo informativos para scalper puro
            log_veto = ""
            # VETO DE TENDENCIA M5 (v8.0: Restaurado como BLOQUEO)
            if h1_trend != "NONE":
                if (sig == "BUY" and h1_trend == "SELL") or (sig == "SELL" and h1_trend == "BUY"):
                    log_veto = " [Contra-H1]"
            
            # v17.1: M5 VETO ES LEY ABSOLUTA (Bypass Oracle v18.9.119)
            skip_m5_veto = (conf >= 0.97) and (adx_val < 40) or is_oracle_signal
            
            if not skip_m5_veto:
                if not MIRROR_MODE and (m5_trend_label == "🔴🔴") and sig == "BUY":
                    return {
                        "symbol": sym, "signal": "VETO-M5", "confidence": conf, "ai": raw_prob, 
                        "rsi": rsi_val, "lot": ASSET_CONFIG[sym]["lot"],
                        "state": "🔴", "profit": sym_pnl
                    }
                if not MIRROR_MODE and (m5_trend_label == "🟢🟢") and sig == "SELL":
                    return {
                        "symbol": sym, "signal": "VETO-M5", "confidence": conf, "ai": raw_prob, 
                        "rsi": rsi_val, "lot": ASSET_CONFIG[sym]["lot"],
                        "state": "🟢", "profit": sym_pnl
                    }

            # --- FILTRO VOLATILIDAD RELAJADO v7.88 ---
            atr = df_ta['atr'].iloc[-1] if 'atr' in df_ta.columns else 0
            if atr > 2.8: # Oro saltando más de $2.8 es el nuevo límite
                block_council = True; block_council_reason = f"VETO: Caos Total (ATR:{atr:.2f})"

            if votos_buy > votos_sell:
                # Veto BUY: Si estamos debajo de la EMA y la vela aún es roja
                if precio_bajo_ema and ultima_vela_roja and m5_trend_dir == "SELL":
                    block_council = True; block_council_reason = "VETO: Caída libre (M1 roja + EMA bajo)"
            elif votos_sell > votos_buy:
                # Veto SELL: Si estamos sobre la EMA y la vela aún es verde
                if precio_sobre_ema and ultima_vela_verde and m5_trend_dir == "BUY":
                    block_council = True; block_council_reason = "VETO: Subida vertical (M1 verde + EMA alto)"

                # M5 Trend Penalty (v7.92) - Softened for Scalping
                if sig == "BUY" and m5_trend_dir == "SELL":
                    conf -= 0.10; razones.append("P:M5↓")
                elif sig == "SELL" and m5_trend_dir == "BUY":
                    conf -= 0.10; razones.append("P:M5↑")

            # v11.1: Si la IA hizo OVERRIDE, saltar filtros. v15.6 Shield
            ia_intent = ia_dir
            sig_raw = sig
            
            # v11.1: Usa skip_m5_veto (cubre override Y confianza alta IA)
            if not skip_m5_veto:
                # v15.6 Titanium Shield: Escudo de Decisión Progresivo
                if conf < 0.98: # Si IA no es absoluta (98%), requiere consenso técnico
                    if council_sig != sig and conf < 0.80:
                        sig = "HOLD"
                        if now % 20 < 1: log(f"🛡️ BLOQUEO TÉCNICO: IA quiere {ia_intent} pero el Consejo dice {council_sig}. Esperando consenso.")

                    # v18.9.48: Definición de seguridad
                    ai_res = STATE.get('ai_results', {}).get(sym, {})
                    ai_d = ai_res.get('dir', "NONE")
                    ai_c = ai_res.get('conf', 0.0)

                    conflict = False
                    if (sig == "BUY" and ai_d == "SELL" and ai_c > 0.88): conflict = True
                    if (sig == "SELL" and ai_d == "BUY" and ai_c > 0.88): conflict = True

                    if conflict:
                        sig = "HOLD"
                        if now % 10 < 1: log(f"🛡️ CONFLICTO DE IA: IA externa contradice señal ({ai_d} {ai_c*100:.0f}%). Bloqueando {sig_raw}.")
                    
                    # --- SUAVIZADO DE CONFIANZA v11.1 (FIX: era 0.6/0.4 -> inflaba a 99%) ---
                    # v11.1: Cambiado a 0.3/0.7 para que conf siga la realidad, no la acumule
                    last_s = SMOOTH_CONF.get(sym, conf)
                    smooth = (last_s * 0.3) + (conf * 0.7)
                    SMOOTH_CONF[sym] = smooth
                    conf = smooth

                    # Log movido al final para consistencia v8.7.1
                    LAST_INSTINTO_LOG[sym] = sig
                
                # === ESTABILIDAD TITANIUM v15.6 ===
                wait_time = 1.0 # 1 Segundo de calma mínima
                st_sig, st_ts = LAST_STABLE_SIG.get(sym, ("NONE", 0))
                if sig == st_sig:
                    if (now - st_ts) < wait_time: 
                        sig = "HOLD" 
                else:
                    LAST_STABLE_SIG[sym] = (sig, now)
                    sig = "HOLD" 
            else:
                # IA OVERRIDE: Señal pasa directamente, sin filtros.
                LAST_STABLE_SIG[sym] = (sig, now)
                SMOOTH_CONF[sym] = conf

        # === PRE-PROCESAMIENTO DE SEÑAL VANGUARDIA ===
        # Capturamos la intención original antes de los filtros físicos
        intent_sig = sig
        intent_conf = conf
        
        # (Push notifications movidas al final para consistencia)

        # --- DETERMINACIÓN DE SEÑAL Y BLOQUEOS ---
        block_action = block_council # FIXED: Respect Council Vetoes
        block_reason = block_council_reason
        
        # v18.9.99: VETO MAESTRO WEB (Autonomous Fire)
        if not STATE.get("auto_mode", False):
            block_action = True
            block_reason = "VETO WEB: AUTONOMOUS FIRE APAGADO"
            
        # v16.5: Blindaje de Extremos Bollinger (Anti-Suicidio)
        # Prohibido vender en el suelo o comprar en el techo, sin excepciones de IA.
        # v8.7: SI ESTAMOS EN PELEO/ESPEJO, BYPASSEAMOS FILTROS DE SEGURIDAD
        if active and not MIRROR_MODE:
            # Veto Dinámico por bandas (ADX aware)
            corridor = upper_band - lower_band
            if adx_val > 25: # Tendencia: Más libertad
                margin = corridor * 0.12
            else: # Rango: Más rigor
                margin = corridor * 0.22
            
            # --- v18.0: BLOQUEO BINARIO DE TENDENCIA (EL GRILLETE) ---
            # EXCEPCIÓN: Si la IA tiene confianza sólida (80%+) permitimos ir contra corriente.
            if m5_trend_dir == "SELL" or precio_bajo_ema or ultima_vela_roja:
                if sig == "BUY" and conf < 0.80: 
                    sig = "HOLD"
                    block_action = True
                    block_reason = "CORRIENTE EN CONTRA (M5/EMA/VELA): Compra bloqueada."
            
            if m5_trend_dir == "BUY" or precio_sobre_ema or ultima_vela_verde:
                if sig == "SELL" and conf < 0.80:
                    sig = "HOLD"
                    block_action = True
                    block_reason = "CORRIENTE EN CONTRA (M5/EMA/VELA): Venta bloqueada."
            
            # 2. BLOQUEO Bollinger (v18.7: MODO CONTRAGOLPE)
            b_range = upper_band - lower_band
            b_ceiling = lower_band + (b_range * 0.82)
            b_floor = lower_band + (b_range * 0.18)
            
            # EXCEPCIÓN CONTRAGOLPE: Si no hay posiciones y estamos en el techo/piso
            # v18.9.125: DESACTIVADO. El usuario quiere control total y dependencia del Oráculo.
            # Nada de compras automáticas por Bollinger.
            contragolpe_active = False
            # if active and n_balas_reales == 0:
            #     if curr_price >= b_ceiling and ultima_vela_roja:
            #         sig = "SELL"; conf = 0.90; block_action = False; contragolpe_active = True
            #         log(f"⚔️ MODO CONTRAGOLPE: Techo detectado. Abriendo SELL táctico (0.01)")
            #     elif curr_price <= b_floor and ultima_vela_verde:
            #         sig = "BUY"; conf = 0.90; block_action = False; contragolpe_active = True
            #         log(f"⚔️ MODO CONTRAGOLPE: Piso detectado. Abriendo BUY táctico (0.01)")


            if not contragolpe_active and not block_action:
                if sig == "BUY" and curr_price >= b_ceiling:
                    block_action = True; block_reason = f"TECHO CRÍTICO: Esperando retroceso."
                elif sig == "SELL" and curr_price <= b_floor:
                    block_action = True; block_reason = f"PISO CRÍTICO: Esperando rebote."
                elif sig == "BUY" and curr_price >= mid_band and m5_trend_dir != "BUY":
                    block_action = True; block_reason = "ZONA ALTA: Compra prohibida en tendencia débil."
            
            # --- FILTRO DE GRAVEDAD v14.0 (CO-PILOT CONSENSUS) ---
            # EXCEPCIÓN: El Contragolpe ignora la gravedad porque busca precisamente el rebote/retroceso.
            if not contragolpe_active:
                is_contrarian = (curr_dir != "NONE" and sig != curr_dir)
                if sig == "BUY" and delta < -0.60: 
                    if not is_contrarian and conf < 0.95: 
                        block_action = True; block_reason = "GRAVEDAD (CO-PILOT VETO)"
                elif sig == "SELL" and delta > 0.60:
                    if not is_contrarian and conf < 0.95:
                        block_action = True; block_reason = "GRAVEDAD (CO-PILOT VETO)"
            
            # FILTRO DE MOMENTUM CRÍTICO ELIMINADO v7.38 (LIBERTAD TOTAL)
            pass

            # Bloqueo por zona neutra (v11.1: Rango reducido, IA bypass)
            if not contragolpe_active:
                is_in_neutral = 48 < rsi_val < 52  
                ia_uncertain = 0.47 < raw_prob < 0.53  
                if is_in_neutral and ia_uncertain and not ia_override:
                    block_action = True; block_reason = "ZONA NEUTRA"

            # --- v15.58: ACTIVIDAD PERMANENTE (RULE RE-STORED) ---
            # Si no hay posiciones y han pasado 5 mins, forzamos entrada mínima (0.01)
            # para mantener el pulso, salvo que RSI sea extremo.
            time_since_last = now - LAST_MISSION_TIME
            no_positions = len(pos_list) == 0
            
            # v15.62: COOLDOWN ANTI-SPAM (15s entre sondas)
            last_fire_local = STATE.get("last_fire", 0)
            since_fire = now - last_fire_local

            if no_positions and time_since_last > 420 and since_fire > 60:
                if 25 < rsi_val < 75: # Solo si no estamos en extremos peligrosos
                    # v18.6: YA NO DESBLOQUEAMOS block_action. La actividad permanente 
                    # ahora DEBE respetar los filtros de seguridad (Trend/Ceiling).
                    if not block_action:
                        # v18.9.15: Silenciado para evitar spam durante spreads altos
                        # log(f"⏰ ACTIVIDAD PERMANENTE: Buscando entrada exploratoria segura...")
                        pass
            
            # --- v15.36: FILTRO DE SEGURIDAD RSI (SENTINEL) ---
            # EXCEPCIÓN: Si es CONTRAGOLPE, ignoramos el Sentinel porque buscamos la reversión.
            if not contragolpe_active:
                if sig == "BUY" and rsi_val > 75:
                    block_action = True; block_reason = "RSI SOBRECOMPRADO (TECHO)"
                elif sig == "SELL" and rsi_val < 25:
                    block_action = True; block_reason = "RSI SOBREVENDIDO (PISO)"
        
        # === v15.0 VANGUARDIA: PROTECCIONES INSTITUCIONALES ===
        
        # 1. FILTRO DE SPREAD DINÁMICO (v15.4)
        tick = mt5.symbol_info_tick(sym)
        is_exploring = False
        if tick:
            spread = (tick.ask - tick.bid) / mt5.symbol_info(sym).point
            n_balas_actuales = len(pos_list)
            
            if spread > MAX_EXPLORATION_SPREAD and not is_oracle_signal:
                block_action = True
                block_reason = f"SPREAD PROHIBITIVO ({spread:.1f} pts)"
            elif is_oracle_signal and spread > 5000: # Límite extremo para ballenas
                block_action = True
                block_reason = f"SPREAD BALLENA EXTREMO ({spread:.1f})"

            elif spread > MAX_SKEW_SPREAD:
                if n_balas_actuales < MAX_BULLETS: # v18.9.13: Permitir las 5 balas incluso con spread alto
                    is_exploring = (n_balas_actuales == 0) # La primera es 0.01 si es spread alto
                    pass
                else:
                    block_action = True
                    block_reason = f"MAX BALAS ({MAX_BULLETS}) PARA SPREAD {spread:.1f}"

        # v18.8: Conteo físico preservado de la inicialización
        # n_balas_reales ya viene definido desde el inicio de la tarea
        
        # 2. LIMITADOR DE CARGADOR DINÁMICO v18.9.35 (BASADO EN MARGEN)
        margin_level = acc.margin_level if acc else 0.0
        
        # Regla del Comandante v18.9.37 (Margen) + v18.9.103 (Balance)
        if margin_level >= 350:
            user_max_bullets_margin = 5
        elif margin_level >= 200:
            user_max_bullets_margin = 3
        else:
            user_max_bullets_margin = 1
            
        # El balance define el límite maestro (Constitución v18.9.103)
        user_max_bullets = min(current_max_bullets, user_max_bullets_margin)
        effective_max = user_max_bullets
        
        # Ayuda de rescate tras 5 min atascado
        time_since_last_bullet = 0
        if len(pos_list) > 0:
            last_p_time = max(p.time for p in pos_list)
            srv_now = tick.time if (tick and hasattr(tick, 'time')) else time.time()
            time_since_last_bullet = srv_now - last_p_time

        if n_balas_reales >= user_max_bullets and time_since_last_bullet > 300: 
            effective_max = n_balas_reales + 1
            if now % 60 < 1: log(f"🆘 RESCATE VANGUARDIA: Bala de Auxilio #{effective_max} DISPONIBLE.")

        if n_balas_reales >= effective_max:
            block_action = True
            block_reason = f"MAX BALAS ({n_balas_reales}/{effective_max})"
        elif margin_level > 0 and margin_level < MIN_MARGIN_LEVEL:
            block_action = True
            block_reason = f"MARGEN CRÍTICO ({margin_level:.1f}%)"

        # 3. FILTRO DE VOLATILIDAD (ATR DYNAMICS)
        # Si el mercado está loco (ATR alto), aumentamos la distancia de las balas
        atr_factor = 1.0
        if adx_val > 25: # Alta tendencia/volatilidad
            atr_factor = 1.5 if adx_val < 40 else 2.5
        
        # 4. FILTRO DE TENDENCIA MAYOR (M5 ALIGNMENT v15.35 BLINDADO)
        # EXCEPCIÓN: El Contragolpe tiene permiso para ir contra la tendencia M5.
        if not contragolpe_active and not is_exploring and target_sig != "HOLD":
            if (target_sig == "BUY" and m5_trend_dir == "SELL") or (target_sig == "SELL" and m5_trend_dir == "BUY"):
                if conf < 0.80: # v18.9.14: Sincronizado con la regla de Élite (antes 0.96)
                    block_action = True; block_reason = f"TENDENCIA M5 CONTRARIA ({m5_trend_dir})"
                else:
                    if now % 60 < 1: log(f"🧠 IA-OVERRIDE: M5 en contra pero IA 80%+ confident. ¡ENTRANDO!")
                    block_action = False 

        # 6. FILTRO DE MOMENTUM (MOMENTUM RIDER v18.9.19)
        # Si el precio se mueve demasiado rápido, dejamos de ser "tercos" y seguimos la ola.
        if not is_exploring and len(df) >= 3:
            last_3_move = (df['close'].iloc[-1] - df['open'].iloc[-3]) / mt5.symbol_info(sym).point
            
            # BLOQUEO Y GIRO (v18.9.19: El Titan se vuelve Híbrido)
            if last_3_move > 1000: # Tsunami Alcista
                if target_sig == "SELL":
                    block_action = True; block_reason = f"BLOQUEO: NO VENDER CONTRA TSUNAMI (+{last_3_move:.0f})"
                    # Si el bot está activamente buscando entrada, le sugerimos cambiar de bando
                    if n_balas_reales == 0: 
                        log(f"🌊 MOMENTUM RIDER: Detectada fuerza alcista brutal. Sugiriendo CAMBIO A BUY.")
            elif last_3_move < -1000: # Tsunami Bajista
                if target_sig == "BUY":
                    block_action = True; block_reason = f"BLOQUEO: NO COMPRAR EN CAÍDA LIBRE ({last_3_move:.0f})"
                    if n_balas_reales == 0:
                        log(f"🌊 MOMENTUM RIDER: Detectado desplome nuclear. Sugiriendo CAMBIO A SELL.")

        # 7. ANTI-WHIPLASH COOLDOWN (90s v15.6)

        # 6. ESTABILIZACIÓN POST-SESIÓN (DESACTIVADO v15.32 por usuario)
        # if now_dt.minute < 10 and get_market_warning() is not None:
        #    block_action = True
        #    block_reason = "ESTABILIZACIÓN POST-SESIÓN (10m)"
            
        # --- REGLA DE ORO DE ACTIVIDAD PERMANENTE (v18.5 - CANDADO ATÓMICO) ---
        last_perm_fire = STATE.get(f"last_perm_{sym}", 0)
        # v18.5: Si ya se disparó algo en los últimos 30s (incluyendo latencia), bloqueamos
        is_firing_now = (now - STATE.get(f"firing_{sym}", 0)) < 15
        
        # v18.9.32: SINCRO TOTAL - Consultar MT5 justo antes de decidir bala obligatoria
        fresh_pos = mt5.positions_get(symbol=sym)
        n_balas_frescas = len(fresh_pos) if fresh_pos else 0
        
        # v18.9.116: GATILLO ATÓMICO DESACTIVADO (Solo operar por señales IA/Oracle)
        # if n_balas_frescas == 0 and sig in ["BUY", "SELL"] and (now - last_perm_fire) > 60 and not is_firing_now:
        #    ... (Bloque desactivado para evitar entradas no deseadas sin señal Oráculo)
        pass

                # The original block had STATE[f"firing_{sym}"] = now and LAST_ENTRY[sym] = now here,
                # but the new code already has them inside the 'if res' block.
                # The instruction provided had them outside the 'if conf' block, which is incorrect.
                # I'm keeping STATE[f"last_perm_{sym}"] = now here, as it was in the original logic
                # to mark the last permanent fire attempt, regardless of success.
                # The other two (firing_sym and LAST_ENTRY) are only updated on successful order.
        

        # === DECISIÓN FINAL v18.9.42 (MÁXIMA CAUTELA) ===
        # Se elimina el super_conf / IA-OVERRIDE. La realidad del precio manda.
        super_conf = False 
        
        # Veto de Momentum Inmediato (v18.9.42)
        if sig == "SELL" and df.iloc[-1]['close'] > df.iloc[-2]['close']:
            block_action = True; block_reason = "PRECIO SUBIENDO (Veto M1)"
        if sig == "BUY" and df.iloc[-1]['close'] < df.iloc[-2]['close']:
            block_action = True; block_reason = "PRECIO CAYENDO (Veto M1)"

        is_hard_blocked = "MARGEN" in block_reason or "MAX BALAS" in block_reason
        
        if block_action and not is_oracle_signal:
            target_sig = "HOLD"
        else:
            if block_action and (super_conf or is_oracle_signal):
                log(f"🧠 IA-OVERRIDE SUPREMO: Ignorando {block_reason} por {'ORÁCULO' if is_oracle_signal else 'Confianza'}.")
            target_sig = sig if sig != "HOLD" else "HOLD"


        # Compartir decisión con PACMAN (v7.99)
        GLOBAL_ADVICE[sym] = {"sig": target_sig, "conf": conf}
        
        # --- SISTEMA DE CONFIRMACIÓN OLLAMA v18.9.101 (COGNITIVE CACHE) ---
        last_call_ts = LAST_OLLAMA_CALL.get(sym, 0)
        cache = LAST_OLLAMA_CACHE.get(sym)
        
        # ¿Podemos usar el cache? (v18.9.102: Sensibilidad del 3%)
        use_cache = False
        if cache and cache['sig'] == target_sig:
            rsi_diff = abs(rsi_val - cache['rsi'])
            bb_diff = abs(bb_pos - cache['bb'])
            # Reducimos umbral a 3% para scalping minuto a minuto
            if rsi_diff < 3.0 and bb_diff < 0.03:
                use_cache = True
        
        # Throttling inteligente: Si use_cache es True, no llamamos aunque pasen 3m.
        # v18.9.103: Reducimos a 180s (3m) el refresco forzado para scalping minuto a minuto.
        # v18.9.123: Salto de IA si es señal de Oráculo (Confianza ciega en ballenas)
        if not is_oracle_signal and conf >= 0.70 and not active and (not use_cache or (time.time() - last_call_ts > 180)):

            LAST_OLLAMA_CALL[sym] = time.time()
            bb_txt = "TOPE" if bb_pos > 0.8 else "SUELO" if bb_pos < 0.2 else "CENTRO"
            prompt = f"Trader HFT: {sym} en {target_sig}. RSI:{rsi_val:.1f}, BB:{bb_txt}, Momentum:{delta:.2f}. ¿Confirmas entrada? Responde solo SI o NO y breve por qué."
            
            ai_reply, model_used = call_ollama(prompt)
            LAST_OLLAMA_CACHE[sym] = {'rsi': rsi_val, 'bb': bb_pos, 'sig': target_sig, 'res': ai_reply, 'model': model_used}
            with state_lock: STATE["last_ollama_res"] = f"[{model_used}] {ai_reply}"
            
            if "SI" in ai_reply.upper():
                log(f"🧠 OLLAMA CONFIRMA ({model_used}): {ai_reply}")
            else:
                log(f"🛡️ OLLAMA VETO ({model_used}): {ai_reply}. Reduciendo confianza.")
                conf *= 0.8
            
            msg = f"🎯 OPORTUNIDAD VALIDADA IA: {sym} en {target_sig} ({conf*100:.1f}%)"
            log(f"🚨 {msg}"); send_ntfy(msg)
        
        elif use_cache:
            ai_reply = cache['res']
            model_used = cache['model']
            if "SI" not in ai_reply.upper(): conf *= 0.8
            if time.time() % 300 < 1: log(f"🧠 IA CACHE ({sym}): Reutilizando decisión previa ({ai_reply[:20]}...)")

        if active and target_sig != "HOLD":
            # v18.9.32: MIRROR_MODE ELIMINADO POR SEGURIDAD
            v_str = " | ".join(map(str, razones[:4]))
            log(f"⚡ SCALP: {target_sig} ({conf*100:.1f}%) [{v_str}]")

        # 3. LÓGICA DE DISPARO (CAMBIO O ACUMULAR)
        should_fire = False
        trigger_type = "NORMAL"

        if target_sig != "HOLD":
            # v15.29: FRENOS DINÁMICOS SCALPER
            time_since_any_open = now - LAST_ENTRY.get(sym, 0)
            
            if contragolpe_active:
                should_fire = True; trigger_type = "CONTRAGOLPE"
            # Caso A: Entrada Inicial o Cambio de estado de la señal
            elif target_sig != LAST_SIGNALS.get(sym):
                # --- v18.9.78: ANTI-WHIPSAW INTELIGENTE (BLOQUEO DIRECCIÓN) ---
                last_dir = LAST_CLOSE_DIR.get(sym, "")
                last_type = LAST_CLOSE_TYPE.get(sym, "")
                last_time = LAST_CLOSE_TS.get(sym, 0)
                
                # Si perdimos en una COMPRA, no volver a comprar el mismo activo por 180s
                if last_dir == "LOSS" and (now - last_time) < 180 and target_sig == last_type:
                    block_action = True
                    block_reason = f"ANTI-WHIPSAW: Bloqueo re-entrada {target_sig} tras pérdida (180s)"
                
                if not block_action or super_conf or is_oracle_signal:
                    should_fire = True
                    trigger_type = "CAMBIO" if not super_conf else "IA-OVERRIDE"
                elif now % 20 < 1:
                    log(f"🧘 BLOQUEO: IA quería {target_sig} pero hay {block_reason}. Esperando...")
            # v18.9.7: LOG DE PERSISTENCIA (Para que el Comandante no piense que el bot murió)
            elif block_action and now % 30 < 1:
                log(f"📡 ESTATUS: IA en {sig} ({conf*100:.1f}%) pero BLOQUEADO por {block_reason}. Vigilando...")
            # Caso B: Acumular (Piramidación Inteligente v7.60)
            elif target_sig == LAST_SIGNALS.get(sym):
                if not block_action or is_oracle_signal:
                    # --- PIRAMIDACIÓN INTELIGENTE v7.60 ---
                    # Bala 1: Entrada normal (ya fue Caso A)
                    # Bala 2: Si la bala 1 ya va ganando O si hay momentum fuerte
                    # Bala 3-5: Solo si la tendencia se confirma progresivamente
                    
                    n_balas = len(pos_list)
                    rsi_safe = not ((target_sig == "SELL" and rsi_val < 30) or (target_sig == "BUY" and rsi_val > 70))
                    
                    # v13.5: BLOQUEO RSI COMENTADO PARA PERMITIR "JOC" EN EXTREMOS
                    # if not rsi_safe:
                    #     block_action = True
                    #     if rsi_val > 70: block_reason = f"TECHO ADVERTENCIA (RSI {rsi_val:.1f})"
                    #     elif rsi_val < 30: block_reason = f"PISO ADVERTENCIA (RSI {rsi_val:.1f})"
                    
                    last_price = LAST_ENTRY_PRICE.get(sym, 0.0)
                    
                    # --- ENFRIAMIENTO DINÁMICO v18.9.12 (Ajuste Máxima Potencia) ---
                    close_time = LAST_CLOSE_TS.get(sym, 0)
                    is_last_win = LAST_CLOSE_DIR.get(sym) == "WIN"
                    wait_time = 1 if is_last_win else 3 # MODO URGENCIA CUMPLEAÑOS: Metralleta real (Sin demoras)
                    
                    if (now - close_time) < wait_time:
                        block_action = True
                        block_reason = f"ENFRIAMIENTO {'POST-WIN' if is_last_win else 'POST-LOSS'} ({wait_time}s)"

                    if not MIRROR_MODE and target_sig == "BUY" and delta < -0.80: # Relajado v13.5
                        block_action = True
                        block_reason = "TENDENCIA BAJISTA CRÍTICA"
                        
                    # --- BLOQUEO POR RACHA DE PÉRDIDAS v15.6 (Más agresivo) ---
                    if CONSECUTIVE_LOSSES.get(sym, 0) >= 2:
                        now_c = time.time()
                        if now_c < COOL_DOWN_UNTIL.get(sym, 0):
                            block_action = True
                            block_reason = f"RACHA DE PÉRDIDAS ({CONSECUTIVE_LOSSES[sym]}) - PAUSA 10M"
                        else:
                             # Solo resetar si ya pasó el tiempo
                             pass 

                    # Verificar si posiciones actuales van ganando
                    pos_ganando = sym_pnl > 0 if n_balas > 0 else True
                    momentum_fuerte = abs(delta) > 0.30  # Momentum real
                    momentum_dir_ok = (target_sig == "BUY" and delta > 0.10) or (target_sig == "SELL" and delta < -0.10)
                    
                    # Reglas por nivel de bala
                    if n_balas == 0:
                        req_delay = 0; min_dist = 0
                    elif n_balas >= 1:
                        # BLOQUEO DE PROMEDIACIÓN: No añadir si la anterior pierde > $2
                        # EXCEPCIÓN: Si es señal CONTRARIA (Hedging/Rescate), permitir siempre.
                        
                        real_dir = "NONE"
                        if len(pos_list) > 0:
                            p0 = pos_list[0]
                            real_dir = "BUY" if p0.type == mt5.POSITION_TYPE_BUY else "SELL"
                        
                        is_contrarian = (real_dir != "NONE" and target_sig != real_dir)

                        # v12.2: RELAJACIÓN DE VETO (Permitir Rescate)
                        # Solo bloqueamos si NO es un intento de Smart Recovery o Stacking
                        if not MIRROR_MODE and sym_pnl < -2.0 and not is_contrarian:
                             # No bloqueamos aquí preventivamente, dejamos que la lógica de disparo decida
                             pass 
                        
                        # v12.1: DELAY REDUCIDO EN EXTREMOS RSI
                        rsi_extreme = (rsi_val < 35 or rsi_val > 65)
                        base_delay = 1 # KAMIKAZE
                        
                        # v9.9.1: En espejo, permitimos ráfaga rápida (3s) y proximidad
                        req_delay = 1 # KAMIKAZE
                        min_dist = 0.05 # KAMIKAZE
                        
                        # HEDGING INSTANTÁNEO
                        if is_contrarian: 
                            req_delay = 0; min_dist = 0
                    
                    if sig != "HOLD" and (not block_action or is_oracle_signal):
                        dist_val = abs(curr_price - last_price)
                        n_balas = len(pos_list)
                        
                        # DISTANCIA DINÁMICA v15.29 (SCALPER SMART)
                        # v15.29: Rapidez total si ganamos (5s), precaución si perdemos (20s)
                        lp_profit = pos_list[-1].profit if len(pos_list) > 0 else 0
                        req_delay = 5 if lp_profit > 0 else 10 # v18.9.9: Delay reducido de 20 a 10 para rescatar
                        min_dist = 0.2 * atr_factor # v18.9.9: Distancia táctica reducida
                        
                        # --- GIROS RÁPIDOS v13.5 ---
                        if trigger_type == "CAMBIO" and conf < 0.65:
                            should_fire = False
                            if now % 10 < 1: log(f"⏳ ESPERANDO CONFIRMACIÓN: Giro necesita >65% (Ahora {conf*100:.1f}%)")

                        # --- LÓGICA DE RECUPERACIÓN (v7.81) ---
                        recovery_trigger = False
                        stacking_trigger = False # v10.1
                        
                        # v18.9.94: REGLA DE ORO - Solo acumular si la anterior gana
                        if n_balas > 0:
                            lp = pos_list[-1]  # Última posición abierta
                            # BALA 2: Solo si la bala 1 está positiva
                            # BALA 3: Solo si la bala 2 está positiva
                            prev_is_positive = lp.profit > 0
                            if (prev_is_positive and (now - LAST_ENTRY.get(sym, 0)) > 20.0) or (is_oracle_signal and (now - LAST_ENTRY.get(sym, 0)) > 5.0):
                                stacking_trigger = True
                                r_text = 'ORÁCULO FORZA (5s Delay)' if is_oracle_signal else f'Anterior positiva (${lp.profit:.2f})'
                                log(f"🟢 BALA {n_balas+1}: {r_text}. ACUMULANDO.")
                            elif not prev_is_positive:
                                stacking_trigger = False
                                if now % 30 < 1:
                                    log(f"🔴 BALA {n_balas+1} BLOQUEADA: Anterior en ${lp.profit:.2f} (necesita >$0). Esperando...")

                        # --- LÓGICA DE RE-ENTRADA INMEDIATA (ANTI-NOISE) v18.9.106 ---
                        # Si cerramos por Trailing (SUIZO) pero la señal sigue siendo BRUTAL (>88%), 
                        # abrimos de nuevo ignorando el cooldown de 15s.
                        just_closed_trailing = "SUIZO" in LAST_CLOSE_REASON.get(sym, "")
                        same_direction = target_sig == LAST_CLOSE_TYPE_REAL.get(sym, "")
                        is_urgent_continuation = just_closed_trailing and same_direction and conf > 0.88
                        
                        if is_urgent_continuation and active and n_balas == 0:
                            log(f"🔄 RE-ENTRADA INMEDIATA: La señal sigue fuerte ({conf*100:.0f}%) tras cierre por ruido. Continuando cacería...")
                            should_fire = True
                            trigger_type = "CONTINUACIÓN-PRO"
                            # Limpiamos la razón para no loopear infinitamente
                            LAST_CLOSE_REASON[sym] = "RE-ENTERED"

                        if n_balas == 0 and not is_urgent_continuation:
                             # v16.7: Solo entrar si NO hay bloqueos de Bollinger/Spread
                             # v18.9.120: ORACLE BYPASS total de bloqueos tácticos
                             if (not block_action or is_oracle_signal) and conf >= 0.60:  
                                 should_fire = True
                             else:
                                 should_fire = False

                                 if now % 20 < 1 and not block_action: 
                                     log(f"⏳ BAJA CONFIANZA: {conf*100:.1f}% < 70%")
                                 elif now % 20 < 1:
                                     log(f"🧘 BLOQUEO VANGUARDIA: {block_reason}")

                             if should_fire:
                                 if is_exploring:
                                     trigger_type = "EXPLORACIÓN-0.01"
                                 else:
                                     trigger_type = "SOLO"
                        elif stacking_trigger:
                             # Solo stacking si no llegamos al límite
                             if n_balas < MAX_BULLETS:
                                 should_fire = True; trigger_type = f"ACUM-B{n_balas+1}"
                             else:
                                 should_fire = False
                                 log(f"🛑 LIMITE: {n_balas}/{MAX_BULLETS} balas activas.")
                        # --- GESTIÓN ADAPTATIVA DE BALAS v18.9.103 (Lógica de Salvación) ---
                        # Si hay posiciones abiertas > 5 minutos sin profit, desbloquear salvación (4 y 5) sobre $100
                        if balance >= 100.0 and n_balas >= 3:
                            oldest_pos_time = min(p.time for p in pos_list) if pos_list else now
                            if (now - oldest_pos_time) > 300: # 5 minutos
                                current_max_bullets = 5
                                log(f"🆘 ACTIVANDO BALAS DE SALVACIÓN (n={n_balas+1}): Posiciones estancadas > 5m.")

                        if n_balas >= current_max_bullets:
                            should_fire = False
                            if now % 20 < 1: log(f"🛑 LIMITE ADAPTATIVO: {n_balas}/{current_max_bullets} balas (Saldo ${balance:.2f}).")
                            else:
                                 # v18.9.40: Distancia Maratón (Misión $500)
                                 # v18.9.81: Distancia reducida si la confianza es BRUTAL
                                 smart_min_dist = 0.80  # v18.9.94: Min 80 pts entre balas en Oro
                                 
                                 # 3. Confirmación de color de vela (Flexibilizado para Máxima Potencia)
                                 confirmacion_vela = False
                                 if target_sig == "SELL" and ultima_vela_roja: confirmacion_vela = True
                                 if target_sig == "BUY" and ultima_vela_verde: confirmacion_vela = True
                                 
                                 # Si la IA es BRUTAL (85%+), ignoramos el color de la vela y el delay
                                 if conf >= 0.85: 
                                     confirmacion_vela = True
                                     # req_delay ya se cumplió por el elif

                                 # Condición de Rescate Real
                                 if dist_val >= smart_min_dist and confirmacion_vela:
                                     # Solo promediamos si hay una señal clara
                                     if raw_prob > 0.75 or conf > 0.90:
                                         if is_exploring:
                                             if n_balas == 0:
                                                 should_fire = True
                                                 trigger_type = "EXPLORACIÓN-0.01"
                                             else:
                                                 should_fire = False
                                         else:
                                             should_fire = True
                                             trigger_type = f"BALA-{n_balas+1}"
                                     
                                     if should_fire:
                                         if sym_pnl < 0:
                                              log(f"🚑 RESCATE VANGUARDIA: B{n_balas+1} (D:{dist_val:.2f} P:{raw_prob:.2f})")
                                         else:
                                              log(f"🪜 TRABAJANDO: Añadiendo B{n_balas+1} (IA:{raw_prob:.2f}) a favor")
                                 else:
                                     should_fire = False
                                     # Log de espera detallado
                                     if now % 20 < 1:
                                         razon_espera = "Distancia" if dist_val < smart_min_dist else "Color de Vela"
                                         log(f"🧘 AFILANDO PUNTERÍA: Esperando {razon_espera} para B{n_balas+1} (D:{dist_val:.2f}/0.25)")
                        
                        # --- FILTRO DE VIDA MÍNIMA v11.6 (ANTI-WHIPSAW) ---
                        # v12.1: Ignorar delay si es un HEDGE (Rescate urgente)
                        if trigger_type == "CAMBIO" and time_val < 15.0 and not is_contrarian:
                            should_fire = False
                            if now % 5 < 1: log(f"⏳ PROTECCIÓN: Esperando estabilidad (15s) para {sym}")
                        else:
                             if dist_val < min_dist or time_val < req_delay:
                                 should_fire = False
                                 if now % 20 < 1: # Reducido spam v14.1
                                     reason = f"Distancia {dist_val:.2f}/{min_dist}" if dist_val < min_dist else f"Tiempo {int(time_val)}/{req_delay}s"
                                     log(f"💤 EN GUARDIA: Esperando B{n_balas+1} en {sym} para {target_sig} ({reason}) | IA:{raw_prob:.2f}")
                    elif block_action and (now - LAST_INSTINTO_LOG.get(f"block_{sym}", 0)) > 15:
                        log(f"🧘 BLOQUEO VANGUARDIA: {block_reason}")
                        LAST_INSTINTO_LOG[f"block_{sym}"] = now

        # --- PROTECCIÓN CIERRE DE MERCADO ORO (v15.64: HORARIO ADELANTADO) ---
        # Oro cierra a las 19:00 Chile. 
        # - 18:30: SE PROHÍBEN NUEVAS ENTRADAS (Soft Close)
        # - 18:45: CIERRE FORZOSO DE TODO (Hard Close)
        
        hora_chile = now_dt.hour
        minuto_chile = now_dt.minute
        
        mercado_cerrado = False
        bloqueo_entrada = False

        if hora_chile == 18:
            if minuto_chile >= 45: mercado_cerrado = True # Hard Close
            elif minuto_chile >= 40: bloqueo_entrada = True # Soft Close (solo 5 min antes)
        elif hora_chile == 19:
            mercado_cerrado = True
        elif hora_chile == 20 and minuto_chile < 5:
            mercado_cerrado = True
        
        if "XAU" in sym:
            if mercado_cerrado:
                if len(pos_list) > 0:
                    log(f"🔒 CIERRE MERCADO (HARD): Cerrando {sym} antes del gap! (18:45)")
                    for p in pos_list:
                         close_ticket(p, "MERCADO_CERRADO")
                    # v18.9.29: Detener misión para evitar reaperturas indeseadas
                    log(f"🏁 MISIÓN FINALIZADA POR HORARIO. Retirada estratégica.")
                    stop_mission()
                    should_fire = False 
                    block_action = True
                else:
                    # Si no hay posiciones pero el mercado cerró, también nos aseguramos de apagar
                    if mission_state.get("active"):
                        stop_mission()
                    block_action = True
                    block_reason = "MERCADO CERRADO (18:45-20:05)"
            elif bloqueo_entrada:
                if len(pos_list) == 0:
                    block_action = True
                    block_reason = "RESTRICCIÓN PRE-CIERRE (18:30)"

        # --- BOTÓN DE PÁNICO (Última defensa - SUBIDO A $150) ---
        if sym_pnl <= -150.0 and len(pos_list) > 0:
            log(f"🚨 PÁNICO CRÍTICO: Limpiando {sym} (Limite -$150)")
            target_sig = "HOLD"
            should_fire = True

        # --- GESTIÓN DE SALIDA (SIN ASFIXIA) ---
        # (Lógica simplificada para el hilo)

        # --- ENVÍO DE SEÑAL OPTIMIZADA (ANTI-LAG) ---
        # v16.0: Blindaje Total - Solo enviamos señales si hay una misión ACTIVA.
        if active:
            time_since_last = now - LAST_HEARTBEAT.get(sym, 0)
            is_heartbeat = time_since_last > 5.0
            
            # v18.1: Blindaje de Envío de Señal
            # Solo enviar si NO hay bloqueos o si es un refresco de una señal ya existente
            # v18.9.24: Liberación de Gatillo - IA 97%+ / Oracle ignora bloqueos tácticos (M5/Trend)
            if target_sig in ["BUY", "SELL"] and (not block_action or super_conf or is_oracle_signal):

                should_send = False
                if should_fire: should_send = True # Disparo forzado (nuevo o stacking)
                elif is_heartbeat and target_sig == LAST_SIGNALS.get(sym): should_send = True # Heartbeat normal
                
                if should_send:
                    # v18.9.45: VALIDACIÓN DE EXCLUSIÓN DE PRECIO (Anti-Metralleta)
                    tick = mt5.symbol_info_tick(sym)
                    price = tick.ask if target_sig == "BUY" else tick.bid
                    
                    # Escanear precios de posiciones actuales
                    too_close = False
                    for p in pos_list:
                        dist_to_pos = abs(price - p.price_open)
                        if dist_to_pos < 0.35: # 350 puntos de zona prohibida
                            too_close = True
                            break
                    
                    if too_close:
                        if now % 10 < 1: log(f"⏳ ZONA PROHIBIDA: Precio demasiado cerca de bala existente. Esperando espacio...")
                        return
                    
                    # v18.9.115: REGLA BUNKER $25 USD (Recuperación/Stacking)
                    side_mt5 = mt5.ORDER_TYPE_BUY if target_sig == "BUY" else mt5.ORDER_TYPE_SELL
                    final_lot = ASSET_CONFIG[sym]["lot"]
                    sl_price = get_bunker_sl_price(sym, final_lot, side_mt5, price)

                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": sym, "volume": final_lot,
                        "type": side_mt5,
                        "price": price, "sl": sl_price, "magic": 777,
                        "comment": f"TITAN-BUNKER-25USD",

                        "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    
                    res = mt5.order_send(request)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        log(f"✅ RECUPERACIÓN EXITOSA: {target_sig} (#{res.order})")
                        with state_lock: STATE[f"firing_{sym}"] = now
                        LAST_ENTRY[sym] = now
                        time.sleep(10) # Seguro de 10s contra metralleta
                    else:
                        log(f"⚠️ Fallo API: {res.comment if res else 'Error'}. Usando bridge...")
                        send_signal(sym, target_sig, force=should_fire)
                LAST_ENTRY_PRICE[sym] = float(tick.ask if target_sig == "BUY" else tick.bid)
                if target_sig not in ["NONE", "HOLD"]:
                    log(f"⚡ {sym} -> {target_sig} ({conf*100:.1f}%) [{trigger_type}]")

        return {
            "symbol": sym, "signal": target_sig if target_sig != "HOLD" else LAST_SIGNALS.get(sym, "WAIT"),
            "confidence": conf, "ai": raw_prob, "rsi": rsi_val, "lot": ASSET_CONFIG[sym]["lot"],
            "state": "🚀" if should_fire else "💤", "profit": sym_pnl,
            "bb_pos": bb_pos, "m5_trend": m5_trend_label, "h1_trend": h1_trend
        }
    except Exception as e:
        log(f"⚠️ Error task {sym}: {e}")
        return None

def metralleta_loop():
    global MIRROR_MODE
    global LAST_MISSION_TIME
    global LAST_LATENCY, LAST_LATENCY_UPDATE # v15.53: Fix Scope Error
    log("======================================================")
    log("🚀 OCTOPUS 2.0 INITIALIZING... (Parallel Mode)")
    print("🚀 [CONSOLE] OCTOPUS STARTING... CHECKING MT5...")
    log("======================================================")
    while not init_mt5():
        log("❌ MT5 Connection Failed. Retrying in 5s...")
        time.sleep(5)
    cargar_modelo_lstm()
    load_settings() 
    if not mission_state["active"]:
        positions = mt5.positions_get()
        if positions and any(p.symbol in SYMBOLS for p in positions):
            log("📡 DETECTADAS POSICIONES HUÉRFANAS: Reconectando misión automáticamente...")
            mission_state["active"] = True
            mission_state["symbol"] = "ORO/VANGUARDIA" 
            mission_state["target"] = 50.0
            if mission_state.get("start_equity", 0) == 0:
                acc = mt5.account_info()
                mission_state["start_equity"] = acc.balance if acc else get_equity()
                mission_state["start_time"] = time.time()
            save_mission_state()
        else:
            # --- RESET ATÓMICO v15.36 ---
            log("🧹 RESET TOTAL: Detectado estado sin posiciones. Limpiando PnL pegado.")
            mission_state["active"] = False
            mission_state["start_equity"] = float(get_equity())
            mission_state["target_profit"] = 50.0
            mission_state["last_pnl"] = 0.0
            STATE["pnl"] = 0.0
            STATE["daily_profit"] = 0.0
            if os.path.exists(MISSION_FILE_PATH):
                try: os.remove(MISSION_FILE_PATH)
                except: pass
            save_mission_state()
    load_history() 
    
    PNL_SNAPSHOTS = []      # Lista de (time, pnl)
    PRICE_SNAPSHOTS = {}    # {sym: [(time, price)]}
    
    # --- EXORCISMO DE ARCHIVOS VIEJOS (FANTASMAS) ---
    try:
        if os.path.exists(MQL5_FILES_PATH):
            for f in os.listdir(MQL5_FILES_PATH):
                if f.startswith("titan_signal_") and f.endswith(".txt"):
                    # Extraer simbolo: titan_signal_GBPJPYm.txt -> GBPJPYm
                    sym_name = f.replace("titan_signal_", "").replace(".txt", "")
                    if sym_name not in SYMBOLS:
                        full_path = os.path.join(MQL5_FILES_PATH, f)
                        try:
                            os.remove(full_path)
                            log(f"🧹 EXORCISMO: Eliminado fantasma {f}")
                        except Exception as e:
                            log(f"⚠️ No se pudo borrar {f}: {e}")
    except Exception as e:
        log(f"⚠️ Error limpieza: {e}")

    log("🐙 CEREBRO HÍBRIDO ONLINE")
    
    with state_lock: STATE["price_history"] = []

    # ============ 2. CONFIGURACIÓN DE AI & INDICADORES ============   
    pacman_timer = 0

    while True:
        global VANGUARDIA_LOCK
        try:
            now_loop = time.time()
            
            # v18.9.28: BLOQUEO DINÁMICO POR MARGEN (Fix: 0% sin posiciones = cuenta libre)
            acc_check = mt5.account_info()
            has_open_pos = len(mt5.positions_get() or []) > 0
            if acc_check and has_open_pos and acc_check.margin_level < MIN_MARGIN_LEVEL:
                if not VANGUARDIA_LOCK:
                    VANGUARDIA_LOCK = True
                    log(f"🛡️ BLOQUEO DE SEGURIDAD: Margen insuficiente ({acc_check.margin_level:.1f}%)")
            elif VANGUARDIA_LOCK and (not has_open_pos or (acc_check and acc_check.margin_level > (MIN_MARGIN_LEVEL + 20))):
                VANGUARDIA_LOCK = False
                log(f"🔓 SISTEMA LIBERADO: Margen OK o sin posiciones.")
            # v18.9.78: GESTIÓN DE RIESGO ADAPTATIVA
            current_equity = get_equity()
            # El usuario solicita lotaje dinámico para mover la cuenta
            # Si la IA tiene >90% confianza, permitimos bono de lotaje
            # logic handled inside process_symbol_task if needed
            
            # --- SENSOR DE VELOCIDAD DEL MERCADO (v18.9.20) ---
            ph_v = STATE.get("price_history", [])
            m_speed = 20.0 # Default
            if len(ph_v) > 10:
                m_speed = (max(ph_v) - min(ph_v)) * 6.0 # $/min aprox con 0.01
            with state_lock: STATE["market_speed_val"] = m_speed

            # --- GESTOR DE RIESGO HIPER-VELOCIDD (PACMAN) ---
            positions = mt5.positions_get()
            current_open_pnl = 0.0 
            
            if positions:
                # v18.9.21: Modo Co-Piloto - Vigilar también posiciones manuales (magic 0) del Comandante
                open_positions = [pos for pos in positions if (pos.magic == 777 or (pos.magic == 0 and pos.symbol in SYMBOLS))]
                current_open_pnl = sum(p.profit for p in open_positions)
                with state_lock: STATE["open_pnl"] = current_open_pnl

                # A. COSECHA DE RAÍZ DINÁMICA (v18.9.20)
                # Cerrar al 95% de la meta para asegurar profit antes de retrocesos
                target_harvest = mission_state.get("target", 50.0) * 0.95
                if current_open_pnl >= target_harvest: 
                    log(f"💎 COSECHA DE RAÍZ ADAPTATIVA: +${current_open_pnl:.2f} (Meta 95% tocada)")
                    for p in open_positions: close_ticket(p, "COSECHA_RAIZ_v20")
                    continue

                # B. PROTOCOLO DE BLINDAJE INDIVIDUAL (v7.71)
                for p in open_positions:
                    # v11.5: Sincronización de Tiempos (Last Entry Fix)
                    # Si reiniciamos, el bot no sabe cuándo abrió. Lo leemos de MT5.
                    p_sym = p.symbol
                    if p_sym not in LAST_ENTRY or LAST_ENTRY[p_sym] == 0:
                        LAST_ENTRY[p_sym] = float(p.time)
                        # log(f"⏱️ SINCRONIZADO: {p_sym} abierto hace {int(now_loop - p.time)}s")
                    
                    sym = p.symbol
                    lot = p.volume
                    entry = p.price_open
                    profit = p.profit + getattr(p, 'swap', 0.0) + getattr(p, 'commission', 0.0)
                    
                    if p.magic == 0 and now_loop % 30 < 1:
                        log(f"🛡️ PROTEGIENDO POSICIÓN MANUAL: {sym} (${profit:.2f})")
                    
                    # === PROTOCOLO DE $25 HARD STOP (v18.9.77) ===
                    # El usuario indicó que prefiere arriesgar los $25 para aguantar la volatilidad extrema.
                    if profit <= -25.0:
                        log(f"🚨 HARD STOP ACTIVADO: {sym} alcanzó límite de -$25.00. Cerrando.")
                        close_ticket(p, "HARD_STOP_USER"); continue

                    # === PROTOCOLO DE TRIPLE TRAILING (v18.9.80) ===
                    m_speed_current = STATE.get("market_speed_val", 20.0)
                    is_fast = m_speed_current > 100 # Mercado volátil/rápido
                    
                    # 0. MODO KAMIKAZE: TRAILING RELÁMPAGO INTELIGENTE
                    # A medida que sube la ganancia, vamos ajustando el SL de forma escalonada.
                    # Mientras más sube, más agresivo es el cierre detrás del precio.
                    if profit >= 0.50 and (now_loop - p.time) < 45: 
                        symbol_info = mt5.symbol_info(sym)
                        if symbol_info:
                            dist_sl = 1 / (lot * symbol_info.trade_contract_size)
                            
                            # Trailing Inteligente Escalonado (Kamikaze Adaptativo)
                            if profit >= 1.50: locked_p = profit - 0.40   # Si va muy arriba, damos $0.40 de espacio (para dejarlo volar)
                            elif profit >= 1.00: locked_p = profit - 0.30 # Damos $0.30 de oxígeno
                            elif profit >= 0.80: locked_p = profit - 0.20 # Damos $0.20 de oxígeno
                            else: locked_p = profit - 0.15                # Entre $0.50 y $0.80, ajustamos a solo $0.15 de distancia
                            
                            new_sl_kamikaze = entry + (dist_sl * locked_p) if p.type == mt5.ORDER_TYPE_BUY else entry - (dist_sl * locked_p)
                            curr_sl = float(p.sl)
                            new_sl_kamikaze = round(new_sl_kamikaze, symbol_info.digits)
                            
                            is_better = False
                            if p.type == mt5.ORDER_TYPE_BUY:
                                if curr_sl == 0 or new_sl_kamikaze > curr_sl + symbol_info.point * 10: is_better = True
                            else:
                                if curr_sl == 0 or (0 < new_sl_kamikaze < curr_sl - symbol_info.point * 10): is_better = True
                                
                            if is_better:
                                update_sl(p.ticket, new_sl_kamikaze, f"KAMI-TRL (${profit:.2f})")
                                continue # Cortar el loop si ya le movimos el SL a nivel de ganancia

                    # 1. Trailing Dinámico para mercados rápidos
                    if is_fast and profit >= 1.05:
                        # Si es rápido y tenemos >$1, NO CERRAR. Dejar que PACMAN o el Trailing del EA lo gestionen.
                        # Solo cerramos si la señal de la IA cambia drásticamente.
                        adv = GLOBAL_ADVICE.get(sym, {"sig": "HOLD", "conf": 0.0})
                        is_contrarian = (p.type == mt5.ORDER_TYPE_BUY and adv["sig"] == "SELL") or (p.type == mt5.ORDER_TYPE_SELL and adv["sig"] == "BUY")
                        if is_contrarian and adv["conf"] > 0.80:
                            log(f"🧠 GIRO IA RÁPIDO: Cerrando {sym} con ${profit:.2f} por señal contraria.")
                            close_ticket(p, "QUANTUM_FLIP"); continue
                    
                    # 2. Cierre de Hierro Normal (Meta de $0.85 en Kamikaze)
                    elif not is_fast and profit >= 0.85:
                        adv = GLOBAL_ADVICE.get(sym, {"sig": "HOLD", "conf": 0.0})
                        is_contrarian = (p.type == mt5.ORDER_TYPE_BUY and adv["sig"] == "SELL") or (p.type == mt5.ORDER_TYPE_SELL and adv["sig"] == "BUY")
                        if is_contrarian or (now_loop % 45 < 1):
                            log(f"💰 META CERRADA: {sym} protegiendo ${profit:.2f}. (M. Estable)")
                            close_ticket(p, "IRON_PROFIT_v21"); continue
                    
                    # 3. Cierre Micro en mercado estancado (Trailing Ultra-Corto)
                    elif profit >= 0.30:
                        trade_life = now_loop - p.time
                        if trade_life > 20: # Más de 20s sin avanzar -> Cortar rápido
                            log(f"🐜 MICRO-CIERRE (LENTO): Asegurando ${profit:.2f} por estancamiento (20s).")
                            close_ticket(p, "SLOW_MARKET_EXIT"); continue
                    
                    symbol_info = mt5.symbol_info(sym)
                    if not symbol_info: continue
                    dist_sl = 1 / (lot * symbol_info.trade_contract_size)
                    
                    # --- BLINDAJE ULTRA-AGRESIVO (v7.71) ---
                    new_sl = 0.0
                    comment = ""
                    
                    # --- RATCHET SUIZO v16.1 (ULTRA-GRANULAR) ---
                    if profit >= 9.0:
                        locked_p = profit - 1.2 
                        new_sl = entry + (dist_sl * locked_p) if p.type == mt5.ORDER_TYPE_BUY else entry - (dist_sl * locked_p)
                        comment = f"SUIZO-9K"
                    elif profit >= 5.0:
                        new_sl = entry + (dist_sl * 4.0) if p.type == mt5.ORDER_TYPE_BUY else entry - (dist_sl * 4.0)
                        comment = "SUIZO-5K ($4.0)"
                    elif profit >= 3.0:
                        new_sl = entry + (dist_sl * 2.5) if p.type == mt5.ORDER_TYPE_BUY else entry - (dist_sl * 2.5)
                        comment = "SUIZO-3K ($2.5)"
                    elif profit >= 2.2:
                        new_sl = entry + (dist_sl * 1.5) if p.type == mt5.ORDER_TYPE_BUY else entry - (dist_sl * 1.5)
                        comment = "SUIZO-2.2K ($1.5)"
                    elif profit >= 1.6:
                        # v18.9.2: Nivel mínimo de blindaje asegurando al menos $1.0
                        new_sl = entry + (dist_sl * 1.05) if p.type == mt5.ORDER_TYPE_BUY else entry - (dist_sl * 1.05)
                        comment = "SUIZO-1.6K ($1.0)"
                    # Niveles inferiores eliminados para cumplir con la regla de >$1 USD
                    
                    # --- PROFIT PARACHUTE v7.93 (MÁS TOLERANTE) ---
                    max_p = STATE.get(f"max_p_{p.ticket}", 0.0)
                    if profit > max_p: STATE[f"max_p_{p.ticket}"] = profit
                    # --- v15.3: ESTRATEGIA DE REDUCCIÓN DE DAÑO (STRATEGIC EXIT) ---
                    min_p = STATE.get(f"min_p_{p.ticket}", 0.0)
                    if profit < min_p: STATE[f"min_p_{p.ticket}"] = profit # Guardamos el punto más bajo
                    
                    # Lógica: Si estuvimos en -$15 o peor, y recuperamos hasta -$5, evaluamos salida digna
                    if not MIRROR_MODE and min_p < -15.0 and profit > -5.0:
                        advice = GLOBAL_ADVICE.get(sym, {"sig": "HOLD", "conf": 0.0})
                        t_sig = advice["sig"]
                        # Si la recuperación se estanca o hay señal contraria, cerramos para salvar el capital
                        recover_pct = abs(profit - min_p) / abs(min_p)
                        is_contrarian = (p.type == mt5.ORDER_TYPE_BUY and t_sig == "SELL") or (p.type == mt5.ORDER_TYPE_SELL and t_sig == "BUY")
                        
                        if recover_pct > 0.70 and (is_contrarian or now_loop % 30 < 1):
                            log(f"✂️ SALIDA ESTRATÉGICA: Reduciendo daño de {min_p:.2f} a {profit:.2f} ({recover_pct:.1%})")
                            close_ticket(p, "STRATEGIC_REAVE"); continue

                    # === PROTOCOLO BUNKER TOTAL v7.97 ===
                    if MIRROR_MODE:
                        pass # No cerrar por cambio de señal en modo espejo
                    else:
                        trade_life = now_loop - p.time
                        if trade_life < 15:
                            pass 
                        else:
                            # v17.0: BLOQUEO DE CIERRE POR PÁNICÓ (BUNKER)
                            # El bot ya NO tiene permiso para cerrar en pérdida por cambio de señal.
                            # Solo el usuario o el SL/TP físico pueden cerrar.
                            pass

                    # Aplicar SL si es mejor que el actual
                    if new_sl > 0:
                        curr_sl = float(p.sl)
                        digits = symbol_info.digits
                        new_sl = round(new_sl, digits)
                        
                        is_better = False
                        if p.type == mt5.ORDER_TYPE_BUY:
                            if curr_sl == 0 or new_sl > curr_sl + symbol_info.point * 10: is_better = True
                        else:
                            if curr_sl == 0 or (0 < new_sl < curr_sl - symbol_info.point * 10): is_better = True
                            
                        if is_better:
                            update_sl(p.ticket, new_sl, comment)

                # C. COSECHA TACTICA (DESHABILITADA v15.25)
                # El Ratchet Suizo individual maneja cada posición. 
                # La cosecha cerraba prematuramente posiciones que seguían subiendo.
                # if current_open_pnl >= 12.0: 
                #     log(f"🧺 COSECHA TACTICA: +${current_open_pnl:.2f}. ¡ASEGURANDO META CORTA!")
                #     for p in open_positions: 
                #         if p.profit >= 1.20: close_ticket(p, "COSECHA_TACTICA")
                #     continue

                # v18.9.28: BOTÓN DE PÁNICO GLOBAL (REACTIVADO)
                if current_open_pnl <= MAX_SESSION_LOSS:
                    # v18.9.44: CIERRE POR PÁNICO DESACTIVADO (Decisión del Comandante)
                    log(f"🧘 VIGILANCIA VANGUARDIA: PnL {current_open_pnl:.2f}. Manteniendo posiciones por potencial de profit.")
                    # for p in open_positions: close_ticket(p, "PANIC_GLOBAL")
                    # stop_mission()
                    continue

            # --- 2. PROCESAMIENTO PARALELO (THE OCTOPUS) ---
            # ... (resto del loop) ...

            # --- PACMAN TIMER (Legacy cleanup) ---
            if (now_loop - pacman_timer) > PACMAN_DELAY:
                # Logic moved to main loop for speed
                pacman_timer = now_loop

            # ACTUALIZAR CONTADOR DE BALAS REAL (POSICIONES ABIERTAS TOTALES)
            try:
                all_account_pos = mt5.positions_get()
                bullet_count = len([p for p in all_account_pos if p.symbol == "XAUUSDm"]) if all_account_pos else 0
            except:
                bullet_count = 0
            
            # --- CALCULO DE PNL GLOBAL REAL (TRUE EQUITY SYNC) ---
            current_equity = get_equity()
            
            # v18.9.25: Solo calculamos PnL si la misión está activa para evitar confusión visual
            if mission_state.get("active", False):
                pnl = current_equity - mission_state.get("start_equity", current_equity)
                pnl = round(pnl, 2)
            else:
                pnl = 0.0
            
            # v12.0: DETECCIÓN DE VICTORIA INSTANTÁNEA (Sin Lag) (v15.41: +Active Check)
            target_val = mission_state.get("target", 0)
            if mission_state.get("active") and target_val > 0 and pnl >= target_val:
                 log(f"🎆 ¡META FINAL CUMPLIDA! PnL: ${pnl:.2f} >= ${target_val:.2f}")
                 st_time = mission_state.get("start_time", time.time())
                 stop_mission() 
                 generate_report(st_time)
                 STATE["active"] = False
                 # v15.39: Bot permanece vivo siempre
                 continue 
            
            # ACTUALIZAR REPORTE EN TIEMPO REAL
            with state_lock:
                STATE["daily_profit"] = pnl
                STATE["pnl"] = pnl 
                STATE["equity"] = current_equity
            
            # v16.0: Sincronización limpia de conteo de balas
            # Ya se calculó el bullet_count arriba usando el magic 777 de manera precisa.
            
            # eq = get_equity() # This line is now redundant as current_equity is calculated above
            with state_lock:
                STATE["bullets"] = bullet_count
                active = mission_state["active"]

            # --- v18.9.113: PULSO ADAPTATIVO FIX ---
            ping_start = time.perf_counter()
            target_pulse_sym = "XAUUSDm"
            tick_gold = mt5.symbol_info_tick(target_pulse_sym)
            if not tick_gold or (time.time() - tick_gold.time > 60):
                target_pulse_sym = "BTCUSDm"
                tick_gold = mt5.symbol_info_tick(target_pulse_sym)
            ping_end = time.perf_counter()


            
            # Solo actualizar si el dato de latencia es muy viejo (> 5s)
            if time.time() - LAST_LATENCY_UPDATE > 5.0:
                 lat_ping = (ping_end - ping_start) * 1000
                 with state_lock:
                     # El ping de info_tick es más rápido que trade, ajustamos factor x1.5 para realismo
                     LAST_LATENCY = lat_ping * 1.5 
                     LAST_LATENCY_UPDATE = time.time()

            # --- v15.84: CAJA NEGRA DE AUDITORIA (SOLO EN MISION) ---
            if not hasattr(metralleta_loop, "last_telemetry"): metralleta_loop.last_telemetry = 0
            
            # SOLO GRABAMOS SI HAY MISION ACTIVA
            with state_lock:
                is_mission_active = mission_state.get("active", False)

            if is_mission_active and (time.time() - metralleta_loop.last_telemetry) > 60:
                metralleta_loop.last_telemetry = time.time()
                try:
                    t_path = os.path.join(MQL5_FILES_PATH, "titan_telemetry.csv")
                    if not os.path.exists(t_path):
                        with open(t_path, "w") as f: f.write("Timestamp,Equity,PnL,Floating,Spread,Latency,Bullets\n")
                    
                    s_info = mt5.symbol_info(target_pulse_sym) if tick_gold else None
                    spread_val = (tick_gold.ask - tick_gold.bid) / s_info.point if tick_gold and s_info else 0


                    
                    row = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},{current_equity:.2f},{pnl:.2f},{current_open_pnl:.2f},{spread_val:.1f},{LAST_LATENCY:.0f},{bullet_count}\n"
                    with open(t_path, "a") as f: f.write(row)
                except: pass

            if tick_gold:
                with state_lock:
                    ph = STATE.get("price_history", [])
                    ph.append(tick_gold.bid)
                    if len(ph) > 50: ph.pop(0)
                    STATE["price_history"] = ph
                    
                    pts = STATE.get("price_timestamps", [])
                    pts.append(time.time())
                    if len(pts) > 50: pts.pop(0)
                    STATE["price_timestamps"] = pts
                # True PnL ya calculado arriba por True Equity Sync
                mission_state["last_profit"] = pnl
                
                # --- AUTO-SAVE PERSISTENCIA v7.74 ---
                # Guardar cada 5 segundos para que si Python muere, no se pierda la misión
                if int(now_loop) % 5 == 0:
                    save_mission_state()

                # --- ACTUALIZAR SNAPSHOTS PARA IMPACT SHIELD ---
                PNL_SNAPSHOTS.append((now_loop, pnl))
                if len(PNL_SNAPSHOTS) > 15: PNL_SNAPSHOTS.pop(0)


                if pnl > STATE.get("max_profit", -9999):
                     STATE["max_profit"] = pnl
                     mission_state["max_profit"] = pnl # Sincro para persistencia
                
                mission_state["last_pnl"] = pnl # Guardar pnl actual para recovery visual

                # ⚠️ EMERGENCY KILL (v15.57: LÓGICA RESTAURADA PERO "MODO ESPARTANO") ⚠️
                # SE MANTIENE EL CÓDIGO PERO DESACTIVADO POR ORDEN SUPERIOR ("TODO O NADA")
                
                # 1. Protección de Sesión (Límite Diario Absoluto)
                is_session_kill = pnl <= MAX_SESSION_LOSS
                
                # 2. Protección de Drawdown (DESACTIVADA)
                # max_p = float(STATE.get("max_profit", 0.0))
                # drawdown = pnl - max_p
                # is_drawdown_kill = drawdown <= MAX_SESSION_LOSS
                
                # 3. Protección de Posición Individual (Flash Crash - DESACTIVADA)
                # is_floating_kill = current_open_pnl <= (MAX_SESSION_LOSS - 5.0) 

                # v15.57: SOLO SE EJECUTARÍA SI SE REACTIVA LA PROTECCIÓN DE SESIÓN
                # if active and is_session_kill:
                #     log(f"💀 EMERGENCY KILL [SESIÓN]: PnL {pnl:.2f}. Abortando!")
                #     st_time_abort = mission_state.get("start_time", time.time())
                #     stop_mission()
                #     generate_report(st_time_abort)
                #     time.sleep(1)
                #     continue 

                # Save Market Status for APK
                m_warn = get_market_warning()
                with state_lock:
                    STATE["market_warning"] = m_warn if m_warn else "OPEN 🟢"
                    STATE["pnl"] = pnl


            # --- 2. PROCESAMIENTO PARALELO (THE OCTOPUS) ---
            futures = []
            for sym in SYMBOLS:
                # v18.9.95: FILTRO DE CEREBROS Y MERCADO
                # 1. Verificar si el cerebro está ON
                brain_on = True
                with state_lock:
                    if "XAU" in sym or "Gold" in sym: brain_on = STATE.get("oro_brain_on", True)
                    elif "BTC" in sym: brain_on = STATE.get("btc_brain_on", True)
                
                if not brain_on:
                    if time.time() % 60 < 1: log(f"💤 CEREBRO {sym} APAGADO (Manual)")
                    continue
                    
                # 2. Verificar si el mercado está abierto
                if is_market_closed(sym):
                    if time.time() % 300 < 1: log(f"🛑 MERCADO {sym} CERRADO - Durmiendo octopus...")
                    continue
                
                futures.append(executor_octopus.submit(process_symbol_task, sym, active, mission_state))
            
            report = []
            for f in futures:
                try:
                    res = f.result(timeout=2)
                    if res: report.append(res)
                except: continue

            # --- 2.1 RADAR MÚLTIPLE (ORDENAR POR CONFIANZA) ---
            radar_hits = sorted(report, key=lambda x: x['confidence'], reverse=True)
            best_asset = radar_hits[0] if radar_hits else None
            
            # --- 2.2 GENERAR CONSEJO HUMANO ---
            # --- 2.2 GENERAR CONSEJO HUMANO (v18.9.90: Heartbeat forzado con tiempo) ---
            if best_asset:
                human_text = get_human_advice(best_asset['signal'], best_asset['confidence'], best_asset['symbol'])
                STATE["human_advice"] = human_text
                STATE["last_best_sym"] = best_asset['symbol']
            else:
                STATE["human_advice"] = f"⌛ [{datetime.now().strftime('%H:%M:%S')}] SENTINEL: Escaneando activos..."

            # --- v7.8: SINCRONIZACIÓN DASHBOARD FINAL (ALWAYS RUN) ---
            if int(now_loop) % 2 == 0:
                try:
                    acc = mt5.account_info()
                    tick_oro = mt5.symbol_info_tick("XAUUSDm")
                    sym_info = mt5.symbol_info("XAUUSDm")
                    
                    # Consolidar alertas del buffer
                    alertas_list = list(LOG_BUFFER)
                    
                    # Formatear posiciones
                    pos_formatted = []
                    all_pos = mt5.positions_get()
                    if all_pos:
                        for p in all_pos:
                            if p.symbol in SYMBOLS or p.symbol == "XAUUSDm":
                                pos_formatted.append({
                                    "tipo": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                                    "open": p.price_open,
                                    "profit": p.profit + getattr(p, 'swap', 0) + getattr(p, 'commission', 0),
                                    "ticket": p.ticket,
                                    "symbol": p.symbol
                                })

                    current_pnl = 0.0
                    if mission_state.get("active"):
                        current_pnl = (acc.equity - mission_state.get("start_equity", acc.equity)) if acc else 0
                    
                    # Calcular progreso hacia la meta de 500% ($34.79 * 5 = $173.95)
                    goal_usd = 173.95
                    progress_pct = min(100, max(0, (current_pnl / goal_usd) * 100)) if current_pnl > 0 else 0
                    
                    ai_status = STATE.get("last_ollama_res", "Ollama Sentinel Active")
                    
                    fb_payload = {
                        "ts": datetime.now().isoformat(),
                        "balance": acc.balance if acc else 0,
                        "equity": acc.equity if acc else 0,
                        "total_float": current_open_pnl,
                        "pnl": round(current_pnl, 2),
                        "goal_progress": round(progress_pct, 1),
                        "goal_usd": goal_usd,
                        "bid": tick_oro.bid if tick_oro else (STATE.get("price_history", [0])[-1] if STATE.get("price_history") else 0),
                        "ask": tick_oro.ask if tick_oro else 0,
                        "spread": (tick_oro.ask - tick_oro.bid) / sym_info.point if (tick_oro and sym_info) else 0,
                        "rsi": report[0].get("rsi", 50) if report and len(report)>0 else 50,
                        "bb_pos": report[0].get("bb_pos", 0.5) if report and len(report)>0 else 0.5,
                        "m5_trend": report[0].get("m5_trend", "⚪") if report and len(report)>0 else "⚪",
                        "h1_trend": report[0].get("h1_trend", "NEUTRAL") if report and len(report)>0 else "NEUTRAL",
                        "margin_level": acc.margin_level if (acc and acc.margin_level > 0) else 2000.0,
                        "pos": pos_formatted,
                        "gemini": STATE.get("human_advice", "VIGILANCIA TÁCTICA ACTIVA"),
                        "ai_insight": ai_status,
                        "radar": radar_hits[:10] if 'radar_hits' in locals() else [],
                        "last_best_sym": STATE.get("last_best_sym", "XAUUSDm"),
                        "alertas": alertas_list[-15:],
                        "health": {"mt5": True if acc else False, "ai": "FAILED" not in ai_status},
                        "active": mission_state.get("active", False),
                        "market": get_market_warning() or "OPEN 🟢",
                        "oro_brain_on": STATE.get("oro_brain_on", True),
                        "btc_brain_on": STATE.get("btc_brain_on", True),
                        "auto_mode": STATE.get("auto_mode", False)
                    }
                    push_firebase(fb_payload)
                except Exception as fe:
                    if int(now_loop) % 10 == 0: log(f"⚠️ Error Sincro Dashboard: {fe}")

            # --- 3. GESTIÓN DE MISIÓN & REPORTES ---
            if active:
                if (mission_state.get("target", 0) > 0 and pnl >= mission_state["target"]):
                    log(f"🎯 META ALCANZADA: PnL {pnl:.2f}. Misión exitosa.")
                    start_ts = mission_state.get("start_time", time.time())
                    stop_mission()
                    time.sleep(2)
                    generate_report(start_ts)
                    LAST_MISSION_TIME = time.time()
                    continue
                elif pnl <= MAX_SESSION_LOSS:
                    log(f"💀 EMERGENCY KILL: PnL {pnl:.2f} alcanzó límite crítico de pérdida ({MAX_SESSION_LOSS}).")
                    start_ts = mission_state.get("start_time", time.time())
                    stop_mission()
                    time.sleep(2)
                    generate_report(start_ts)
                    LAST_MISSION_TIME = time.time()
                    continue

            # --- CAPTURA DE DATOS PARA GRÁFICO (VELAS) ---
            try:
                # Usar el simbolo configurado por defecto
                target_sym = "XAUUSDm" # Default preference
                
                # Intentar encontrar el oro en la config actual
                if "XAUUSDm" in ASSET_CONFIG: target_sym = "XAUUSDm"
                elif "XAUUSD" in ASSET_CONFIG: target_sym = "XAUUSD"
                elif "GOLD" in ASSET_CONFIG: target_sym = "GOLD"
                elif len(ASSET_CONFIG) > 0: target_sym = list(ASSET_CONFIG.keys())[0] # Fallback al primero 
                
                # 1. M1 CANDLES
                rates_m1 = mt5.copy_rates_from_pos(target_sym, mt5.TIMEFRAME_M1, 0, 30)
                if rates_m1 is None: # Si falla, probar XAUUSD pelado
                     rates_m1 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 30)
                
                if rates_m1 is not None and len(rates_m1) > 20:
                     # Calcular Bollinger Bands (20, 2)
                     df_bb = pd.DataFrame(rates_m1)
                     indicator_bb = ta.volatility.BollingerBands(close=df_bb['close'], window=20, window_dev=2)
                     df_bb['bb_h'] = indicator_bb.bollinger_hband()
                     df_bb['bb_m'] = indicator_bb.bollinger_mavg()
                     df_bb['bb_l'] = indicator_bb.bollinger_lband()
                     
                     # Convertir numpy array a lista de dicts con BB
                     data = []
                     # v18.9.20: Limitar a 20 velas para la APK (Reducir peso JSON y evitar crasheos)
                     for i, r in df_bb.tail(20).iterrows():
                         data.append({
                             "o": float(r['open']), 
                             "h": float(r['high']), 
                             "l": float(r['low']), 
                             "c": float(r['close']),
                             "bb_h": float(r['bb_h']) if not pd.isna(r['bb_h']) else None,
                             "bb_m": float(r['bb_m']) if not pd.isna(r['bb_m']) else None,
                             "bb_l": float(r['bb_l']) if not pd.isna(r['bb_l']) else None
                         })
                     STATE["candles_m1"] = data # Guardar en STATE con BB 🪐
                
                # 2. M5 CANDLES
                rates_m5 = mt5.copy_rates_from_pos(target_sym, mt5.TIMEFRAME_M5, 0, 30)
                if rates_m5 is None: 
                     rates_m5 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 30)

                if rates_m5 is not None and len(rates_m5) > 0:
                     data = []
                     for r in rates_m5:
                         data.append({
                             "o": float(r['open']), 
                             "h": float(r['high']), 
                             "l": float(r['low']), 
                             "c": float(r['close'])
                         })
                     STATE["candles_m5"] = data

            except Exception as e:
                log(f"⚠️ Error fetching candles: {e}")

            # --- 4. AUTO-PILOT AI (GOD MODE) ---
            highest_conf = 0.0
            best_asset = None
            
            for r in report:
                if r['confidence'] > highest_conf:
                    highest_conf = r['confidence']
                    best_asset = r
            
            # AUTO START LOGIC (v18.9.89: AGRESIVIDAD FIN DE SEMANA)
            if STATE.get("auto_pilot", True) and not mission_state["active"]:
                cooldown_passed = (time.time() - LAST_MISSION_TIME) > 2 # Reducido a 2s
                if highest_conf >= 0.45 and cooldown_passed: # Umbral más bajo para BTC
                    log(f"🚀 AUTO-PILOT RELOADED! {highest_conf*100:.1f}% Confianza. GO!")
                    start_mission(None, target_profit=50.0)
                elif highest_conf >= 0.85 and not cooldown_passed:
                    remaining = int(300 - (now_loop - LAST_MISSION_TIME))
                    if now_loop % 10 < 1: # Solo loguear cada tanto
                        log(f"⏳ COOLDOWN ACTIVO: Esperando {remaining}s para nueva misión tras éxito.")
            # TACTICAL ADVICE GENERATION
            advice = "MARKET NEUTRAL. WAITING FOR CATALYST."
            if best_asset:
                s_sym = best_asset['symbol']
                c_conf = int(best_asset['confidence'] * 100)
                rsi_val = float(best_asset['rsi'])
                sig = best_asset['signal']
                
                if c_conf > 90: advice = f"⚠️ CRITICAL OPPORTUNITY ON {s_sym}! {c_conf}% PROBABILITY."
                elif c_conf > 80: advice = f"STRONG SIGNAL ({s_sym}). {sig} LIKLEY."
                elif rsi_val > 75: advice = f"{s_sym} OVERBOUGHT (RSI {int(rsi_val)}). WATCH REVERSAL."
                elif rsi_val < 25: advice = f"{s_sym} OVERSOLD (RSI {int(rsi_val)}). POTENTIAL BOUNCE."
                elif mission_state["active"]: 
                    pnl_val = STATE.get("daily_profit", 0.0)
                    if pnl_val > 0: advice = f"WINNING POSITION ({pnl_val:.2f}). TRAILING STOP ACTIVE."
                    else: advice = "MARKET VOLATILITY HIGH. HOLD POSITIONS. TRUST THE ALGO."
            
            with state_lock:
                STATE["advice"] = advice
                STATE["active_pairs"] = report
            
            # Calc Elapsed Time
            elapsed = "00:00:00"
            start_t = mission_state.get("start_time", time.time())
            end_t = time.time() if mission_state["active"] else mission_state.get("end_time", time.time())
            
            if start_t > 0:
                 elapsed = str(timedelta(seconds=int(end_t - start_t)))
            
            print_dashboard(report, elapsed)
            time.sleep(1)
            
        except Exception as e:
            log(f"❌ CRITICAL LOOP CRASH: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)


# ============ JSON ENCODER (FIX FLOAT32 ERROR) ============
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): 
            if np.isnan(obj): return 0.0 # NaN -> 0.0 (Safe for non-null Double)
            if np.isinf(obj): return 999999.0 
            return float(obj)
        if isinstance(obj, float):
            if math.isnan(obj): return 0.0
            if math.isinf(obj): return 999999.0
            return obj
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

# ============ TITAN FASTAPI BRIDGE (v7.15.1) ============
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Global variables for notifications (if needed, define them here)
# For example:
# NOTIFICATION_QUEUE = [] 

app = FastAPI(title="TITAN BRIDGE AI v4.0", version="7.54")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINT LEGACY PARA LA APK ---
@app.get("/status")
async def get_status_legacy():
    global mission_state
    try:
        with state_lock:
            pnl = STATE.get("pnl", 0.0)
            bullets = int(STATE.get("bullets", 0))
            equity = float(STATE.get("equity", 0.0))
            balance = float(STATE.get("balance", 0.0))
            max_p = float(STATE.get("max_profit", 0.0))
            advice = STATE.get("advice", "TITAN ONLINE")
            auto_pilot = bool(STATE.get("auto_pilot", False))
            active_list = STATE.get("active_pairs", [])
            price_history = list(STATE.get("price_history", []))[-50:]
            candles_m1 = STATE.get("candles_m1", [])
            candles_m5 = STATE.get("candles_m5", [])
        tgt = float(mission_state.get("target", 50.0))
        if tgt <= 0: tgt = 50.0
        start_t = mission_state.get("start_time", time.time())
        end_t = time.time() if mission_state["active"] else mission_state.get("end_time", time.time())
        elapsed_str = str(timedelta(seconds=int(end_t - start_t))) if start_t > 0 else "00:00:00"
        
        clean_pairs = []
        if isinstance(active_list, dict): 
            for s, d in active_list.items():
                clean_pairs.append({
                    "symbol": s,
                    "signal": d.get("signal", "HOLD"),
                    "confidence": float(d.get("confidence", 0)),
                    "ai": float(d.get("ai", 0)),
                    "rsi": float(d.get("rsi", 0)),
                    "lot": float(d.get("lot", 0.03)),
                    "state": d.get("state", "WAIT")
                })
        else:
            for p in active_list:
                clean_pairs.append({
                    "symbol": p.get("symbol", ""),
                    "signal": p.get("signal", "HOLD"),
                    "confidence": float(p.get("confidence", 0)),
                    "ai": float(p.get("ai", 0)),
                    "rsi": float(p.get("rsi", 0)),
                    "lot": float(p.get("lot", 0.03)),
                    "state": p.get("state", "WAIT")
                })

        tick = mt5.symbol_info_tick("XAUUSDm")
        spr = (tick.ask - tick.bid) / 0.01 if tick else 0 # 0.01 fix para puntos
        return {
            "balance": float(balance),
            "equity": float(equity),
            "daily_profit": float(pnl),
            "bullets": int(bullets),
            "trail_max": float(max_p),
            "spread": float(spr), # Spread para la APK
            "streak": int(wins_today if 'wins_today' in locals() else 0),
            "active_pairs": clean_pairs,
            "instruments": clean_pairs, 
            "mission": {
                "active": mission_state["active"],
                "target": float(tgt),
                "current": float(pnl),
                "progress": float((pnl / tgt) * 100 if tgt > 0 else 0),
                "time_str": elapsed_str,
                "elapsed": int(end_t - start_t) if start_t > 0 else 0
            },
            "history": list(MISSION_HISTORY)[-100:] if MISSION_HISTORY else [],
            "system": {"cpu": 0, "ram": 0, "ping": 0},
            "price_history": price_history,
            "candles_m1": candles_m1,
            "candles_m2": candles_m5, # Compatibilidad
            "candles_m5": candles_m5,
            "advice": advice,
            "auto_pilot": auto_pilot,
            "market_warning": STATE.get("market_warning", "OPEN 🟢"),
            "oro_brain_on": STATE.get("oro_brain_on", True),
            "btc_brain_on": STATE.get("btc_brain_on", True),
            "symbol": "XAUUSDm",
            "lot": 0.03
        }
    except Exception as e:
        log(f"⚠️ Status Legacy Error: {e}")
        return {"error": str(e)}

@app.get("/")
async def get_dashboard():
    global mission_state
    try:
        tgt = mission_state.get("target_profit", 50.0)
        pnl = mission_state.get("daily_profit", 0.0)
        prog = (pnl / tgt) * 100 if tgt > 0 else 0
        
        start_t = mission_state.get("start_time", time.time())
        end_t = time.time() if mission_state["active"] else mission_state.get("end_time", time.time())
        elapsed = str(timedelta(seconds=int(end_t - start_t))) if start_t > 0 else "00:00:00"

        # HISTORY_BUFFER is not defined in the provided snippet, assuming it's a global list/deque
        # hist = list(HISTORY_BUFFER) 
        # hist_slice = hist[-15:] if len(hist) > 15 else hist
        
        clean_pairs = []
        with state_lock:
            active_list = STATE.get("active_pairs", [])
            for d in active_list:
                clean_pairs.append({
                    "symbol": d.get("symbol", ""),
                    "signal": d.get("signal", "HOLD"),
                    "confidence": d.get("confidence", 0),
                    "pnl": d.get("pnl", 0),
                    "lot": d.get("lot", 0),
                    "state": d.get("state", "WAIT")
                })

        return {
            "status": "ONLINE",
            "version": "7.22",
            "trend": "OCTOPUS NEURONAL 🐙",
            "active_pairs": clean_pairs,
            "mission": {
                "active": mission_state["active"],
                "target": float(tgt),
                "current": float(pnl),
                "progress": float(min(max(prog, 0.0), 100.0)),
                "time_str": elapsed
            },
            "advice": STATE.get("advice", "VIGILANCIA TÁCTICA ACTIVA"),
            "market_warning": STATE.get("market_warning", "OPEN 🟢"),
            "market": STATE.get("market_warning", "OPEN 🟢"),
            "oro_brain_on": STATE.get("oro_brain_on", True),
            "btc_brain_on": STATE.get("btc_brain_on", True)
        }
    except Exception as e:
        log(f"⚠️ API Error (get_dashboard): {e}")
        return {"error": str(e)}

@app.get("/logs")
async def get_logs():
    # LOG_BUFFER is not defined in the provided snippet, assuming it's a global list/deque
    return list(LOG_BUFFER)

@app.get("/mission")
async def get_mission():
    return mission_state

@app.post("/control/brain")
async def toggle_brain(brain: str, status: bool):
    """ v18.9.95: Control Remoto de Cerebros """
    global STATE
    with state_lock:
        if brain.upper() == "ORO":
            STATE["oro_brain_on"] = status
            log(f"🧠 MANDO: Cerebro ORO {'ACTIVADO' if status else 'DESACTIVADO'}")
        elif brain.upper() == "BTC":
            STATE["btc_brain_on"] = status
            log(f"🧠 MANDO: Cerebro BTC {'ACTIVADO' if status else 'DESACTIVADO'}")
        else:
            return {"error": "Cerebro no reconocido. Usa ORO o BTC."}
    return {"status": "ok", "brain": brain, "active": status}

@app.get("/ping")
async def ping():
    return {"status": "pong", "time": time.time(), "version": "18.9.100"}

@app.post("/command")
async def post_command(request: Request):
    global LAST_MISSION_TIME
    try:
        d = await request.json()
        action = d.get("action", "").upper()
        if not action: action = d.get("command", "").upper()
        
        log(f"📨 COMANDO API: {action} | {d}")
        atomic_write(CMD_FILE_PATH, f"{action}:{d.get('target','')}")

        if action in ["START", "START_MISSION"]:
            # v15.66: BLOQUEO DE API EN HORARIO PROHIBIDO
            # 18:30 a 20:05 Chile
            ahora = datetime.fromtimestamp(time.time() + 0) # Asumimos server time = local time
            h, m = ahora.hour, ahora.minute
            
            is_blocked = False
            if h == 18 and m >= 30: is_blocked = True
            elif h == 19: is_blocked = True
            elif h == 20 and m < 5: is_blocked = True
            
            # BYPASS DE EMERGENCIA: Si el comando viene con 'force': True
            if is_blocked and not d.get("force", False):
                log(f"⛔ COMANDO START BLOQUEADO: Mercado Cerrado (18:30-20:05)")
                return {"status": "DENIED", "reason": "MERCADO CERRADO"}

            tgt = d.get("target") or d.get("meta") or 50.0
            lot = d.get("lot")
            if not lot and "params" in d: lot = d["params"].get("lot")
            if lot and float(lot) > 0:
                nl = float(lot)
                with state_lock:
                    for k in ASSET_CONFIG: ASSET_CONFIG[k]["lot"] = nl
                    DEFAULT_CONFIG["lot"] = nl
            LAST_MISSION_TIME = 0 
            start_mission(target_profit=float(tgt))
            # v15.38: Forzar refresco visual e impresión inmediata
            with state_lock: STATE["pnl"] = 0.0
            # Pequeño trigger para que el loop principal despierte y pinte
            LAST_DASHBOARD_REFRESH = 0 
        
        elif action == "AUTO":
            with state_lock:
                act = STATE.get("auto_pilot", False)
                STATE["auto_pilot"] = not act
                save_settings()
        
        elif action in ["STOP", "STOP_MISSION"]: # Changed from "STOP", "STOP_MISSION" to ["STOP", "STOP_MISSION"]
            s_ts = mission_state.get("start_time", 0)
            with state_lock: STATE["auto_pilot"] = False
            save_settings()
            stop_mission()
            generate_report(s_ts)

        return {"status": "EXECUTED", "cmd": action}
    except Exception as e:
        log(f"⚠️ POST Error (post_command): {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    try:
        # v18.9.84: Validación PRE-VUELO (Evitar Predict Err)
        global_health_check()
        
        t = threading.Thread(target=metralleta_loop, daemon=True)
        t.start()
        
        # v18.9.97: Iniciar poller de mandos web
        t2 = threading.Thread(target=firebase_command_poller, daemon=True)
        t2.start()
        
        log(f"🚀 TITAN BRAIN ONLINE @ PORT {PORT} (FASTAPI MODE)")
        # v18.9.111: Blindaje de Uvicorn y bucle de persistencia
        try:
            uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="error")
        except Exception as uv_e:
            log(f"⚠️ Uvicorn detenido inesperadamente: {uv_e}")

        log("🧥 MODO PERSISTENCIA ACTIVADO: Evitando cierre de ventana...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("🛑 APAGADO MANUAL")
    except Exception as e:
        error_msg = f"\n💥 ERROR FATAL (v18.9.112): {e}\n{traceback.format_exc()}"
        log(error_msg)
        print(error_msg)
        print("\n🧥 [ESCUDO] BLOQUEANDO CIERRE DE VENTANA POST-ERROR...")
        while True:
            time.sleep(1)


