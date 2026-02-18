@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion
chcp 950 >nul

REM 多專案管理器快速啟動腳本（Windows）
echo Confluence Sync System - 多專案管理器
echo ==========================================
echo.

REM 檢查 Python
@where python >nul 2>nul
@if errorlevel 1 (
  echo [錯誤] 未找到 Python。請先安裝 Python 3 並加入 PATH。
  echo.
  pause
  exit /b 1
)

REM 檢查 venv
@if not exist "venv\" (
  echo [資訊] 建立虛擬環境 venv...
  @python -m venv venv
  @if errorlevel 1 (
    echo [錯誤] 建立虛擬環境失敗。
    echo.
    pause
    exit /b 1
  )
)

REM 啟動 venv
echo [資訊] 啟動虛擬環境...
@call "venv\Scripts\activate.bat"
@if errorlevel 1 (
  echo [錯誤] 啟動 venv 失敗（venv\Scripts\activate.bat）。
  echo.
  pause
  exit /b 1
)

REM 安裝依賴（用 python -m pip 確保是 venv 的 pip）
echo [資訊] 安裝/更新依賴（requirements.txt）...
@python -m pip install -q -r requirements.txt
@if errorlevel 1 (
  echo [錯誤] 安裝依賴失敗（requirements.txt / 網路 / 權限）。
  echo.
  pause
  exit /b 1
)

echo.
echo [完成] 環境準備完成！
echo.

REM 檢查 configs.txt
@if not exist "configs.txt" (
  echo [警告] 未找到配置清單 configs.txt
  echo        請先建立 configs.txt，範例：
  echo          config/project_a.yaml
  echo          config/project_b.yaml
  echo          config/project_c.yaml
  echo.
  pause
  exit /b 1
)

REM 統計配置數量（排除註解與空行）
set /a CONFIG_COUNT=0
for /f "usebackq delims=" %%L in (`type "configs.txt" ^| findstr /R /V "^[ 	]*$" ^| findstr /R /V "^[ 	]*#"`) do (
  set /a CONFIG_COUNT+=1
)

echo [資訊] 找到 !CONFIG_COUNT! 個專案配置
echo.

if !CONFIG_COUNT! LEQ 0 (
  echo [警告] configs.txt 內沒有有效配置（空白或全是註解）。
  echo.
  pause
  exit /b 1
)

REM 預設一律監聽模式（watch）
echo [執行] 啟動監聽模式（watch）...
echo.
@python multi_project_manager.py --config-list configs.txt --mode watch %*
@if errorlevel 1 (
  echo.
  echo [錯誤] multi_project_manager.py 執行失敗（watch）。請查看上方錯誤訊息。
  echo.
  pause
  exit /b 1
)

endlocal
