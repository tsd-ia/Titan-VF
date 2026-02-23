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

# CONFIGURACIÓN DEL ORÁCULO ORO (PAXG/USDT)
SYMBOL_BINANCE = "paxgusdt"
WHALE_THRESHOLD = 25000    
GOD_MODE_THRESHOLD = 90000 
FILE_SIGNAL = "titan_gold_signals.json"
FILE_PULSE = "titan_gold_pulse.json"
FIREBASE_FLAG_URL = "https://titan-sentinel-default-rtdb.firebaseio.com/live/oro_brain_on.json"

STATE = {
    "window": {"buys": [], "sells": [], "price": 0.0},
    "last_signal_time": 0.0,
    "last_pulse_time": 0.0
}

def is_brain_on():
    try:
        res = requests.get(FIREBASE_FLAG_URL, timeout=2)
        if res.status_code == 200:
            val = res.json()
            if val is None: return True 
            return bool(val)
    except:
        return True 
    return True

async def gold_oracle():
    print(f"🔱 ORÁCULO ORO v18.9.950 [HI-SYNC]")
    
    while True:
        if not is_brain_on():
            print(f"💤 [{datetime.now().strftime('%H:%M:%S')}] CEREBRO ORO EN DESCANSO...")
            await asyncio.sleep(15)
            continue

        try:
            url = f"wss://stream.binance.com:9443/ws/{SYMBOL_BINANCE}@aggTrade"
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                print(f"⚡ [{datetime.now().strftime('%H:%M:%S')}] CONECTADO A BINANCE (ORO)")
                while True:
                    if int(time.time()) % 30 == 0:
                        if not is_brain_on(): break

                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(msg)
                        
                        price = float(data['p'])
                        col = float(data['q']) * price
                        side = "SELL" if data['m'] else "BUY"
                        ts = data['T'] / 1000.0
                        
                        STATE["window"]["price"] = price
                        win = STATE["window"]["buys"] if side == "BUY" else STATE["window"]["sells"]
                        win.append((ts, col))
                        
                        now = time.time()
                        STATE["window"]["buys"] = [x for x in STATE["window"]["buys"] if now - x[0] < 2.0]
                        STATE["window"]["sells"] = [x for x in STATE["window"]["sells"] if now - x[0] < 2.0]
                        
                        vol_buy = sum(x[1] for x in STATE["window"]["buys"])
                        vol_sell = sum(x[1] for x in STATE["window"]["sells"])
                        
                        sig = "HOLD"
                        vol = 0
                        if vol_buy > WHALE_THRESHOLD:
                            sig = "BUY"; vol = vol_buy
                        elif vol_sell > WHALE_THRESHOLD:
                            sig = "SELL"; vol = vol_sell
                        
                        if sig != "HOLD" and (now - STATE["last_signal_time"]) > 5:
                            STATE["last_signal_time"] = now
                            data_sig = {
                                "symbol": "XAUUSDm", "signal": sig, "volume": vol,
                                "price": price, "timestamp": now, "god_mode": vol >= GOD_MODE_THRESHOLD
                            }
                            with open(FILE_SIGNAL, "w") as f: json.dump(data_sig, f)
                            ts_str = datetime.now().strftime('%H:%M:%S')
                            print(f"🔱 [{ts_str}] BALLENA ORO: {sig} | Vol: ${vol/1000:.1f}k {'[GOD MODE]' if vol >= GOD_MODE_THRESHOLD else ''}")
                        
                        # PULSO DE VIDA (Aislado)
                        if now - STATE["last_pulse_time"] > 5.0:
                            STATE["last_pulse_time"] = now
                            v_total = (vol_buy + vol_sell)
                            ts_str = datetime.now().strftime('%H:%M:%S')
                            print(f"📡 [{ts_str}] [RADAR] Oro escaneando... | Rumor: ${v_total/1000:.1f}k")
                            pulse_data = {"symbol": "XAUUSDm", "signal": "HEARTBEAT", "timestamp": now}
                            with open(FILE_PULSE, "w") as f: json.dump(pulse_data, f)

                    except asyncio.TimeoutError:
                        if time.time() - STATE["last_pulse_time"] > 10.0:
                            ts_str = datetime.now().strftime('%H:%M:%S')
                            print(f"📡 [{ts_str}] [RADAR] Oro escaneando... | Mercado Lento")
                            STATE["last_pulse_time"] = time.time()
                        continue 
        except Exception as e:
            print(f"⚠️ Error Oro: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(gold_oracle())
