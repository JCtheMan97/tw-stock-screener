#!/bin/bash
# run_dashboard.sh
# 一鍵啟動台股大波段蓄勢與突破模型 Web 戰情室

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "🚀 正在啟動台股大波段蓄勢與突破模型・Web 視覺化戰情室..."
echo "=========================================================="

# 啟用虛擬環境
source "$SCRIPT_DIR/venv/bin/activate"

# 檢查是否已有最新資料，若無則自動先執行一次初篩
if [ ! -f "$SCRIPT_DIR/cache/latest_screen_data.json" ]; then
    echo "📊 首次啟動：正在初始化全市場選股資料庫 (約10秒)..."
    python "$SCRIPT_DIR/main.py" --dry-run
fi

echo "🌐 即將在瀏覽器自動開啟戰情室 (http://localhost:8501) ..."
streamlit run "$SCRIPT_DIR/app.py" --server.port 8501
