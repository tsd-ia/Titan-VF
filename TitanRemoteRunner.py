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
        if res.status_code != 200:
            time.sleep(5); continue
        
        cmds = res.json()
        if not cmds:
            time.sleep(5); continue

        # v18.11.970: Manejo ultra-robusto de booleanos (acepta True, 1 o "true")
        launch_val = cmds.get("remote_launch", False)
        if launch_val in [True, 1, "true", "True"]:
            # 1.5. LIMPIEZA PREVENTIVA (Anti-Multi-Ventana)
            print("🧹 Limpiando instancias antiguas...")
            os.system('taskkill /F /FI "WINDOWTITLE eq TITAN_BRAIN*" /T >nul 2>&1')
            os.system('taskkill /F /FI "WINDOWTITLE eq TITAN_ORACLE*" /T >nul 2>&1')
            time.sleep(1)

            # 2. Resetear la señal en Firebase ANTES de lanzar (Evita bucles)
            print("🎯 SEÑAL RECIBIDA: Iniciando Motores Selectivos...")
            try: requests.patch(f"{FIREBASE_URL}/commands.json", json={"remote_launch": False}, timeout=5)
            except: pass
            
            # 3. Verificar cada activo antes de lanzar
            if get_flag("btc_brain_on"):
                print("🔥 Lanzando ORÁCULO BTC...")
                subprocess.Popen('start "TITAN_ORACLE" cmd /k "python Titan_Oracle_Binance.py"', shell=True)
            
            if get_flag("oro_brain_on"):
                print("🔥 Lanzando ORÁCULO ORO...")
                subprocess.Popen('start "TITAN_ORACLE_GOLD" cmd /k "python Titan_Oracle_Gold.py"', shell=True)
            
            if get_flag("crypto_brain_on"):
                print("🔥 Lanzando ORÁCULO CRYPTO...")
                subprocess.Popen('start "TITAN_ORACLE_CRYPTO" cmd /k "python Titan_Oracle_Crypto.py"', shell=True)

            # 4. Lanzar el Cerebro Core siempre si hubo comando
            print("🧠 Lanzando CORE ENGINE...")
            subprocess.Popen('start "TITAN_BRAIN" cmd /k "python TitanBrain_VPIN.py"', shell=True)

            # 5. Lanzar el Oficial de Puente (Telegram IA)
            print("🦅 Lanzando OFICIAL DE PUENTE (Telegram IA)...")
            subprocess.Popen('start "TITAN_MESSENGER" cmd /k "python Titan_Messenger_IA.py"', shell=True)
            
            print("✅ Despliegue completado. Estabilizando sensores (5s)...")
            time.sleep(5)
                
        time.sleep(2)
    except Exception:
        # v2.5: Silencio Total ante caídas de Firebase/Red (Evita spam SSLError)
        time.sleep(10)
