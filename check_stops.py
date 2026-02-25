import MetaTrader5 as mt5
if not mt5.initialize():
    print("Failed")
    quit()
symbol = "XAUUSDm"
info = mt5.symbol_info(symbol)
if info:
    print(f"Symbol: {symbol}")
    print(f"Trade Stops Level: {info.trade_stops_level}")
    print(f"Point: {info.point}")
    print(f"Digits: {info.digits}")
    print(f"Spread: {info.spread}")
else:
    print("Not found")
mt5.shutdown()
