import MetaTrader5 as mt5

def check_margin_req():
    if not mt5.initialize(): return
    
    symbols = ["XAUUSDm", "BTCUSDm"]
    for sym in symbols:
        info = mt5.symbol_info(sym)
        if info:
            # Calcular margen para 0.01 lotes
            margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, sym, 0.01, info.ask)
            print(f"Símbolo: {sym}")
            print(f"  - Precio Ask: {info.ask}")
            print(f"  - Margen para 0.01: ${margin}")
            print(f"  - Apalancamiento: {info.leverage if hasattr(info, 'leverage') else 'N/A'}")
        else:
            print(f"No se pudo obtener info de {sym}")

if __name__ == "__main__":
    check_margin_req()
