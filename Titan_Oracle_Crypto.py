import asyncio
import json
import time
import os
import threading
from datetime import datetime
try:
    import websockets
    import requests
except ImportError:
    os.system("pip install websockets requests")
    import websockets
    import requests

# CONFIGURACIÓN DEL ORÁCULO CRYPTO
SYMBOLS_BINANCE = ["solusdt", "ethusdt", "mstrusdt", "opnusdt"]
# Umbrales por símbolo (Ajustados para 2026)
WHALES_CONFIG = {
    "solusdt": {"whale": 150000, "mini": 50000},
    "ethusdt": {"whale": 250000, "mini": 80000},
    "mstrusdt": {"whale": 100000, "mini": 30000},
    "opnusdt": {"whale": 80000, "mini": 20000}
}

FILE_SIGNAL = "titan_crypto_signals.json"

STATE = {
    "windows": {s: {"buys": [], "sells": [], "price": 0.0} for s in SYMBOLS_BINANCE},
    "last_signal_time": {s: 0.0 for s in SYMBOLS_BINANCE}
}

def write_signals(all_signals):
    try:
        with open(FILE_SIGNAL, "w") as f:
            json.dump(all_signals, f)
    except:
        pass

async def binance_oracle():
    # Stream combinado para los 4 símbolos
    streams = "/".join([f"{s}@aggTrade" for s in SYMBOLS_BINANCE])
    url = f"wss://fstream.binance.com/ws/{streams}"
    
    print(f"📡 ORÁCULO CRYPTO ONLINE: Monitoreando {SYMBOLS_BINANCE}")
    
    async with websockets.connect(url) as ws:
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                
                sym = data['s'].lower()
                price = float(data['p'])
                col = float(data['q']) * price
                side = "SELL" if data['m'] else "BUY"
                ts = data['T'] / 1000.0
                
                STATE["windows"][sym]["price"] = price
                win = STATE["windows"][sym]["buys"] if side == "BUY" else STATE["windows"][sym]["sells"]
                win.append((ts, col))
                
                # Limpiar ventana de 1.5s
                now = time.time()
                STATE["windows"][sym]["buys"] = [x for x in STATE["windows"][sym]["buys"] if now - x[0] < 1.5]
                STATE["windows"][sym]["sells"] = [x for x in STATE["windows"][sym]["sells"] if now - x[0] < 1.5]
                
                # Calcular volumen acumulado
                total_buy = sum(x[1] for x in STATE["windows"][sym]["buys"])
                total_sell = sum(x[1] for x in STATE["windows"][sym]["sells"])
                
                # --- v18.9.180: SENSOR DINÁMICO (Ahorro de Energía) ---
                if now % 10 < 0.1:
                    try:
                        res = requests.get("https://titan-sentinel-default-rtdb.firebaseio.com/live/crypto_brain_on.json", timeout=2)
                        if res.status_code == 200 and res.json() == False:
                            print("💤 CEREBRO CRYPTO OFFLINE (Dashboard): Entrando en hibernación...")
                            await asyncio.sleep(10)
                            continue
                    except: pass
                
                conf = WHALES_CONFIG[sym]
                
                all_signals = {}
                for s in SYMBOLS_BINANCE:
                    s_buy = sum(x[1] for x in STATE["windows"][s]["buys"])
                    s_sell = sum(x[1] for x in STATE["windows"][s]["sells"])
                    
                    sig = "HOLD"
                    vol = 0
                    if s_buy > conf["whale"]:
                        sig = "BUY"
                        vol = s_buy
                    elif s_sell > conf["whale"]:
                        sig = "SELL"
                        vol = s_sell
                        
                    if sig != "HOLD" and (now - STATE["last_signal_time"][s]) > 5:
                        STATE["last_signal_time"][s] = now
                        all_signals[s] = {
                            "signal": sig,
                            "volume": vol,
                            "price": STATE["windows"][s]["price"],
                            "timestamp": now
                        }
                
                if all_signals:
                    write_signals(all_signals)
                    for s, details in all_signals.items():
                        print(f"💎 [{s.upper()}] BALLENA {details['signal']}: ${details['volume']/1000:.1f}k | Precio: {details['price']} | {datetime.now().strftime('%H:%M:%S')}")

            except Exception as e:
                print(f"⚠️ Error Oráculo: {e}")
                await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(binance_oracle())
