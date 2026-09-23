@echo off
rem NEXA CREDIT - lanceur Windows : double-cliquer sur ce fichier.
rem Premiere fois : installe les dependances (quelques minutes). Ensuite : demarrage direct.
rem Option : "NEXA.bat demo" cree en plus le cabinet de demonstration (dossiers fictifs).
setlocal
cd /d "%~dp0"
title NEXA CREDIT

rem --- Python 3.11 ou plus recent
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (where python >nul 2>&1 && set "PY=python")
if not defined PY goto :sans_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 || goto :sans_python

rem --- Interface (construite une seule fois ; necessite Node.js)
if exist "frontend\dist\index.html" goto :serveur
where npm >nul 2>&1 || goto :sans_node
echo [1/3] Construction de l'interface...
pushd frontend
call npm install --no-audit --no-fund || (popd & goto :erreur)
call npm run build || (popd & goto :erreur)
popd

:serveur
if exist "backend\.venv\Scripts\python.exe" goto :lancer
echo [2/3] Installation du serveur Python...
%PY% -m venv backend\.venv || goto :erreur
backend\.venv\Scripts\python -m pip install --quiet --upgrade pip
backend\.venv\Scripts\python -m pip install --quiet -r backend\requirements.txt || goto :erreur

:lancer
pushd backend
if /i "%~1"=="demo" .venv\Scripts\python -m app.demo
echo.
echo [3/3] NEXA CREDIT demarre sur http://127.0.0.1:8000
echo       Laissez cette fenetre ouverte. Pour arreter : fermez-la ou Ctrl+C.
echo.
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8000"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
popd
goto :fin

:sans_python
echo Python 3.11 ou plus recent est necessaire : https://www.python.org/downloads/
echo Pendant l'installation, cochez "Add python.exe to PATH", puis relancez NEXA.bat.
goto :erreur_pause

:sans_node
echo Node.js est necessaire pour la premiere installation : https://nodejs.org (version LTS)
echo Installez-le, puis relancez NEXA.bat.
goto :erreur_pause

:erreur
echo.
echo Une erreur est survenue. Copiez le message ci-dessus pour obtenir de l'aide.

:erreur_pause
pause
exit /b 1

:fin
endlocal
