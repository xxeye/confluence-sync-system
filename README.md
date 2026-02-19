# Confluence Sync System

Confluence 美術資源自動同步系統，支援多專案管理與擴展。

監聽本地資料夾 → 計算差異 → 自動同步附件到 Confluence → 重新渲染資源清單頁面。

---

## 功能特點

- 🔄 **自動同步**：監聽本地資料夾變更，自動上傳 / 更新 / 刪除 Confluence 附件
- 🚀 **並發處理**：支援多執行緒下載校驗、上傳、刪除
- 🎯 **精確比對**：MD5 哈希比對，只處理真正變更的檔案
- 🏗️ **插件式架構**：新增專案只需實作三個類別，不修改核心代碼
- 📝 **版本歷史**：自動記錄每次同步的變更摘要
- 🎯 **多專案並行**：單一程式同時監聽多個專案
- ✅ **命名驗證**：可選的檔名規範驗證器，在 Confluence 頁面標示異常檔案
- 📋 **說明文件**：從 xlsx 讀取圖片說明，自動填入頁面對應欄位

---

## 專案結構

```
confluence-sync-system/
├── config/                     # 配置文件
│   ├── base.yaml              # 配置範本（含所有可用欄位說明）
│   ├── game_dict.yaml         # 命名規範字典範例（由 Google Sheets 匯出）
│   └── project_*.yaml         # 各專案實際配置（列入 .gitignore）
├── core/                       # 核心引擎（不含業務邏輯）
│   ├── sync_engine.py         # 同步引擎基類與 SyncDiff
│   ├── confluence_client.py   # Confluence REST API 封裝
│   ├── file_monitor.py        # 檔案監聽器（含防抖）
│   ├── hash_calculator.py     # MD5 哈希計算
│   └── state_manager.py       # 狀態快取與版本歷史管理
├── projects/                   # 專案實作（插件）
│   └── slot_game/
│       ├── classifier.py      # 資源分類邏輯
│       ├── page_builder.py    # Confluence XHTML 生成
│       ├── validator.py       # 檔名驗證器（可選）
│       └── sync_engine.py     # 專案同步引擎
├── utils/                      # 工具模組
│   ├── logger.py              # 日誌系統
│   ├── retry.py               # 重試裝飾器
│   ├── config_loader.py       # YAML 配置載入（支援環境變數）
│   └── note_loader.py         # xlsx 說明文件載入器
├── docs/
│   ├── README.md              # asset_notes.xlsx 使用說明
│   └── export_dict.gs         # Google Sheets Apps Script（匯出字典用）
├── tests/                      # 測試
├── multi_project_manager.py    # 多專案管理入口
├── configs.txt                 # 多專案配置清單（列入 .gitignore）
└── requirements.txt
```

---

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
# Windows
set CONFLUENCE_TOKEN=your_api_token_here

# macOS / Linux
export CONFLUENCE_TOKEN=your_api_token_here
```

### 3. 建立配置文件

```bash
cp config/base.yaml config/my_project.yaml
# 編輯 my_project.yaml，填入 Confluence 資訊
```

最小配置範例：

```yaml
project:
  name: "MyProject"
  type: "slot_game"

confluence:
  url: "https://your-domain.atlassian.net"
  page_id: "YOUR_PAGE_ID"
  email: "your@email.com"
  api_token: "${CONFLUENCE_TOKEN}"
  user_account_id: "YOUR_ACCOUNT_ID"

sync:
  target_folder: "./art_assets"
```

### 4. 執行

```bash
# 監聽模式（持續監控，推薦）
python multi_project_manager.py --configs config/my_project.yaml --mode watch

# 單次同步
python multi_project_manager.py --configs config/my_project.yaml --mode once

# 預覽模式（不實際執行）
python multi_project_manager.py --configs config/my_project.yaml --mode once --dry-run
```

---

## 多專案同時運行

```bash
# 建立配置清單
cat > configs.txt << 'EOF'
config/project_a.yaml
config/project_b.yaml
config/project_c.yaml
EOF

# 啟動多專案監聽
python multi_project_manager.py --config-list configs.txt --mode watch
```

詳細說明請參考 [MULTI_PROJECT_GUIDE.md](MULTI_PROJECT_GUIDE.md)。

---

## 完整配置說明

```yaml
project:
  name: "專案顯示名稱"
  type: "slot_game"           # 對應 projects/ 下的資料夾名稱

confluence:
  url: "https://your-domain.atlassian.net"
  page_id: "頁面 ID"
  email: "帳號 Email"
  api_token: "${CONFLUENCE_TOKEN}"   # 建議使用環境變數
  user_account_id: "帳號 Account ID"
  notes_file: "./asset_notes.xlsx"   # 說明文件路徑，不存在時靜默略過
  jira_filter_url: ""                # Jira 篩選器 URL（可選）
  page_width: "full-width"           # full-width / fixed-width

sync:
  target_folder: "./art_assets"      # 監聽的資料夾路徑
  watch_delay: 10                    # 防抖延遲（秒）
  max_workers:
    download: 15                     # 啟動時並發下載校驗數
    delete: 1                        # 並發刪除數
    upload: 3                        # 並發上傳數
  history_keep: 5                    # 保留歷史筆數

file_patterns:
  include: ["*.png", "*.jpg", "*.jpeg"]
  exclude: ["*_temp.*", "*_backup.*"]

cache:
  remote_state_file: ".sync_cache.json"
  history_file: "version_history.json"

# 命名驗證器（可選，預設停用）
validator:
  enabled: false
  dict_file: "config/game_dict.yaml"   # 命名規範字典
  naming_doc_url: ""                    # 規範文件連結，顯示在頁面警告中
```

---

## 命名驗證器

啟用後（`validator.enabled: true`），每次渲染頁面時自動驗證所有檔名，異常檔案會在 Confluence 頁面上以橘色標示，並在頁面頂部顯示彙整列表。

驗證項目包含：
- 雲端同步衝突複本（如 `file (1).png`、`file - 複製.png`）
- macOS / Office 系統暫存檔
- 檔名含空白字元
- 欄位數量不足
- 命名欄位違反字典規範

字典文件（`game_dict.yaml`）由 Google Sheets 匯出，使用 `docs/export_dict.gs` 自動生成。

---

## 說明文件（asset_notes.xlsx）

放置於專案資料夾旁，美術人員手動維護。格式為兩欄：A 欄填檔名或群組名，B 欄填說明文字。

詳細格式說明請參考 [docs/README.md](docs/README.md)。

---

## 日誌

輸出至終端與 `logs/專案名稱_YYYYMMDD.log`。

| 圖示 | 說明 |
|------|------|
| 🏁 | 啟動 |
| 📡 | 連線雲端 |
| 🚀 | 開始處理 |
| 🔄 | 處理中 |
| 🆕 | 新增 |
| 🗑️ | 刪除 |
| ✅ | 完成 |
| ❌ | 錯誤 |
| 👁️ | 監控中 |

---

## 故障排除

**API Token 無效**
- 確認環境變數是否正確設定
- 確認 Token 有對應頁面的讀寫權限

**上傳失敗**
- 確認檔案大小未超過 Confluence 限制（預設 10MB）
- 確認頁面未被鎖定

**監聽無反應**
- 確認 `target_folder` 路徑存在且正確
- 確認檔案符合 `file_patterns.include` 規則
- 查看 `logs/` 下的日誌

---

## 開發

```bash
# 執行測試
pytest tests/ -v

# 程式碼風格
flake8 core/ projects/ utils/
```

---

## 授權

MIT License
