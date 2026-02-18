#!/bin/bash

# Confluence Sync System - 快速啟動腳本

echo "🚀 Confluence Sync System"
echo "=============================="
echo ""

# 檢查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 錯誤：未找到 Python 3"
    exit 1
fi

# 檢查虛擬環境
if [ ! -d "venv" ]; then
    echo "📦 創建虛擬環境..."
    python3 -m venv venv
fi

# 啟動虛擬環境
echo "🔧 啟動虛擬環境..."
source venv/bin/activate

# 安裝依賴
echo "📥 檢查依賴..."
pip install -q -r requirements.txt

echo ""
echo "✅ 環境準備完成！"
echo ""

# 檢查配置文件
if [ ! -f "config/project_a.yaml" ]; then
    echo "⚠️  警告：未找到配置文件 config/project_a.yaml"
    echo "請先複製 config/base.yaml 並配置您的專案資訊"
    echo ""
    echo "執行以下命令："
    echo "  cp config/base.yaml config/project_a.yaml"
    echo "  vim config/project_a.yaml  # 編輯配置"
    echo ""
    exit 1
fi

# 顯示使用方式
echo "📖 使用方式："
echo ""
echo "  監聽模式（持續運行）："
echo "    python main.py --config config/project_a.yaml --mode watch"
echo ""
echo "  單次執行："
echo "    python main.py --config config/project_a.yaml --mode once"
echo ""
echo "  Dry-run 模式（僅預覽）："
echo "    python main.py --config config/project_a.yaml --mode once --dry-run"
echo ""

# 如果提供參數，直接執行
if [ $# -gt 0 ]; then
    python main.py "$@"
else
    # 預設執行監聽模式
    echo "🎯 啟動監聽模式..."
    echo ""
    python main.py --config config/project_a.yaml --mode watch
fi
