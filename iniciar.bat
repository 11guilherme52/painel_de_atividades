@echo off
title Meu Dia - servidor
cd /d "%~dp0"

where python >nul 2>nul
if not %errorlevel%==0 (
    echo.
    echo [ERRO] Python nao foi encontrado.
    echo Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

rem Liga o servidor e abre a pagina no GitHub Pages.
rem Deixe esta janela aberta enquanto usa o Meu Dia.
python app.py %*
pause
