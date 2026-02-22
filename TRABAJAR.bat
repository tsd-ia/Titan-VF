@echo off
TITLE TITAN LAUNCHER 2026
echo ==================================================
echo   🛡️ TITAN INSTITUTIONAL LAUNCHER
echo ==================================================
echo.
echo [1/2] Iniciando ORACULO DE BINANCE (High Speed)...
start cmd /k "python Titan_Oracle_Binance.py"
echo [2/2] Iniciando TITAN CORE ENGINE...
start cmd /k "python TitanBrain_VPIN.py"
echo.
echo ==================================================
echo   ✅ SISTEMA OPERATIVO Y VIGILANDO
echo ==================================================
pause
