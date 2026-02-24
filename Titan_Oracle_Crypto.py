import asyncio
import json
import time
import os
import requests
from datetime import datetime
try:
    import websockets
except ImportError:
    os.system("pip install websockets requests")
    import websockets

# CONFIGURACIÓN DEL ORÁCULO CRYPTO
SYMBOLS_BINANCE = ["ethusdt", "mstrusdt", "opnusdt"]
WHALES_CONFIG = {
    "ethusdt": {"whale": 220000, "mini": 100000},
    "mstrusdt": {"whale": 220000, "mini": 50000},
    "opnusdt": {"whale": 220000, "mini": 40000}
}
FILE_SIGNAL = "titan_crypto_signals.json"
FIREBASE_FLAG_URL = "https://titan-sentinel-default-rtdb.firebaseio.com/live/crypto_brain_on.json"

STATE = {
    "windows": {s: {"buys": [], "sells": [], "price": 0.0} for s in SYMBOLS_BINANCE},
    "last_signal_time": {s: 0.0 for s in SYMBOLS_BINANCE},
    "active_signals": {} # Memoria persistente para no borrar un activo con otro
}

def is_brain_on():
    try:
        res = requests.get(FIREBASE_FLAG_URL, timeout=2)
        if res.status_code == 200:
            return bool(res.json())
    except:
        return True 
    return True

async def crypto_oracle():
    print(f"📡 ORÁCULO CRYPTO v18.9.190 [DYNAMO]")
    
    while True:
        if not is_brain_on():
            print(f"💤 [{datetime.now().strftime('%H:%M:%S')}] CEREBRO CRYPTO EN DESCANSO... (Esperando Dashboard)")
            await asyncio.sleep(15)
            continue

        try:
            streams = "/".join([f"{s}@aggTrade" for s in SYMBOLS_BINANCE])
            url = f"wss://fstream.binance.com/ws/{streams}"
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                print(f"⚡ CONECTADO A BINANCE (CRYPTO) - Scaneando {SYMBOLS_BINANCE}")
                while True:
                    if int(time.time()) % 30 == 0:
                        if not is_brain_on(): break

                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(msg)
                        
                        sym = data['s'].lower()
                        price = float(data['p'])
                        col = float(data['q']) * price
                        # CORRECCIÓN COMANDANTE: Seguir al Agresor (Taker)
                        # data['m'] (True) -> Buyer is Maker -> Aggressor is SELLER
                        side = "SELL" if data['m'] else "BUY"
                        ts = data['T'] / 1000.0
                        
                        STATE["windows"][sym]["price"] = price
                        win = STATE["windows"][sym]["buys"] if side == "BUY" else STATE["windows"][sym]["sells"]
                        win.append((ts, col))
                        
                        now = time.time()
                        STATE["windows"][sym]["buys"] = [x for x in STATE["windows"][sym]["buys"] if now - x[0] < 1.5]
                        STATE["windows"][sym]["sells"] = [x for x in STATE["windows"][sym]["sells"] if now - x[0] < 1.5]
                        
                        conf = WHALES_CONFIG[sym]
                        all_signals_to_write = False
                        for s in SYMBOLS_BINANCE:
                            s_buy = sum(x[1] for x in STATE["windows"][s]["buys"])
                            s_sell = sum(x[1] for x in STATE["windows"][s]["sells"])
                            
                            sig = "HOLD"
                            vol = 0
                            if s_buy > conf["whale"]: sig = "BUY"; vol = s_buy
                            elif s_sell > conf["whale"]: sig = "SELL"; vol = s_sell
                                
                            if sig != "HOLD" and (now - STATE["last_signal_time"][s]) > 5:
                                STATE["last_signal_time"][s] = now
                                sig_data = {
                                    "signal": sig, "volume": vol, "price": STATE["windows"][s]["price"], "timestamp": now
                                }
                                STATE["active_signals"][s] = sig_data
                                all_signals_to_write = True
                        
                        if all_signals_to_write:
                            # v18.9.200: Limpieza de señales antiguas en memoria (>60s)
                            STATE["active_signals"] = {k: v for k, v in STATE["active_signals"].items() if now - v["timestamp"] < 60}
                            
                            if STATE["active_signals"]:
                                with open(FILE_SIGNAL, "w") as f: json.dump(STATE["active_signals"], f)
                                for s, d in STATE["active_signals"].items():
                                    if now - d["timestamp"] < 1: # Solo imprimir el nuevo
                                        print(f"💎 [{s.upper()}] BALLENA {d['signal']}: ${d['volume']/1000:.1f}k | {datetime.now().strftime('%H:%M:%S')}")
                    except asyncio.TimeoutError:
                        continue
        except Exception as e:
            print(f"⚠️ Error Crypto: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # v18.9.195: ACTIVACIÓN SELECTIVA
    if not is_brain_on():
        print("💤 CEREBRO CRYPTO APAGADO EN DASHBOARD. Abortando lanzamiento...")
        time.sleep(2)
        exit(0)
    asyncio.run(crypto_oracle())
