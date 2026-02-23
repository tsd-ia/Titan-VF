import MetaTrader5 as mt5
if not mt5.initialize():
    print("Failed")
else:
    symbols = mt5.symbols_get()
    search = ["SOL", "ETH", "MSTR", "OPN"]
    for s in symbols:
        if any(x in s.name for x in search):
            print(f"{s.name}")
    mt5.shutdown()
