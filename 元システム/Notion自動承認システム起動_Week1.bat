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
"%PYTHON%" "%SCRIPT_DIR%invite_notion_week1.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week1_week2.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week2_week3.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week3_week4.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week4_week5.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week5_week6.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week6_week7.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week7_week8.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week8_week9.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week9_week10.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week10_week11.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week11_week12.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week12_week13.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week13_week14.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week14_week15.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week15_week16.py"
    timeout /t 3 >nul

    "%PYTHON%" "%SCRIPT_DIR%invite_notion_week16_week17.py"


echo 3分待機中...
timeout /t 180 >nul
goto LOOP