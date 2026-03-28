@echo off
chcp 65001 >nul
title Configurar SIAOL-PRO-V6

echo ==================================================
echo        SISTEMA DE CONFIGURACAO AUTOMATICA
echo ==================================================
echo.
echo Esse script foi criado pelo seu Programador Senior.
echo Ele vai configurar seu banco de dados e instalar as maquinas virtuais.
echo.

set /p URL="1. Cole sua SUPABASE_URL (ou aperte Enter): "
set /p KEY="2. Cole sua SUPABASE_KEY (ou aperte Enter): "

echo SUPABASE_URL="%URL%" > .env
echo SUPABASE_KEY="%KEY%" >> .env

echo.
echo [OK] O arquivo de senhas (.env) foi gerado!
echo.
echo Instalando as dependencias silenciosamente...
pip install -r requirements.txt python-dotenv

echo.
echo ==================================================
echo CONFIGURACAO CONCLUIDA COM SUCESSO!
echo Pode fechar esta janela no "X".
echo Para iniciar o sistema, clique no arquivo "1_INICIAR_SIAOL.bat"
echo ==================================================
pause
