@echo off
setlocal
cd /d "%~dp0"
set LEAGUE_ID=12258

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python nao encontrado. Instala-o de https://www.python.org e tenta de novo.
  pause
  exit /b 1
)

echo A atualizar os dados da liga...
"%PY%" scripts\fetch_data.py
if errorlevel 1 (
  echo Aviso: nao foi possivel atualizar. O site abre com os ultimos dados guardados.
  pause
)

echo A abrir o dashboard em http://localhost:8000 ...
echo Fecha esta janela para desligar o servidor.
start "" "http://localhost:8000/?abrir=%RANDOM%"
"%PY%" scripts\servir.py 8000
