import MetaTrader5 as mt5

if not mt5.initialize():
    print("Error MT5")
    quit()

acc = mt5.account_info()
print(f"--- Info de Cuenta ({acc.login}) ---")
print(f"Leverage: 1:{acc.leverage}")
print(f"Balance: {acc.balance}")
print(f"Equity: {acc.equity}")
print(f"Margen Libre: {acc.margin_free}")

symbol = "XAUUSDm"
mt5.symbol_select(symbol, True)
lot = 0.01
margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lot, mt5.symbol_info_tick(symbol).ask)
print(f"\nMargen requerido para 0.01 {symbol}: ${margin:.2f}")

symbol_btc = "BTCUSDm"
margin_btc = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol_btc, 0.01, mt5.symbol_info_tick(symbol_btc).ask)
print(f"Margen requerido para 0.01 {symbol_btc}: ${margin_btc:.2f}")

mt5.shutdown()
