@echo off
TITLE TITAN_LAUNCHER
echo ==================================================
echo   🛡️ TITAN INSTITUTIONAL LAUNCHER
echo ==================================================
echo.

echo [0/2] Limpiando instancias previas para evitar colapsos...
:: Matamos específicamente las ventanas con nuestros títulos para no cerrar el Runner
taskkill /F /FI "WINDOWTITLE eq TITAN_ORACLE" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TITAN_BRAIN" /T >nul 2>&1

echo [1/2] Iniciando ORACULO DE BINANCE (High Speed)...
start "TITAN_ORACLE" cmd /k "python Titan_Oracle_Binance.py"

echo [2/2] Iniciando TITAN CORE ENGINE...
:: Agregamos un pequeño delay para que el Oráculo cree el socket primero
timeout /t 2 >nul
start "TITAN_BRAIN" cmd /k "python TitanBrain_VPIN.py"

echo.
echo ==================================================
echo   ✅ MISIONES REINICIADAS CON EXITO
echo ==================================================
timeout /t 5
exit
