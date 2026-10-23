# 🚀 台股「翻倍大波段」蓄勢模型與 LINE 自動推播工作流

專為捕捉台股**「翻倍大波段起漲前夕」**所設計的量化選股與推播系統。  
結合 **Mark Minervini SEPA 趨勢模板、0050 Alpha RS 相對強度、VCP 量價收縮 (Dead Quiet)、外資波段狂買、集保千張大戶籌碼鎖定** 與 **細分次族群共振聚類**，每個台股交易日盤後自動執行並推播精選清單至您的 LINE。

---

## 🎯 大波段起漲前夕核心型態

根據實戰經驗，翻倍大飆股在起漲前夕具備高度一致的**「主力暗中壓盤吃貨（Stealth Accumulation）」**軌跡：
1. **外資狂買一陣子**：過去 15~20 個交易日內持續吸籌，買超天數比率過半（$\ge 50\% \sim 60\%$），累計買超大幅淨流入。
2. **股價狹幅橫盤不動**：近 20 日高低價格震盪幅度極小（$\le 10\% \sim 12\%$），主力壓盤吃貨、以盤代跌。
3. **集保千張大戶增加**：直接串接台灣集保結算所（TDCC）股權分散表，千張大戶持股連續攀升或高度鎖籌（$\ge 50\%$），散戶持股持續退場。
4. **成交量極致萎縮**：符合 Minervini VCP 與 Pine Script 的 `Dead Quiet`（靜止平台，3日均量 < 20日均量 70%）或 `VCP 80+Tight CV`，浮額被徹底清洗。
5. **趨勢健康 + 強於大盤**：符合 Minervini 7 大趨勢條件，且 $Alpha\_RS > 100$ 對照 0050 呈現領先動能。
6. **次族群共振性 ⭐**：整合 2,045+ 檔台股次產業分類（CPO、散熱、BBU、先進封裝等），**同細分次族群內有 $\ge 2$ 檔**同時符合蓄勢條件，優先置頂推播！

---

## 📱 LINE 推播樣式

```text
🚀【台股大波段蓄勢・族群共振報告】
📅 交易日期：2026-10-23
🎯 嚴選標的：共 4 檔符合所有大波段蓄勢模板
━━━━━━━━━━━━━━━━━━━━
🔥 族群共振區（同產業 ≥ 2 檔同步蓄勢）：

【AI伺服器 BBU 備用電池】(2 檔符合 | 外資波段大買 +6,250張)
• 6781 AES-KY  $780.0 (+2.50)
  📦 20日振幅：6.8% (極度緊縮) | 💎 極致壓縮(80%+CV)
  🏛️ 外資吸籌：20日累計買超 +3,850張 (買超天數比 75%)
  👥 千張大戶：72.4% (週增 +1.25%)
  📈 動能指標：Minervini 7 條件全符 | 🌟 Alpha領先

• 3211 順達  $162.0 (+0.50)
  📦 20日振幅：8.2% (極度緊縮) | 💤 Dead Quiet (靜止平台)
  🏛️ 外資吸籌：20日累計買超 +2,400張 (買超天數比 65%)
  👥 千張大戶：58.1% (週增 +0.40%)
  📈 動能指標：Minervini 7 條件全符 | 📈 動能回復中
━━━━━━━━━━━━━━━━━━━━
```

---

## 🛠️ LINE Messaging API 設定指南 (完全免費)

> [!NOTE]
> LINE Notify 服務已於 2025 年 3 月 31 日終止。本專案採用官方 **LINE Messaging API (LINE Bot)**，個人推播方案提供每月 **200 則免費發送額度**（本系統每個交易日推送 1 則，每月約 20~22 則，完全在免費額度內）。

### 步驟 1：建立 LINE Channel
1. 登入 [LINE Developers Console](https://developers.line.biz/)。
2. 建立或選擇一個 **Provider**（例如「StockBot」）。
3. 點選 **Create a new channel**，選擇 **Messaging API**。
4. 填寫名稱與基本資料後建立。

### 步驟 2：取得金鑰與 User ID
1. **Channel Access Token**：進入剛建立的 Channel → 點選 **Messaging API** 頁籤 → 滑到最下方點擊 **Issue** 產生長效 Token。
2. **User ID**：進入 **Basic settings** 頁籤 → 滑到最下方找到 **Your user ID**（一串以 `U` 開頭的字串）。
3. **加 Bot 好友**：在 **Messaging API** 頁籤掃描 QR Code 將您自建的 Bot 加入好友。

### 步驟 3：設定本機環境變數
在專案根目錄建立 `.env` 檔案：
```bash
LINE_CHANNEL_ACCESS_TOKEN=填入您的Channel_Access_Token
LINE_USER_ID=填入您的User_ID
```

---

## 💻 本地端使用方式

### 方式 A：一鍵開啟 Web 視覺化戰情室（推薦 ⭐）
無需記憶任何指令，盤後或有空時在終端機輸入：
```bash
./run_dashboard.sh
```
或者手動啟動：
```bash
source venv/bin/activate
streamlit run app.py
```
- 瀏覽器將自動彈出戰情室首頁 (`http://localhost:8501`)。
- **六大功能分頁**：
  1. 🔥 **族群共振看板**：按次族群分塊展示、外資吸籌與集保大戶動態。
  2. ⭐ **獨立潛力標的**：單兵突進黑馬一覽。
  3. 📈 **互動式 K 線圖 (Plotly)**：切換檢視 50/150/200MA、10日 Pivot 頸線與成交量放量。
  4. 💎 **首選標的 SEPA 特檢報告**：已公布實質財報三率三期對照、EBITDA、FCF 與 Code 33 診斷。
  5. 🔍 **自選股即時特檢**：輸入任一台股代碼即時聯網生成基本面特檢。
  6. 📊 **30 天實質績效回測報告**：查看過去 2 年 70+ 檔標的實測數據。

---

### 方式 B：終端機命令列執行
```bash
# 1. 啟用虛擬環境
source venv/bin/activate

# 2. 執行篩選 (僅輸出終端機，自動存檔至 reports/)
python main.py --dry-run

# 3. 正式執行並推播至 LINE
python main.py
```

---

## ☁️ GitHub Actions 自動化部署 (每日 16:30 免費自動推播)

1. 將本專案 Push 至您的 GitHub 專案。
2. 進入 GitHub Repo → **Settings** → **Secrets and variables** → **Actions**。
3. 點擊 **New repository secret**，新增兩個環境密鑰：
   - `LINE_CHANNEL_ACCESS_TOKEN`: 填入您的 LINE Token
   - `LINE_USER_ID`: 填入您的 LINE User ID
4. 工作流排程已設定在 `.github/workflows/daily_screener.yml`，於**每個台股交易日 16:30（UTC 08:30）**自動執行。
5. 亦可在 GitHub **Actions** 頁籤隨時點擊 **Run workflow** 手動執行。
