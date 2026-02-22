@echo off
TITLE TITAN_LAUNCHER
echo ==================================================
echo   🛡️ TITAN INSTITUTIONAL LAUNCHER v18.9.155
echo   MODO: CEREBRO TRIPLE ACTIVADO (ORO/BTC/CRYPTO)
echo ==================================================
echo.

echo [0/3] Limpiando instancias previas...
taskkill /F /FI "WINDOWTITLE eq TITAN_ORACLE" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TITAN_ORACLE_CRYPTO" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TITAN_BRAIN" /T >nul 2>&1

echo [1/3] Iniciando ORACULO BTC (Principal)...
start "TITAN_ORACLE" cmd /k "python Titan_Oracle_Binance.py"

echo [2/3] Iniciando ORACULO CRYPTO (SOL/ETH/MSTR/OPN)...
start "TITAN_ORACLE_CRYPTO" cmd /k "python Titan_Oracle_Crypto.py"

echo [3/3] Iniciando TITAN CORE ENGINE...
timeout /t 3 >nul
start "TITAN_BRAIN" cmd /k "python TitanBrain_VPIN.py"

echo.
echo ==================================================
echo   ✅ TRIPLE CEREBRO LANZADO CON EXITO
echo ==================================================
timeout /t 5
exit
