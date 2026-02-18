@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

REM ============================================
REM Confluence Sync System - Windows 啟動腳本
REM ============================================

echo Confluence Sync System
echo ==============================
echo.

REM 檢查 Python 是否存在
@where python >nul 2>nul
@if errorlevel 1 (
  @echo [錯誤] 找不到 Python！
  @echo        請先安裝 Python 3，並在安裝時勾選「Add Python to PATH」。
  @exit /b 1
)

REM 若 venv 不存在則建立
@if not exist "venv\" (
  @echo [資訊] 建立虛擬環境 venv...
  @python -m venv venv
  @if errorlevel 1 (
    @echo [錯誤] 建立虛擬環境失敗。
    @exit /b 1
  )
)

REM 啟動 venv
@echo [資訊] 啟動虛擬環境...
@call "venv\Scripts\activate.bat"
@if errorlevel 1 (
  @echo [錯誤] 無法啟動虛擬環境（venv\Scripts\activate.bat）。
  @exit /b 1
)

REM 安裝依賴
@echo [資訊] 安裝/更新依賴（requirements.txt）...
@pip install -q -r requirements.txt
@if errorlevel 1 (
  @echo [錯誤] 安裝依賴失敗，請檢查 requirements.txt 或網路/權限狀態。
  @exit /b 1
)

@echo.
@echo [完成] 環境準備完成！
@echo.

REM 檢查設定檔
@if not exist "config\project_a.yaml" (
  @echo [警告] 找不到設定檔：config\project_a.yaml
  @echo        請先複製模板並填寫專案資訊：
  @echo.
  @echo        copy config\base.yaml config\project_a.yaml
  @echo        notepad config\project_a.yaml
  @echo.
  @exit /b 1
)

REM 顯示用法（中文）
@echo [用法]
@echo.
@echo   監聽模式（持續運行）：
@echo     python main.py --config config\project_a.yaml --mode watch
@echo.
@echo   單次執行：
@echo     python main.py --config config\project_a.yaml --mode once
@echo.
@echo   Dry-run 模式（只預覽不實作）：
@echo     python main.py --config config\project_a.yaml --mode once --dry-run
@echo.

REM 若沒帶參數，預設跑 watch；有帶參數就原樣轉交給 main.py
@if "%~1"=="" (
  @echo [執行] 啟動監聽模式...
  @echo.
  @python main.py --config config\project_a.yaml --mode watch
) else (
  @python main.py %*
)

@endlocal
