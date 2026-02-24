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
WHALE_VOLUME_USD = 220000  # $220k USD: Umbral solicitado por Comandante (Evitar ruido)
MINI_WHALE_THRESHOLD = 80000  # $80k USD: Alertas de presión real
FILE_SIGNAL = "titan_oracle_signal.json"


STATE = {
    "buys_window": [],  # Lista de tuplas (timestamp, volume)
    "sells_window": [],
    "last_heartbeat": time.time(),
    "last_signal_time": 0.0, # Para evitar spam del mismo lado en periodos cortos
    "last_price": 0.0
}


def write_signal(signal, side, volume):
    data = {
        "timestamp": time.time(),
        "source": "BINANCE_ORACLE",
        "symbol": "BTCUSDm",  # Equivalente en MT5
        "signal": signal,
        "volume": volume,
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
        
        # Limpiar operaciones fuera de la ventana de 1.2 segundos (Ultra HFT)
        window_size = 1.2
        STATE["buys_window"] = [(ts, vol) for ts, vol in STATE["buys_window"] if now - ts <= window_size]
        STATE["sells_window"] = [(ts, vol) for ts, vol in STATE["sells_window"] if now - ts <= window_size]
        
        # CORRECCIÓN COMANDANTE: Seguir al Agresor (Taker), no al Maker (Atrapado)
        # m = True -> El Comprador es Maker -> El VENDEDOR es Taker (Agresor) -> SELL
        # m = False -> El Vendedor es Maker -> El COMPRADOR es Taker (Agresor) -> BUY
        if is_buyer_maker: 
            STATE["sells_window"].append((now, volume_usd))
        else: 
            STATE["buys_window"].append((now, volume_usd))

            
        total_sells = sum(vol for ts, vol in STATE["sells_window"])
        total_buys = sum(vol for ts, vol in STATE["buys_window"])
        
        # v18.9.140: CONFIRMACIÓN DE PRECIO (Evitar atrapar ventas absorbidas por compras)
        price_confirm_sell = (price <= STATE["last_price"]) if STATE["last_price"] > 0 else True
        price_confirm_buy = (price >= STATE["last_price"]) if STATE["last_price"] > 0 else True

        # Anti-spam: No disparar misma señal en menos de 1 segundo de la anterior
        can_trigger = (now - STATE["last_signal_time"]) > 1.0
        
        if total_sells > WHALE_VOLUME_USD and can_trigger and price_confirm_sell:
            write_signal("SELL", "VENTA ACUMULADA", total_sells)
            STATE["last_signal_time"] = now
            STATE["sells_window"].clear()
        elif total_sells > MINI_WHALE_THRESHOLD and now % 3 < 0.1:
            print(f"[{time.strftime('%H:%M:%S')}] 📉 PRESIÓN DE VENTA CONTINUA: ${total_sells:,.0f} USD")
            
        if total_buys > WHALE_VOLUME_USD and can_trigger and price_confirm_buy:
            write_signal("BUY", "COMPRA ACUMULADA", total_buys)
            STATE["last_signal_time"] = now
            STATE["buys_window"].clear()
        elif total_buys > MINI_WHALE_THRESHOLD and now % 3 < 0.1:
            print(f"[{time.strftime('%H:%M:%S')}] 📈 PRESIÓN DE COMPRA CONTINUA: ${total_buys:,.0f} USD")

        STATE["last_price"] = price

                
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
    # --- v18.9.195: ACTIVACIÓN SELECTIVA (Solo si el Jefe dice ON) ---
    import requests
    FIREBASE_URL = "https://titan-sentinel-default-rtdb.firebaseio.com/live/btc_brain_on.json"
    try:
        res = requests.get(FIREBASE_URL, timeout=5)
        if res.status_code == 200 and res.json() == False:
            print("💤 CEREBRO BTC APAGADO EN DASHBOARD. Abortando lanzamiento...")
            time.sleep(2)
            exit(0)
    except: pass
    
    start_oracle()
