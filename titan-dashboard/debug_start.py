import sys, traceback

try:
    print("=== DIAGNÓSTICO TITAN ===", flush=True)
    print(f"Python: {sys.version}", flush=True)
    
    print("1. Importando módulos base...", flush=True)
    import os, time, threading, json
    print("   OK", flush=True)
    
    print("2. Importando MetaTrader5...", flush=True)
    import MetaTrader5 as mt5
    print(f"   OK - MT5 version: {mt5.__version__}", flush=True)
    
    print("3. Importando TensorFlow...", flush=True)
    import tensorflow as tf
    print(f"   OK - TF version: {tf.__version__}", flush=True)
    
    print("4. Importando pandas/numpy/ta...", flush=True)
    import pandas, numpy, ta
    print("   OK", flush=True)
    
    print("5. Importando FastAPI/uvicorn...", flush=True)
    from fastapi import FastAPI
    import uvicorn
    print("   OK", flush=True)
    
    print("6. Importando psutil...", flush=True)
    import psutil
    print("   OK", flush=True)
    
    print("7. Probando kill_port_process...", flush=True)
    import subprocess
    try:
        cmd = f'netstat -ano | findstr :8000'
        res = subprocess.check_output(cmd, shell=True).decode()
        print(f"   Puerto 8000 en uso: {res.strip()[:100]}", flush=True)
    except:
        print("   Puerto 8000 libre", flush=True)
    
    print("8. Cargando TitanBrain_VPIN.py...", flush=True)
    # Intentar importar el módulo
    import importlib.util
    spec = importlib.util.spec_from_file_location("TitanBrain_VPIN", "TitanBrain_VPIN.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("   IMPORT OK!", flush=True)
    
    print("9. Iniciando metralleta_loop en thread...", flush=True)
    t = threading.Thread(target=mod.metralleta_loop, daemon=True)
    t.start()
    print("   Thread iniciado OK", flush=True)
    
    print("10. Lanzando uvicorn...", flush=True)
    uvicorn.run(mod.app, host="0.0.0.0", port=8000, log_level="error")
    
except Exception as e:
    print(f"\n💥 ERROR ENCONTRADO: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)
