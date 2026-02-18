#!/bin/bash

# 多專案管理器快速啟動腳本

echo "🚀 Confluence Sync System - 多專案管理器"
echo "=========================================="
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
if [ ! -f "configs.txt" ]; then
    echo "⚠️  警告：未找到配置清單 configs.txt"
    echo "請先創建配置清單文件"
    echo ""
    echo "範例內容："
    echo "  config/project_a.yaml"
    echo "  config/project_b.yaml"
    echo "  config/project_c.yaml"
    echo ""
    exit 1
fi

# 統計配置數量
CONFIG_COUNT=$(grep -v '^#' configs.txt | grep -v '^$' | wc -l)
echo "📋 找到 $CONFIG_COUNT 個專案配置"
echo ""

# 顯示使用方式
if [ $# -eq 0 ]; then
    echo "📖 使用方式："
    echo ""
    echo "  1. 監聽模式（持續運行，推薦）："
    echo "     ./start_multi.sh watch"
    echo ""
    echo "  2. 單次同步（循序執行）："
    echo "     ./start_multi.sh once"
    echo ""
    echo "  3. 單次同步（並行執行，更快）："
    echo "     ./start_multi.sh once --parallel"
    echo ""
    echo "  4. 指定配置文件："
    echo "     ./start_multi.sh watch --configs config/project_a.yaml config/project_b.yaml"
    echo ""
    read -p "請選擇模式 (watch/once) [watch]: " MODE
    MODE=${MODE:-watch}
else
    MODE=$1
    shift
fi

# 執行
if [ "$MODE" = "watch" ]; then
    echo "🎯 啟動監聽模式..."
    echo ""
    python multi_project_manager.py --config-list configs.txt --mode watch "$@"
elif [ "$MODE" = "once" ]; then
    echo "🎯 執行單次同步..."
    echo ""
    python multi_project_manager.py --config-list configs.txt --mode once "$@"
else
    echo "❌ 未知模式: $MODE"
    echo "僅支援 watch 或 once"
    exit 1
fi
