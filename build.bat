@echo off
:: ─────────────────────────────────────────────────────
::  wltech SSH Tunnel Manager — Build Script
:: ─────────────────────────────────────────────────────
echo.
echo [wltech] Verificando Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Python nao encontrado no PATH.
    echo.
    echo  Instale o Python 3.x em: https://www.python.org/downloads/
    echo  IMPORTANTE: marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

python --version

echo.
echo [wltech] Instalando dependencias (CustomTkinter, etc)...
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet

echo.
echo [wltech] Gerando executavel...
:: Adicionando as dependencias do customtkinter e o icone
python -m PyInstaller --onefile --windowed --name "wltech-tunnel" --icon="assets\icon.ico" --add-data "assets;assets" src\main.py

echo.
if exist dist\wltech-tunnel.exe (
    echo [OK] Executavel gerado em: dist\wltech-tunnel.exe
) else (
    echo [ERRO] Falha ao gerar executavel.
)
pause
