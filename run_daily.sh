#!/bin/bash
# run_daily.sh
# 每日定時自動執行台股大波段選股與推播腳本

# 取得腳本所在目錄
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 啟用 Python 虛擬環境
source "$SCRIPT_DIR/venv/bin/activate"

# 執行選股主程式 (日誌寫入 logs/daily_run.log)
mkdir -p "$SCRIPT_DIR/logs"
TODAY=$(date "+%Y-%m-%d_%H%M%S")
echo "=== [${TODAY}] 開始執行台股大波段蓄勢選股 ===" >> "$SCRIPT_DIR/logs/daily_run.log"

python "$SCRIPT_DIR/main.py" >> "$SCRIPT_DIR/logs/daily_run.log" 2>&1

echo "=== [$(date '+%Y-%m-%d_%H%M%S')] 執行完成 ===" >> "$SCRIPT_DIR/logs/daily_run.log"
