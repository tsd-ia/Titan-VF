# 🛡️ TITAN VANGUARDIA - CONSTITUCIÓN SAGRADA (v18.9.2)

Este documento define las reglas inmutables del sistema. Cualquier modificación a estas reglas requiere autorización explícita del Mando Supremo (Usuario).

## 1. REGLAS DE SUPERVIVENCIA (Riesgo)
*   [x] **TODO O NADA:** Prohibido cerrar posiciones en negativo manualmente por "pánico" o drawdown.
    *   Salida 1: Take Profit (Meta de Sesión).
    *   Salida 2: Stop Loss (Mecánico en MT5).
    *   Salida 3: Margin Call (Liquidación).
*   [x] **Meta de Sesión:** +$50.00 USD. Al llegar, se cierra todo y se apaga.
*   [x] **Stop Loss Dinámico (Escudo Elástico):**
    *   Si Spread < 100: SL Normal.
    *   Si Spread > 100: SL x 5 (Para aguantar volatilidad).
*   [x] **Ratchet Suizo (v18.9.2 - REGLA DEL DÓLAR):** **Mínimo de cierre asegurado: $1.00 USD.**
    *   **Nivel 1 (Punto de Fuga):** Al llegar a **+$1.60** -> **Asegura +$1.05 USD MÍN.** (Blindaje inicial).
    *   **Nivel 2 (Refuerzo +$2.20):** Asegura +$1.50.
    *   **Nivel 3 (+$3.00):** Asegura +$2.50.
    *   **Nivel 4 (+$5.00):** Asegura +$4.00.
    *   **Nivel 5 (+$9.00):** Asegura Ganancia Total (Distancia de seguridad $1.20).
*   [x] **Cierre Hormiga:** Solo se permite cierre táctico por estancamiento (>90s) si el beneficio es **mayor a $1.00 USD**.

## 2. REGLAS DE ENTRADA (MÁXIMA POTENCIA v18.9.2)
*   [x] **Límite de Fuego:** Aumentado a **5 Balas Simultáneas** (XAUUSDm).
*   [x] **Privilegio de Contragolpe:** Entradas tácticas (0.01) en pisos/techos de Bollinger tienen **bypass total** de:
    *   Filtro de Gravedad (Caída libre).
    *   Filtro de Zona Neutra.
    *   Veto por Tendencia M5 contraria.
*   [x] **Bala 0 (La Exploradora):** Confianza > 70% para entrar.
*   [x] **Balas 1-5 (El Rescate Inteligente):**
    *   **Distancia Mínima:** Al menos **700 puntos ($0.70)** de separación.
    *   **Confirmación de Vela:** Debe ser del color de la señal.
*   [x] **Actividad Permanente:** Si el bot está vacío por 5 mins, busca entrada segura (0.01).
*   [x] **Filtro de Spread (Protección Nuclear):**
    *   Límite acumulativo de 300 pts. Bala exploradora 0.01 permitida hasta 250 pts.

## 3. CHECKLIST APK (Control Remoto)
*   [x] **Dashboard Espejo:** PnL, Equidad y Estado real.
*   [x] **Velocímetro ($/min):** Medidor de flujo de caja.
*   [x] **Control Total:** START / STOP / PANIC.
*   [x] **Gráfico Tick:** Visualización de latencia y precio real.

## 4. TELEMETRIA & BLINDAJE
*   [x] **Blindaje de Scope (v18.8.1):** Inicialización atómica de variables proactiva para evitar crashes.
*   [x] **Monitor de Latencia:** Alerta visual ante retrasos > 400ms.

## 5. SALÓN DE LA FAMA (Hitos)
*   [x] **Hito $1.000 USD:** ¡ALCANZADO! (2026-02-17)
*   [ ] **Hito $1.500 USD:** Siguiente objetivo táctico.

---
**Última Actualización:** v18.9.2 (Máxima Potencia - Doctrina del Dólar y 5 Balas)
**Estado:** VANGUARDIA ACTIVA - CAZADOR DE REVERSIONES 🦾🛡️💰
