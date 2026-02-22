@echo off
TITLE TITAN_LAUNCHER
echo ==================================================
echo   🛡️ TITAN INSTITUTIONAL LAUNCHER v18.9.160
echo   MODO: CEREBRO TRIPLE ACTIVADO (ORO/BTC/CRYPTO)
echo   ESTADO: TRIPLE ORACLE SYSTEM (XAU/BTC/CRYPTO)
echo ==================================================
echo.

echo [0/4] Limpiando instancias previas...
taskkill /F /FI "WINDOWTITLE eq TITAN_ORACLE" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TITAN_ORACLE_CRYPTO" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TITAN_ORACLE_GOLD" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TITAN_BRAIN" /T >nul 2>&1

echo [1/4] Iniciando ORACULO BTC (Binance High Speed)...
start "TITAN_ORACLE" cmd /k "python Titan_Oracle_Binance.py"

echo [2/4] Iniciando ORACULO CRYPTO (SOL/ETH/MSTR/OPN)...
start "TITAN_ORACLE_CRYPTO" cmd /k "python Titan_Oracle_Crypto.py"

echo [3/4] Iniciando ORACULO ORO (PAXG/USDT Proxy)...
start "TITAN_ORACLE_GOLD" cmd /k "python Titan_Oracle_Gold.py"

echo [4/4] Iniciando TITAN CORE ENGINE...
timeout /t 5 >nul
start "TITAN_BRAIN" cmd /k "python TitanBrain_VPIN.py"

echo.
echo ==================================================
echo   ✅ SISTEMA CUADRUPLE LANZADO CON EXITO
echo ==================================================
timeout /t 5
exit
