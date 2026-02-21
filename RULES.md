# 📜 TITAN vF: REGLAS Y ARQUITECTURA MAESTRA

Este documento sirve como la "Constitución" para cualquier IA o desarrollador que trabaje en el proyecto Titan. Aquí se definen las reglas de oro para mantener el bot estable, rentable y ligero.

## 1. Arquitectura de Tres Capas
1.  **CAPA DE DATOS (MT5)**: MetaTrader 5 provee los Ticks y ejecuta las órdenes. El script de Python NUNCA debe bloquear el hilo principal de MT5.
2.  **CAPA DE INTELIGENCIA (Python)**:
    *   **TitanBrain_VPIN.py**: El motor central. Usa `ThreadPoolExecutor` (Octopus) para procesar ORO y BTC en paralelo.
    *   **IA Híbrida**: Combina modelos LSTM locales (`.h5`) con sentimientos de Ollama.
3.  **CAPA VISUAL (Vercel)**: Next.js 15 conectado por Firebase. Solo sirve para monitoreo y mandos remotos (toggles de cerebros).

## 2. Reglas de Gestión de Riesgo (Protocolo v18.9.103)
El bot debe adaptar su agresividad según el saldo real de la cuenta:
- **Balance < $50**: 1 Bala máxima. Solo Scalping de precisión. Lote: `0.01` (máximo `0.03` si la IA tiene >90% conf).
- **Balance $50 - $100**: Máximo 2 posiciones simultáneas. Lote: `0.02 - 0.04`.
- **Balance > $100**: Hasta 3 posiciones base + 2 de salvación. Libertad de lote hasta `0.06`.
- **Salvación**: Solo se activa si las posiciones base llevan > 5 minutos estancadas.

## 3. Lógica de Inteligencia Artificial
- **Ollama Throttling**: No pedir confirmación a la IA si los indicadores técnicos (RSI/BB) no han cambiado más de un 3% (Caché Cognitivo).
- **Veto IA**: Si la IA local dice "BUY" pero Ollama dice "NO", se descarta el trade o se reduce la confianza al 50%.

## 4. Mantenimiento del Repositorio
- **Prohibido**: Subir carpetas `node_modules`, `.gradle`, `.idea` o logs de más de 1MB.
- **Esencial**: Mantener siempre limpios los archivos `.h5` y los entrenadores (`TitanTrainer_v5.py` y `TitanTrainer_BTC.py`).

## 5. Horarios de Operación
- **ORO (XAUUSD)**: Cerrado desde el viernes 19:00 hasta el domingo 20:00 (Chile). El bot debe detectar esto automáticamente para no generar errores de conexión.
- **BTC**: Operación 24/7 sin restricciones de mercado.

---
*Cualquier sesión futura de Antigravity debe leer este archivo antes de realizar modificaciones estructurales.*
