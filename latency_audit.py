import MetaTrader5 as mt5
import time

if not mt5.initialize():
    print("Fallo MT5")
    quit()

symbols = ["XAUUSDm", "BTCUSDm"]
print(f"--- Auditoria de Latencia MT5 ({time.ctime()}) ---")

for s in symbols:
    mt5.symbol_select(s, True)
    start = time.perf_counter()
    tick = mt5.symbol_info_tick(s)
    end = time.perf_counter()
    lat = (end - start) * 1000
    print(f"Ping {s}: {lat:.2f}ms")

start = time.perf_counter()
rates = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M1, 0, 100)
end = time.perf_counter()
lat = (end - start) * 1000
print(f"Lectura 100 velas M1 (XAU): {lat:.2f}ms")

mt5.shutdown()
