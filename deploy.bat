@echo off
setlocal

echo ===============================
echo   PAYGAS ONE-CLICK DEPLOY
echo ===============================

cd /d %~dp0

REM ===== CONFIG =====
set APP_NAME=pyGas
set ENTRY=backend.py
set DIST_DIR=dist
set DB_FILE=lpg_transactions.db
set FRONTEND_SRC=frontend\dist
set FRONTEND_DEST=dist\frontend
set NSSM_PATH="C:\Program Files\NSSM\nssm.exe"

echo.
echo [1/6] Installing Python dependencies...
python -m pip install -r requirements.txt
python -m pip install -U pyinstaller

echo.
echo [2/6] Cleaning old builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del %APP_NAME%.spec 2>nul

echo.
echo [3/6] Building executable...
pyinstaller %ENTRY% --onefile --name %APP_NAME% --collect-submodules application

echo.
echo [4/6] Copying required files...
copy %DB_FILE% %DIST_DIR%\ >nul
mkdir %FRONTEND_DEST% 2>nul
xcopy %FRONTEND_SRC% %FRONTEND_DEST% /E /I /Y >nul

echo.
echo [5/6] Installing Windows service...

cd %DIST_DIR%

REM Stop & remove existing service (ignore errors)
%NSSM_PATH% stop %APP_NAME% 2>nul
%NSSM_PATH% remove %APP_NAME% confirm 2>nul

REM Install service
%NSSM_PATH% install %APP_NAME% "%CD%\%APP_NAME%.exe" --port 3 --api-port 8000

REM Optional: auto-start
%NSSM_PATH% set %APP_NAME% Start SERVICE_AUTO_START

echo.
echo [6/6] Starting service...
%NSSM_PATH% start %APP_NAME%

echo.
echo ===============================
echo   DEPLOY COMPLETE ✅
echo ===============================
echo.
echo Service Name: %APP_NAME%
echo API: http://localhost:8000
echo.

pause
