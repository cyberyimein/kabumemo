@echo off
setlocal

for /f "tokens=3" %%i in ('chcp') do set "ORIGINAL_CP=%%i"
chcp 65001 >nul

set "SKIP_PAUSE=0"
if /i "%~1"=="--no-pause" (
    set "SKIP_PAUSE=1"
)

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "ERROR_FLAG=0"

echo =============================================
echo   Kabumemo 開発環境起動バッチ
echo =============================================

echo プロジェクトルート: %ROOT%

if not exist "%BACKEND_DIR%" (
    echo [ERROR] backend ディレクトリが見つかりません: %BACKEND_DIR%
    set "ERROR_FLAG=1"
    goto :pause_and_exit
)

if not exist "%FRONTEND_DIR%" (
    echo [ERROR] frontend ディレクトリが見つかりません: %FRONTEND_DIR%
    set "ERROR_FLAG=1"
    goto :pause_and_exit
)

call :setup_backend || goto :error
call :setup_frontend || goto :error

echo.
echo Backend: http://127.0.0.1:8000/
echo Frontend: http://localhost:5173/
echo ログはそれぞれの新しいコマンドウィンドウで確認・停止できます。
goto :pause_and_exit

:setup_backend
    pushd "%BACKEND_DIR%" >nul 2>&1 || exit /b 1
    echo [Backend] Python 仮想環境を確認します...
    if not exist ".venv\Scripts\python.exe" (
        echo [Backend] 仮想環境を作成します...
        python -m venv .venv || (popd >nul 2>&1 & exit /b 1)
    )
    set "BACKEND_PY=.venv\Scripts\python.exe"
    echo [Backend] 依存関係を確認します...
    if not exist ".venv\Scripts\uvicorn.exe" (
        echo [Backend] 依存関係をインストールします...
        %BACKEND_PY% -m pip install --upgrade pip setuptools || (popd >nul 2>&1 & exit /b 1)
        %BACKEND_PY% -m pip install . || (popd >nul 2>&1 & exit /b 1)
    ) else (
        echo [Backend] 依存関係は既にインストールされています。
    )
    echo [Backend] サーバーを起動します...
    start "Kabumemo Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && %BACKEND_PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    popd >nul 2>&1
    exit /b 0

:setup_frontend
    pushd "%FRONTEND_DIR%" >nul 2>&1 || exit /b 1
    echo [Frontend] 依存関係を確認します...
    if not exist "node_modules" (
        echo [Frontend] npm install を実行します...
        call npm install --no-audit --no-fund || (popd >nul 2>&1 & exit /b 1)
    ) else (
        echo [Frontend] node_modules が見つかりました。インストールをスキップします。
    )
    echo [Frontend] 開発サーバーを起動します...
    start "Kabumemo Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"
    popd >nul 2>&1
    exit /b 0

:error
set "ERROR_FLAG=1"

echo.
echo [ERROR] 起動処理の途中でエラーが発生しました。上記ログを確認してください。

goto :pause_and_exit

:pause_and_exit
echo.
if "%ERROR_FLAG%"=="0" (
    echo すべての処理が完了しました。サービス終了時は各ウィンドウで ^C を押してください。
) else (
    echo エラーが発生しました。必要に応じてウィンドウを確認し、再実行してください。
)
if "%SKIP_PAUSE%"=="0" (
    pause
)
if defined ORIGINAL_CP chcp %ORIGINAL_CP% >nul
exit /b %ERROR_FLAG%
