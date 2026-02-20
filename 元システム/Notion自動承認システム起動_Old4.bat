@echo off
chcp 65001 >nul

echo ==== Python の場所を自動検出中 ====
for /f "delims=" %%i in ('where python') do (
    set PYTHON=%%i
    goto FOUND_PYTHON
)

echo Python が見つかりません。
pause
exit /b

:FOUND_PYTHON
echo 使用するPython → %PYTHON%
echo ----------------------------------------

REM ==== ライブラリ確認 → 無ければインストール ====

echo.
echo ==== ライブラリの確認を行います ====

REM -- selenium --
"%PYTHON%" -c "import selenium" 2>nul
if errorlevel 1 (
    echo selenium がありません → インストールします
    "%PYTHON%" -m pip install selenium
) else (
    echo selenium → インストール済み
)

REM -- webdriver-manager --
"%PYTHON%" -c "import webdriver_manager" 2>nul
if errorlevel 1 (
    echo webdriver-manager がありません → インストールします
    "%PYTHON%" -m pip install webdriver-manager
) else (
    echo webdriver-manager → インストール済み
)

REM -- gspread --
"%PYTHON%" -c "import gspread" 2>nul
if errorlevel 1 (
    echo gspread がありません → インストールします
    "%PYTHON%" -m pip install gspread
) else (
    echo gspread → インストール済み
)

REM -- oauth2client --
"%PYTHON%" -c "import oauth2client" 2>nul
if errorlevel 1 (
    echo oauth2client がありません → インストールします
    "%PYTHON%" -m pip install oauth2client
) else (
    echo oauth2client → インストール済み
)

echo ----------------------------------------
echo ==== ライブラリチェック完了 ====
echo ----------------------------------------

REM ==== BATファイルが存在するフォルダを取得 ====
set SCRIPT_DIR=%~dp0
echo スクリプトフォルダ → %SCRIPT_DIR%
echo ----------------------------------------

REM ==== 自動実行ループ開始 ====
:LOOP
echo ==== Notion 招待処理を実行します ====
"%PYTHON%" "%SCRIPT_DIR%invite_notion_Old4_week5.py"

echo 3待機中...
timeout /t 180 >nul
goto LOOP