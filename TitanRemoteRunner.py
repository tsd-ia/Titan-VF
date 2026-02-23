import subprocess
import time
import requests
import os

# --- TITAN REMOTE RUNNER 2026 v2.0 ---
# Sincronización Selectiva: Solo lanza lo que está ON en el Dashboard.

FIREBASE_URL = "https://titan-sentinel-default-rtdb.firebaseio.com/live"

def get_flag(name):
    try:
        res = requests.get(f"{FIREBASE_URL}/{name}.json", timeout=10)
        if res.status_code == 200:
            return bool(res.json())
    except:
        return False
    return False

print("==================================================")
print("  🚀 TITAN REMOTE RUNNER v2.0 (SELECTIVE)")
print("  Esperando señal del Dashboard para TRABAJAR...")
print("==================================================")

while True:
    try:
        # 1. Escuchar comando maestro (remote_launch) desde la ruta exacta de la web
        res = requests.get(f"{FIREBASE_URL}/commands.json", timeout=10)
        if res.status_code == 200:
            cmds = res.json()
            # v18.11.970: Manejo ultra-robusto de booleanos (acepta True, 1 o "true")
            launch_val = cmds.get("remote_launch", False)
            if launch_val in [True, 1, "true", "True"]:
                print("🎯 SEÑAL RECIBIDA: Iniciando Motores Selectivos...")
            
            # 2. Verificar cada activo antes de lanzar
            if get_flag("btc_brain_on"):
                print("🔥 Lanzando ORÁCULO BTC...")
                subprocess.Popen('start "TITAN_ORACLE" cmd /k "python Titan_Oracle_Binance.py"', shell=True)
            
            if get_flag("oro_brain_on"):
                print("🔥 Lanzando ORÁCULO ORO...")
                subprocess.Popen('start "TITAN_ORACLE_GOLD" cmd /k "python Titan_Oracle_Gold.py"', shell=True)
            
            if get_flag("crypto_brain_on"):
                print("🔥 Lanzando ORÁCULO CRYPTO...")
                subprocess.Popen('start "TITAN_ORACLE_CRYPTO" cmd /k "python Titan_Oracle_Crypto.py"', shell=True)

            # 3. Lanzar el Cerebro Core siempre si hubo comando
            print("🧠 Lanzando CORE ENGINE...")
            subprocess.Popen('start "TITAN_BRAIN" cmd /k "python TitanBrain_VPIN.py"', shell=True)
            
            # Resetear la señal en Firebase
            requests.patch(f"{FIREBASE_URL}/commands.json", json={"remote_launch": False})
            print("✅ Despliegue completado. Volviendo a escucha...")
                
        time.sleep(5)
    except Exception as e:
        print(f"⚠️ Error Runner: {e}")
        time.sleep(10)
