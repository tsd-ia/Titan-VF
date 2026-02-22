import asyncio
import json
import time
import os
from datetime import datetime
try:
    import websockets
except ImportError:
    os.system("pip install websockets")
    import websockets

# CONFIGURACIÓN DEL ORÁCULO ORO (PAXG/USDT como Proxy institucional)
SYMBOL_BINANCE = "paxgusdt" # El Oro de Binance que mueve al mercado Spot
WHALE_THRESHOLD = 220000    # Ajustado para Oro (Menos volumen que BTC)
GOD_MODE_THRESHOLD = 280000 # Regla de Oro del Comandante

FILE_SIGNAL = "titan_gold_signals.json"

STATE = {
    "window": {"buys": [], "sells": [], "price": 0.0},
    "last_signal_time": 0.0
}

def write_signal(sig, vol, price):
    try:
        data = {
            "symbol": "XAUUSDm",
            "binance_sym": SYMBOL_BINANCE,
            "signal": sig,
            "volume": vol,
            "price": price,
            "timestamp": time.time(),
            "god_mode": vol >= GOD_MODE_THRESHOLD
        }
        with open(FILE_SIGNAL, "w") as f:
            json.dump(data, f)
    except:
        pass

async def gold_oracle():
    url = f"wss://stream.binance.com:9443/ws/{SYMBOL_BINANCE}@aggTrade"
    
    print(f"🔱 ORÁCULO ORO ONLINE: Monitoreando {SYMBOL_BINANCE} (Proxy XAUUSD)")
    
    async with websockets.connect(url) as ws:
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                
                price = float(data['p'])
                col = float(data['q']) * price
                side = "SELL" if data['m'] else "BUY"
                ts = data['T'] / 1000.0
                
                STATE["window"]["price"] = price
                win = STATE["window"]["buys"] if side == "BUY" else STATE["window"]["sells"]
                win.append((ts, col))
                
                # Ventana de 2 segundos para Oro (es más lento que BTC)
                now = time.time()
                STATE["window"]["buys"] = [x for x in STATE["window"]["buys"] if now - x[0] < 2.0]
                STATE["window"]["sells"] = [x for x in STATE["window"]["sells"] if now - x[0] < 2.0]
                
                vol_buy = sum(x[1] for x in STATE["window"]["buys"])
                vol_sell = sum(x[1] for x in STATE["window"]["sells"])
                
                sig = "HOLD"
                vol = 0
                if vol_buy > WHALE_THRESHOLD:
                    sig = "BUY"
                    vol = vol_buy
                elif vol_sell > WHALE_THRESHOLD:
                    sig = "SELL"
                    vol = vol_sell
                
                if sig != "HOLD" and (now - STATE["last_signal_time"]) > 5:
                    STATE["last_signal_time"] = now
                    write_signal(sig, vol, price)
                    print(f"🔱 BALLENA ORO: {sig} | Vol: ${vol/1000:.1f}k {'[GOD MODE]' if vol >= GOD_MODE_THRESHOLD else ''}")

            except Exception as e:
                print(f"⚠️ Error Oráculo Oro: {e}")
                await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(gold_oracle())
