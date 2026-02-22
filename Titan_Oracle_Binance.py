import websocket
import json
import time
import os

# --- CONEXIÓN DE BAJA LATENCIA BINANCE (WEBSOCKETS) ---
# Leemos los trades en tiempo real para anticiparnos al Broker
# Usamos el par BTCUSDT de Binance

SYMBOL_BINANCE = "btcusdt"
SOCKET = f"wss://stream.binance.com:9443/ws/{SYMBOL_BINANCE}@aggTrade"

# Umbrales para considerarlo una "Ballena" (Whale)
WHALE_VOLUME_USD = 150000  # $150k USD: Umbral agresivo para volumen de 500+ trades/día
FILE_SIGNAL = "titan_oracle_signal.json"

STATE = {
    "recent_buys": 0.0,
    "recent_sells": 0.0,
    "last_reset": time.time()
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
        # Atomic write
        temp_file = FILE_SIGNAL + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f)
        os.replace(temp_file, FILE_SIGNAL)
        print(f"[{time.strftime('%H:%M:%S')}] 🔥 SEÑAL DISPARADA A TITAN: {signal} ({side} de ${volume:,.0f})")
    except Exception as e:
        print(f"Error escribiendo señal: {e}")

def on_message(ws, message):
    global STATE
    # json structure:
    # {
    #   "e": "aggTrade",  // Event type
    #   "E": 123456789,   // Event time
    #   "s": "BTCUSDT",    // Symbol
    #   "a": 12345,       // Aggregate trade ID
    #   "p": "0.001",     // Price
    #   "q": "100",       // Quantity
    #   "f": 100,         // First breakdown trade ID
    #   "l": 105,         // Last breakdown trade ID
    #   "T": 123456785,   // Trade time
    #   "m": true,        // Is the buyer the market maker?
    #   "M": true         // Ignore
    # }
    try:
        data = json.loads(message)
        price = float(data['p'])
        qty = float(data['q'])
        is_buyer_maker = data['m']  # If true, it means it's a SELL order triggering (buyer is maker). If false, it's a BUY order (seller is maker).
        
        volume_usd = price * qty
        
        now = time.time()
        
        # Reset accumulator every 1 second
        if now - STATE["last_reset"] > 1.0:
            STATE["recent_buys"] = 0.0
            STATE["recent_sells"] = 0.0
            STATE["last_reset"] = now
        
        if is_buyer_maker:
            # SELL
            STATE["recent_sells"] += volume_usd
        else:
            # BUY
            STATE["recent_buys"] += volume_usd
            
        # Detectar ballenas al instante (1 tick) o ráfagas continuas de 1 segundo
        if volume_usd >= WHALE_VOLUME_USD or STATE["recent_buys"] >= WHALE_VOLUME_USD * 1.5:
            # Mucha presión compradora muy rápida (Lead-Lag, Binance sube antes que MT5)
            write_signal("BUY", "COMPRA", max(volume_usd, STATE["recent_buys"]))
            STATE["recent_buys"] = 0.0 # Reset
            
        elif volume_usd >= WHALE_VOLUME_USD or STATE["recent_sells"] >= WHALE_VOLUME_USD * 1.5:
             write_signal("SELL", "VENTA", max(volume_usd, STATE["recent_sells"]))
             STATE["recent_sells"] = 0.0 # Reset
             
    except Exception as e:
        # Silenciar errores menores de parseo
        pass

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### CONEXIÓN BINANCE CERRADA ###")
    print("Reconectando en 3 segundos...")
    time.sleep(3)
    start_oracle()

def on_open(ws):
    print("=========================================================")
    print("👁️  TITAN ORACLE: CONECTADO AL CABLE SUBMARINO BINANCE")
    print(f"🎯 Escaneando Ballenas en BTC/USDT (Umbral: ${WHALE_VOLUME_USD:,.0f} por segundo)")
    print("=========================================================")

def start_oracle():
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(SOCKET,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    ws.run_forever()

if __name__ == "__main__":
    start_oracle()
