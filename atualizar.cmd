@echo off
setlocal
cd /d "%~dp0"
set LEAGUE_ID=12258
set FPL_ENTRY_ID=2420779
set FPL_LEAGUE_ID=779399

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python nao encontrado. Instala-o de https://www.python.org e tenta de novo.
  pause
  exit /b 1
)

echo A atualizar os dados da liga Draft...
"%PY%" scripts\fetch_data.py
if errorlevel 1 (
  echo Aviso: nao foi possivel atualizar o Draft. O site abre com os ultimos dados.
  pause
)

echo.
echo A atualizar a FPL classica...
"%PY%" scripts\fetch_classica.py
if errorlevel 1 (
  echo Aviso: nao foi possivel atualizar a classica.
)

echo.
echo A abrir o dashboard. O endereco para o telemovel aparece abaixo.
echo Fecha esta janela para desligar o servidor.
echo.
start "" "http://localhost:8000/?abrir=%RANDOM%"
"%PY%" scripts\servir.py 8000
