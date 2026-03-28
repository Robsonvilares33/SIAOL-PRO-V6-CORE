@echo off
chcp 65001 >nul
title Motor SIAOL-PRO-V6

echo ==================================================
echo             INICIANDO SIAOL-PRO-V6
echo ==================================================
echo Iniciando fase de coleta e ML...
echo.

python main.py

echo.
echo ==================================================
echo Ciclo finalizado.
echo ==================================================
pause
