# 🦅 TITAN vF (Versión Final)

Este es el repositorio limpio y optimizado para el **Titan Sentinel Dashboard**. Se han eliminado archivos basura de Android, logs pesados y pruebas obsoletas para garantizar un despliegue rápido en Vercel.

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
