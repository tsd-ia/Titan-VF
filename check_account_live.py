import MetaTrader5 as mt5
if not mt5.initialize():
    print("Failed")
    quit()
acc = mt5.account_info()
print(f"Balance: {acc.balance}")
print(f"Equity: {acc.equity}")
print(f"Margin Level: {acc.margin_level}%")
pos = mt5.positions_get()
print(f"Open Positions: {len(pos)}")
for p in pos:
    print(f"  - {p.symbol} ({'BUY' if p.type==0 else 'SELL'}): ${p.profit:.2f}")
mt5.shutdown()
