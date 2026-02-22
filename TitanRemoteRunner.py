import subprocess
import time
import requests
import os

# --- TITAN REMOTE RUNNER 2026 ---
# Este script se queda escuchando a Firebase y lanza el .bat si recibe la orden

FIREBASE_URL = "https://titan-sentinel-default-rtdb.firebaseio.com/live/commands.json"

print("==================================================")
print("  🚀 TITAN REMOTE RUNNER 2026")
print("  Esperando señal del Dashboard para TRABAJAR...")
print("==================================================")

while True:
    try:
        res = requests.get(FIREBASE_URL, timeout=10)
        if res.status_code == 200:
            cmds = res.json()
            if cmds and cmds.get("remote_launch"):
                print("🎯 SEÑAL RECIBIDA: ¡A TRABAJAR!")
                # Ejecutar el .bat que abre los otros dos
                subprocess.Popen(["cmd", "/c", "TRABAJAR.bat"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                
                # Resetear la señal en Firebase para no loopear
                requests.patch(FIREBASE_URL, json={"remote_launch": False})
                print("✅ Motores lanzados. Volviendo a modo escucha...")
                
        time.sleep(5)
    except Exception as e:
        time.sleep(10)
