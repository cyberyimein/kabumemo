@echo off
setlocal EnableDelayedExpansion

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
set "DIST_DIR=%FRONTEND_DIR%\dist"
set "SERVER_HOST=%KABUMEMO_HOST%"
if not defined SERVER_HOST set "SERVER_HOST=0.0.0.0"
set "SERVER_URL=http://%SERVER_HOST%:8000"
set "SERVER_HINT=%SERVER_URL%"
if /i "%SERVER_HOST%"=="0.0.0.0" set "SERVER_HINT=http://127.0.0.1:8000"
set "BACKEND_VENV=%BACKEND_DIR%\.venv"
set "BACKEND_SCRIPTS=%BACKEND_VENV%\Scripts"
set "BACKEND_PY=%BACKEND_SCRIPTS%\python.exe"
set "BOOTSTRAP_PY="
set "BOOTSTRAP_SOURCE="
set "MAMBA_EXE="
set "MAMBA_BASE="
set "ERROR_FLAG=0"

if not exist "%BACKEND_DIR%" (
    echo [ERROR] backend ディレクトリが見つかりません: %BACKEND_DIR%
    set "ERROR_FLAG=1"
    goto :cleanup
)

if not exist "%FRONTEND_DIR%" (
    echo [ERROR] frontend ディレクトリが見つかりません: %FRONTEND_DIR%
    set "ERROR_FLAG=1"
    goto :cleanup
)

echo =============================================
echo   Kabumemo デプロイモード起動バッチ
echo =============================================

echo プロジェクトルート: %ROOT%

echo.
call :select_bootstrap_python
if not defined BOOTSTRAP_PY (
    set "BOOTSTRAP_PY=python"
    set "BOOTSTRAP_SOURCE=system PATH python"
)
echo [Backend] 仮想環境ブートストラップ Python: !BOOTSTRAP_SOURCE! -> !BOOTSTRAP_PY!

call :ensure_backend || goto :error

if not exist "%BACKEND_PY%" (
    echo [Backend] 仮想環境の python が見つかりません: %BACKEND_PY%
    set "ERROR_FLAG=1"
    goto :cleanup
)

set "VIRTUAL_ENV=%BACKEND_VENV%"
set "PATH=%BACKEND_SCRIPTS%;%PATH%"
set "PYTHONHOME="
echo [Backend] 仮想環境を有効化しました: %BACKEND_PY%

call :build_frontend || goto :error

echo.
echo [Server] フロントエンド dist ディレクトリがあれば FastAPI から配信します！
echo [Server] アクセス URL: !SERVER_HINT!
echo [Server] Uvicorn を起動しています ^(Ctrl+C で停止^)...
echo.
set "KABUMEMO_DIST_DIR=%DIST_DIR%"
pushd "%BACKEND_DIR%" >nul 2>&1
"%BACKEND_PY%" -m uvicorn app.main:app --host %SERVER_HOST% --port 8000
set "ERROR_FLAG=%ERRORLEVEL%"
popd >nul 2>&1
goto :cleanup

:ensure_backend
    pushd "%BACKEND_DIR%" >nul 2>&1 || exit /b 1
    echo [Backend] Python 仮想環境を確認します...
    if not exist "%BACKEND_PY%" (
        echo [Backend] 仮想環境を作成します... ^(!BOOTSTRAP_PY!^)
        "!BOOTSTRAP_PY!" -m venv .venv || (popd >nul 2>&1 & exit /b 1)
    )
    echo [Backend] 依存関係を確認します...
    if not exist "%BACKEND_SCRIPTS%\uvicorn.exe" (
        echo [Backend] 依存関係をインストールします...
        "%BACKEND_PY%" -m pip install --upgrade pip setuptools wheel || (popd >nul 2>&1 & exit /b 1)
        "%BACKEND_PY%" -m pip install . || (popd >nul 2>&1 & exit /b 1)
    ) else (
        echo [Backend] 依存関係は既にインストールされています。
    )
    popd >nul 2>&1
    exit /b 0

:select_bootstrap_python
    if defined KABUMEMO_BASE_PY (
        if exist "%KABUMEMO_BASE_PY%" (
            set "BOOTSTRAP_PY=%KABUMEMO_BASE_PY%"
            set "BOOTSTRAP_SOURCE=KABUMEMO_BASE_PY"
            goto :eof
        ) else (
            echo [Backend][WARN] 指定された KABUMEMO_BASE_PY が見つかりません: %KABUMEMO_BASE_PY%
        )
    )

    for /f "delims=" %%i in ('where mamba 2^>nul') do if not defined MAMBA_EXE set "MAMBA_EXE=%%i"
    if defined MAMBA_EXE (
        for /f "delims=" %%i in ('"%MAMBA_EXE%" info --base 2^>nul') do if not defined MAMBA_BASE set "MAMBA_BASE=%%i"
        if defined MAMBA_BASE (
            if exist "%MAMBA_BASE%\python.exe" (
                set "BOOTSTRAP_PY=%MAMBA_BASE%\python.exe"
                set "BOOTSTRAP_SOURCE=mamba base (%MAMBA_BASE%)"
                goto :eof
            ) else (
                echo [Backend][WARN] mamba base に python.exe が見つかりません: %MAMBA_BASE%
            )
        ) else (
            echo [Backend][WARN] mamba base のパスを取得できませんでした。"%MAMBA_EXE%"
        )
    )
    goto :eof

:build_frontend
    pushd "%FRONTEND_DIR%" >nul 2>&1 || exit /b 1
    echo [Frontend] 依存関係を確認します...
    if not exist "node_modules" (
        echo [Frontend] npm install を実行します...
        call npm install --no-audit --no-fund || (popd >nul 2>&1 & exit /b 1)
    ) else (
        echo [Frontend] node_modules が見つかりました。インストールをスキップします。
    )
    echo [Frontend] 静的アセットをビルドします...
    call npm run build || (popd >nul 2>&1 & exit /b 1)
    if not exist "dist" (
        echo [Frontend][WARN] dist ディレクトリが生成されませんでした。
        popd >nul 2>&1
        exit /b 1
    ) else (
        echo [Frontend] dist ディレクトリ: %DIST_DIR%
    )
    popd >nul 2>&1
    exit /b 0

:error
set "ERROR_FLAG=1"

echo.
echo [ERROR] 実行中にエラーが発生しました。上記ログを確認してください。

goto :cleanup

:cleanup
echo.
if "%ERROR_FLAG%"=="0" (
    echo [Server] 正常終了しました。ウィンドウを閉じるには Ctrl+C で停止してください。
) else (
    echo [Server] エラーが発生しました。必要に応じてログを確認してください。
)
if "%SKIP_PAUSE%"=="0" (
    echo.
    pause
)
if defined ORIGINAL_CP chcp %ORIGINAL_CP% >nul
exit /b %ERROR_FLAG%
