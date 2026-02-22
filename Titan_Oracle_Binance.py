import json
import time
import os
import websocket
import threading

# --- TITAN ORACLE BINANCE v18.9.106 ---
# Este script lee el stream de Binance y detecta ballenas en tiempo real.
# v18.9.106: Corregido error de acceso a archivos (WinError 32) y persistencia.

SYMBOL_BINANCE = "btcusdt"
# Umbral para considerarlo una "Ballena" (Whale)
WHALE_VOLUME_USD = 75000  # $75k USD: Umbral agresivo para entrar al inicio de la vela
MINI_WHALE_THRESHOLD = 30000 # $30k USD: Para alertas visuales de presión
FILE_SIGNAL = "titan_oracle_signal.json"


STATE = {
    "recent_buys": 0.0,
    "recent_sells": 0.0,
    "last_reset": time.time(),
    "last_heartbeat": time.time(), # v18.9.117
    "triggered_this_sec": False # v18.9.118: Anti-spam por segundo
}


def write_signal(signal, side, volume):
    data = {
        "timestamp": time.time(),
        "source": "BINANCE_ORACLE",
        "symbol": "BTCUSDm",  # Equivalente en MT5
        "signal": signal,
        "confidence": 1.0,
        "reason": f"🐋 BALLENA DETECTADA: {side} ${volume:,.0f} USD"
    }
    try:
        temp_file = FILE_SIGNAL + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f)
        # os.replace es atómico en la mayoría de los sistemas, pero en Windows
        # si otro proceso tiene abierto el archivo destino, fallará.
        # Por eso el Brain debe abrirlo/cerrarlo rápido y manejar el error.
        os.replace(temp_file, FILE_SIGNAL)
        print(f"[{time.strftime('%H:%M:%S')}] 🔥 SEÑAL DISPARADA A TITAN: {signal} ({side} de ${volume:,.0f})")
    except Exception as e:
        # Si falla por acceso, simplemente ignoramos este tick para no crashear
        pass

def on_message(ws, message):
    global STATE
    try:
        data = json.loads(message)
        price = float(data['p'])
        qty = float(data['q'])
        is_buyer_maker = data['m']
        
        volume_usd = price * qty
        now = time.time()
        
        # Reset accumulator every 1.5 seconds para atrapar ballenas que inyectan más lento
        if now - STATE["last_reset"] > 1.5:
            STATE["recent_buys"] = 0.0
            STATE["recent_sells"] = 0.0
            STATE["last_reset"] = now
            STATE["triggered_this_sec"] = False
            
        if is_buyer_maker: # SELL PRESSURE
            STATE["recent_sells"] += volume_usd
            if STATE["recent_sells"] > WHALE_VOLUME_USD and not STATE["triggered_this_sec"]:
                write_signal("SELL", "VENTA ACUMULADA", STATE["recent_sells"])
                STATE["triggered_this_sec"] = True
            elif STATE["recent_sells"] > MINI_WHALE_THRESHOLD and not STATE["triggered_this_sec"]:
                if now % 2 < 0.1: # Evitar spam en consola
                    print(f"[{time.strftime('%H:%M:%S')}] 📉 PRESIÓN DE VENTA: ${STATE['recent_sells']:,.0f} USD")
        else: # BUY PRESSURE
            STATE["recent_buys"] += volume_usd
            if STATE["recent_buys"] > WHALE_VOLUME_USD and not STATE["triggered_this_sec"]:
                write_signal("BUY", "COMPRA ACUMULADA", STATE["recent_buys"])
                STATE["triggered_this_sec"] = True
            elif STATE["recent_buys"] > MINI_WHALE_THRESHOLD and not STATE["triggered_this_sec"]:
                if now % 2 < 0.1:
                    print(f"[{time.strftime('%H:%M:%S')}] 📈 PRESIÓN DE COMPRA: ${STATE['recent_buys']:,.0f} USD")

                
        # v18.9.117: Heartbeat visual cada 10s para confirmar vida
        if now - STATE["last_heartbeat"] > 10.0:
            print(f"[{time.strftime('%H:%M:%S')}] 💓 ORACLE VIVE | Vigilando Binance...")
            STATE["last_heartbeat"] = now

                
    except Exception as e:
        print(f"⚠️ Error en stream: {e}")

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🛑 Conexión con Binance cerrada. Reintentando...")
    time.sleep(5)
    start_oracle()

def on_open(ws):
    print("======================================================")
    print("👁️  TITAN ORACLE: CONECTADO AL CABLE SUBMARINO BINANCE")
    print(f"🎯 Escaneando Ballenas en BTC/USDT (Umbral: ${WHALE_VOLUME_USD:,.0f} por segundo)")
    print("======================================================")

def start_oracle():
    ws_url = f"wss://stream.binance.com:9443/ws/{SYMBOL_BINANCE}@aggTrade"
    ws = websocket.WebSocketApp(ws_url,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    ws.run_forever()

if __name__ == "__main__":
    start_oracle()
