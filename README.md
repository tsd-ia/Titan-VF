# 🦅 TITAN vF (Versión Final)

## 🐋 HITO DE RECUPERACIÓN EXTRATERRESTRE (v47.8)
- **Versión:** `v47.8.0 Whale Hunter`
- **Misión:** Rescate Familiar de Balance Crítico ($37).
- **Potencia Auditoría (10d):** De **$37.00** a **$6,737.24** (Profit +18,000%).
- **Tecnología:** Trailing Stop Pulmón (80% Riesgo) + Escudo 2+2+2 Multiactivo.
- **Estado:** 🏹 CARGADO PARA LA KILLZONE (04:00 AM).

---

## 📁 Estructura del Proyecto

### 🧠 Motor Python (PC Local)
- **`TitanBrain_VPIN.py`**: El Cerebro Maestro. Ejecuta la estrategia, el paralelismo Octopus y la comunicación con MT5/Firebase.
- **`TitanTrainer_v5.py`**: Entrenador especializado para ORO (XAUUSD).
- **`TitanTrainer_BTC.py`**: Entrenador especializado para BITCOIN (BTCUSD).
- **`TITAN_CORE.py`**: Versión simplificada del núcleo institucional.
- **`deploy_titan.ps1`**: Script de automatización para subidas a Git.

### 🖥️ Dashboard Web (Vercel)
- **`titan-dashboard/`**: Carpeta optimizada con Next.js 15. Contiene solo el código fuente, sin `node_modules` pesados.

### 💾 Modelos de IA
- **`models/`**: Contiene los archivos `.h5` (cerebros entrenados) de Oro y BTC. Nota: Son archivos binarios, no intentes abrirlos como texto.

---

## ⚡ Instrucciones Rápidas
1. **Local**: Ejecuta `TitanBrain_VPIN.py` para iniciar el bot.
2. **Web**: Conecta este repositorio a Vercel apuntando a la carpeta `titan-dashboard`.
3. **Risk**: Las nuevas reglas de lotaje adaptativo (v18.9.103) están integradas.
