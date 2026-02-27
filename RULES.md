# 📜 TITAN vF: REGLAS Y ARQUITECTURA MAESTRA

Este documento sirve como la "Constitución" para cualquier IA o desarrollador que trabaje en el proyecto Titan. Aquí se definen las reglas de oro para mantener el bot estable, rentable y ligero.

## 1. Arquitectura de Tres Capas
1.  **CAPA DE DATOS (MT5)**: MetaTrader 5 provee los Ticks y ejecuta las órdenes. El script de Python NUNCA debe bloquear el hilo principal de MT5.
2.  **CAPA DE INTELIGENCIA (Python)**:
    *   **TitanBrain_VPIN.py**: El motor central. Usa `ThreadPoolExecutor` (Octopus) para procesar ORO y BTC en paralelo.
    *   **IA Híbrida**: Combina modelos LSTM locales (`.h5`) con sentimientos de Ollama.
3.  **CAPA VISUAL (Vercel)**: Next.js 15 conectado por Firebase. Solo sirve para monitoreo y mandos remotos (toggles de cerebros).

## 2. Reglas de Gestión de Riesgo (Protocolo SNIPER v40.10 - COMPROBADO)
*REGISTRO HISTÓRICO: Esta configuración generó +$90.53 USD en 45 minutos (45% de retorno) operando Oro con cuenta de $200. NINGUNA IA FUTURA DEBE ELIMINAR ESTAS REGLAS SIN ORDEN EXPRESA DEL COMANDANTE.*

El bot utiliza el sistema de **Enjambre Blindado**:
- **ORO (XAUUSDm)**: 10 Balas máximo para Capital Variable de $200. Lote fijo 0.01 inamovible. Solo sube en múltiplos aprobados (Ej. $400 = Lote 0.02).
- **VETO DE TENDENCIA (CRÍTICO)**: Jamás disparar SELL si el M5 es alcista, ni BUY si el M5 es bajista.
- **VETO DE MOMENTUM (CRÍTICO)**: Prohibido disparar contra el M1 inmediato. Si la mecha cae, no hay Buy.
- **VETO DE RSI**: Prohibido BUY con RSI > 80. Prohibido SELL con RSI < 20.
- **CERO CIERRES POR MARGEN**: El bot jamás debe cerrar operaciones en pérdida asumiendo riesgo por nivel bajo de margen.
- **MURO SEGUIDOR (TRAILING 80%)**: Las escaleras de trailing fijas están prohibidas. Se debe usar ratchet dinámico continuo: si profit > $3.5, se asegura el 80% del PICO Máximo. Un Paracaídas secundario asegura el 85% a partir de $1.50 ("No respira más").
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
