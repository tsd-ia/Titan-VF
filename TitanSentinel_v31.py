import time
import os
import datetime

LOG_FILE = r"c:\proyectosvscode\Titan-vF\titan_vanguardia.log"
REPORT_FILE = r"c:\proyectosvscode\Titan-vF\SENTINEL_VIGIL_3.md"

def get_last_lines(n=50):
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return lines[-n:]
    except:
        return []

def monitor():
    start_time = datetime.datetime.now()
    # Vigilancia para la sesión de las 13:37
    end_time = start_time + datetime.timedelta(minutes=15)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 🔭 VIGILANCIA TITAN SESIÓN 3 (A partir de 13:37)\n")
        f.write(f"- **Objetivo:** Auditar Cierre de Emergencia v31.9.2 (Fix 10011) + Global Guard\n")
        f.write(f"- **Estado:** ACTIVO - OBSERVANDO\n\n")
        f.write(f"| Hora | Tipo | Detalle del Procedimiento |\n")
        f.write(f"| :--- | :--- | :--- |\n")

    seen_events = set()

    while datetime.datetime.now() < end_time:
        lines = get_last_lines(50)
        new_events = []
        
        # Filtros para la v31.9.2
        keywords = ["GLOBAL GUARD", "EMERGENCY_STOP", "10011", "TRL-SAFE", "ORÁCULO", "SOPESANDO", "VETO", "COSECHA", "ERROR"]
        
        for line in lines:
            if any(k in line for k in keywords):
                try:
                    # Extraer hora HH:MM:SS
                    timestamp = line.split("]")[0].split(" ")[1]
                    # Solo desde las 13:36:30 en adelante para limpiar ruido viejo
                    if timestamp >= "13:36:30":
                        # Extraer todo lo que está después del timestamp y el thread
                        # Ejemplo: [25/02 13:37:48][THRE] MENSAJE...
                        parts = line.split("]")
                        if len(parts) >= 2:
                            content = "]".join(parts[2:]).strip() if len(parts) > 2 else parts[1].strip()
                            event_id = f"{timestamp}_{content[:40]}"
                            if event_id not in seen_events:
                                seen_events.add(event_id)
                                new_events.append((timestamp, content))
                except:
                    continue
        
        if new_events:
            with open(REPORT_FILE, "a", encoding="utf-8") as f:
                for ts, det in new_events:
                    clean_det = det.replace("|", " ").replace("\n", " ").strip()
                    f.write(f"| {ts} | 🛡️ Auditoría | {clean_det} |\n")
        
        time.sleep(3) # Máxima frecuencia para no perder ni un tick

if __name__ == "__main__":
    monitor()
