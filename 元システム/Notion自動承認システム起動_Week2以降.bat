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

REM ==== 日付が変わったらフラグをリセット ====
if not "%date%"=="%LAST_DATE%" (
    set EXECUTED_TODAY=0
    set LAST_DATE=%date%
    echo 日付が変わったので実行フラグをリセットしました
)

REM ==== 現在時刻取得 ====
for /f "tokens=1-2 delims=:.," %%a in ("%time%") do (
    set HH=%%a
    set MN=%%b
)

REM 時刻の先頭スペース対策
if "%HH:~0,1%"==" " set HH=0%HH:~1,1%

echo 現在時刻：%HH%:%MN%

REM ==== 7:00前なら待機 ====
if %HH% LSS 7 (
    echo → 7:00前のため待機中...
    timeout /t 30 >nul
    goto LOOP
)

REM ==== 7:00以降 & 未実行なら処理開始 ====
if %EXECUTED_TODAY% EQU 0 (
    echo → 7:00になったので処理を実行します
    set EXECUTED_TODAY=1

    REM ====== ここから既存の処理 ======

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

    echo → 本日の7:00処理が完了しました
)

REM ==== 7時以降で実行済みなら通常待機 ====
timeout /t 300 >nul
goto LOOP