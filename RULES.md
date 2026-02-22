# 📜 TITAN vF: REGLAS Y ARQUITECTURA MAESTRA

Este documento sirve como la "Constitución" para cualquier IA o desarrollador que trabaje en el proyecto Titan. Aquí se definen las reglas de oro para mantener el bot estable, rentable y ligero.

## 1. Arquitectura de Tres Capas
1.  **CAPA DE DATOS (MT5)**: MetaTrader 5 provee los Ticks y ejecuta las órdenes. El script de Python NUNCA debe bloquear el hilo principal de MT5.
2.  **CAPA DE INTELIGENCIA (Python)**:
    *   **TitanBrain_VPIN.py**: El motor central. Usa `ThreadPoolExecutor` (Octopus) para procesar ORO y BTC en paralelo.
    *   **IA Híbrida**: Combina modelos LSTM locales (`.h5`) con sentimientos de Ollama.
3.  **CAPA VISUAL (Vercel)**: Next.js 15 conectado por Firebase. Solo sirve para monitoreo y mandos remotos (toggles de cerebros).

## 2. Reglas de Gestión de Riesgo (Protocolo v18.9.170)
El bot utiliza un sistema de **Independencia de Balas** (Buckets) por cada instrumento:
- **ORO (XAUUSDm)**: 3 Balas máximo (Excluyente de otros).
- **BTC (BTCUSDm)**: 3 Balas máximo (Excluyente de otros).
- **CRYPTO (SOL, ETH, etc.)**: 5 Balas máximo por símbolo (Excluyente de otros).
- **Regla God Mode ($280k)**: Si el volumen del Oráculo supera $280k, se ignoran grilletes técnicos y se dispara la bala obligatoriamente.
- **Lotaje**: Adaptativo según balance y activo (Crypto usa lotaje base 0.10 para mayor impacto).
- **Salvación**: Solo se activa si las posiciones base llevan > 5 minutos estancadas.

## 3. Lógica de Inteligencia Artificial
- **Ollama Throttling**: No pedir confirmación a la IA si los indicadores técnicos (RSI/BB) no han cambiado más de un 3% (Caché Cognitivo).
- **Veto IA**: Si la IA local dice "BUY" pero Ollama dice "NO", se descarta el trade o se reduce la confianza al 50%.
- **CONSULTA DE UMBRALES (REGLA DE ORO)**: PROHIBIDO bajar o cambiar umbrales de ballena (Oracle) sin preguntar antes al Comandante. El ruido de mercado bajo mata la cuenta en comisiones.

## 4. Mantenimiento del Repositorio
- **Prohibido**: Subir carpetas `node_modules`, `.gradle`, `.idea` o logs de más de 1MB.
- **Esencial**: Mantener siempre limpios los archivos `.h5` y los entrenadores (`TitanTrainer_v5.py` y `TitanTrainer_BTC.py`).

## 5. Horarios de Operación
- **ORO (XAUUSD)**: Cerrado desde el viernes 19:00 hasta el domingo 20:00 (Chile). El bot debe detectar esto automáticamente para no generar errores de conexión.
- **BTC**: Operación 24/7 sin restricciones de mercado.

---
*Cualquier sesión futura de Antigravity debe leer este archivo antes de realizar modificaciones estructurales.*
