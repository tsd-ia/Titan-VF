
import time
import json
import os
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import MetaTrader5 as mt5

# Configuración de Red
PORT = 8000

class TitanBrain:
    def __init__(self):
        self.last_bias = 0
        self.last_change = 0
        self.data_path = ""
        self.setup_mt5()
        
    def setup_mt5(self):
        if not mt5.initialize():
            print("❌ Error: No se pudo conectar a MetaTrader 5")
            return False
        
        info = mt5.terminal_info()
        if info:
            # Ruta de archivos de MT5 (Sandbox)
            self.data_path = os.path.join(info.data_path, 'MQL5', 'Files')
            print(f"✅ Sincronizado con MT5 en: {self.data_path}")
            return True
        return False

    def get_market_data(self):
        if not self.data_path: self.setup_mt5()
        status_file = os.path.join(self.data_path, "titan_status.json")
        try:
            if os.path.exists(status_file):
                with open(status_file, "r") as f:
                    return json.load(f)
        except:
            pass
        return None

    def save_signal(self, bias, symbol, lot):
        if not self.data_path: self.setup_mt5()
        signal_file = os.path.join(self.data_path, "titan_mission.txt")
        try:
            ts = int(time.time())
            # POR SEGURIDAD: SIEMPRE INICIA EN 0 (STANDBY) HASTA NUEVA ORDEN
            is_active = 0 
            with open(signal_file, "w") as f:
                f.write(f"{is_active} {symbol} {lot} {bias} {ts}")
        except Exception as e:
            print(f"Error guardando señal: {e}")

brain_hft = TitanBrain()

def process_logic():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("======================================================================")
    print("👑 TITAN CORE v9.5 - BRIDGE MODE (ULTRA STABLE)                       ")
    print("======================================================================")
    
    while True:
        data = brain_hft.get_market_data()
        if data:
            live_data = data.get("live", {})
            m5_data = data.get("m5", {})
            pnl = live_data.get("pnl", 0)
            symbol = live_data.get("symbol", "XAUUSDm")
            vol_acc = live_data.get("vol_acc", 1.0)
            rsi_val = live_data.get("rsi", 50)
            ema_fast = live_data.get("ema_fast", 0)
            bias_m5 = m5_data.get("bias", 0)
            current_price = live_data.get("price", 0)
            
            voted_bias = 0
            entry_log = "⌛ ANALIZANDO TENDENCIA..."

            # Lógica de Seguridad v9.5
            is_system_active = 0 # POR DEFECTO APAGADO
            
            if bias_m5 == 1: 
                if current_price > ema_fast:
                    voted_bias = 1
                    entry_log = "🚀 COMPRA SEGURA 🟢"
                else: entry_log = "⌛ ESPERANDO RUPTURA ALCISTA..."
            elif bias_m5 == -1: 
                if current_price < ema_fast:
                    voted_bias = -1
                    entry_log = "💣 VENTA SEGURA 🔴"
                else: entry_log = "⌛ ESPERANDO RUPTURA BAJISTA..."

            now = time.time()
            if voted_bias != brain_hft.last_bias:
                if (now - brain_hft.last_change > 0.5):
                    brain_hft.last_bias = voted_bias
                    brain_hft.last_change = now
            
            # SI ESTAMOS EN MODO MANUAL/STANDBY, NO ENVIAR SEÑAL DE DISPARO
            final_signal = brain_hft.last_bias if is_system_active else 0
            
            brain_hft.save_signal(final_signal, symbol, 0.01)
            
            os.system('cls' if os.name == 'nt' else 'clear')
            print("======================================================================")
            print(f"👑 TITAN CORE v9.5 - TREND PROTECTOR (ACTIVO)                      ")
            print("======================================================================")
            print(f"ESTADO TENDENCIA: {'🟢 ALCISTA' if bias_m5 == 1 else '🔴 BAJISTA' if bias_m5 == -1 else '⚪ NEUTRO'}")
            print(f"INDICADOR: {entry_log}")
            print(f"PRECIO: {current_price:.2f} | EMA: {ema_fast:.2f}")
            print("----------------------------------------------------------------------")
            print(f"PNL: ${pnl:.2f} | SIGNAL: {'BUY' if brain_hft.last_bias == 1 else 'SELL' if brain_hft.last_bias == -1 else 'WAIT'}")
            print("======================================================================")
        else:
            # os.system('cls' if os.name == 'nt' else 'clear')
            print("\r😴 ESPERANDO DATOS DE MT5 (Verifica que el EA esté activo en MT5)...", end="")

        time.sleep(0.5)

class TitanHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            data = brain_hft.get_market_data()
            self.wfile.write(json.dumps(data).encode())
    def log_message(self, format, *args): return 

def run_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), TitanHandler)
        server.serve_forever()
    except Exception as e:
        print(f"❌ ERROR DE RED: {e}")

if __name__ == "__main__":
    t = threading.Thread(target=process_logic, daemon=True)
    t.start()
    run_server()
