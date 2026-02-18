# Confluence Sync System

企業級的 Confluence 資源自動同步系統，支援多專案管理與擴展。

## 功能特點

- 🔄 **自動同步**：監聽本地資料夾變更，自動同步到 Confluence
- 🚀 **高效能**：支援並發下載、上傳、刪除操作
- 🎯 **精確比對**：使用 MD5 哈希進行像素級精確比對
- 🏗️ **模組化架構**：易於擴展到多個專案
- 📝 **版本管理**：完整的變更歷史記錄
- 🔌 **插件式設計**：每個專案可自訂分類和頁面生成邏輯

## 專案結構

```
confluence-sync-system/
├── config/                 # 配置文件
│   ├── base.yaml          # 基礎配置範本
│   └── project_a.yaml     # 專案 A 配置範例
├── core/                   # 核心引擎
│   ├── sync_engine.py     # 同步引擎基類
│   ├── confluence_client.py  # Confluence API 封裝
│   ├── file_monitor.py    # 檔案監聽器
│   ├── hash_calculator.py # 哈希計算器
│   └── state_manager.py   # 狀態管理
├── projects/               # 專案實作
│   └── slot_game/         # Slot Game 專案
│       ├── classifier.py  # 資源分類邏輯
│       ├── page_builder.py # XHTML 生成邏輯
│       └── sync_engine.py # 專案同步引擎
├── utils/                  # 工具模組
│   ├── logger.py          # 日誌系統
│   ├── retry.py           # 重試裝飾器
│   └── config_loader.py   # 配置載入器
├── tests/                  # 測試文件
├── main.py                 # 主入口
└── requirements.txt        # 依賴套件
```

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 配置專案

複製配置範本並修改：

```bash
cp config/base.yaml config/my_project.yaml
# 編輯 my_project.yaml 填入你的 Confluence 資訊
```

配置範例：

```yaml
project:
  name: "MyProject"
  type: "slot_game"  # 專案類型

confluence:
  url: "https://your-domain.atlassian.net"
  page_id: "123456"
  email: "your@email.com"
  api_token: "${CONFLUENCE_TOKEN}"  # 從環境變數讀取
  user_account_id: "abc123"

sync:
  target_folder: "./art_assets"
  watch_delay: 10
  max_workers:
    download: 15
    delete: 1
    upload: 3
  history_keep: 5
```

### 3. 設定環境變數

```bash
export CONFLUENCE_TOKEN="your_api_token_here"
```

### 4. 執行同步

**監聽模式（持續監控）：**

```bash
python main.py --config config/my_project.yaml --mode watch
```

**單次執行模式：**

```bash
python main.py --config config/my_project.yaml --mode once
```

**Dry-run 模式（僅預覽變更）：**

```bash
python main.py --config config/my_project.yaml --mode once --dry-run
```

## 進階使用

### 多專案同時運行

```bash
# 終端 1
python main.py --config config/project_a.yaml --mode watch

# 終端 2
python main.py --config config/project_b.yaml --mode watch
```

### 自訂專案類型

1. 在 `projects/` 下創建新資料夾
2. 實作 `classifier.py`、`page_builder.py`、`sync_engine.py`
3. 在配置文件中指定 `project.type`

範例：

```python
# projects/my_custom_project/sync_engine.py
from core.sync_engine import BaseSyncEngine
from .classifier import MyClassifier
from .page_builder import MyPageBuilder

class MyProjectSyncEngine(BaseSyncEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.classifier = MyClassifier()
        self.page_builder = MyPageBuilder()
    
    def classify_assets(self, files):
        # 實作你的分類邏輯
        pass
    
    def build_page_content(self, categories, history):
        # 實作你的頁面生成邏輯
        pass
```

## 配置說明

### 完整配置選項

```yaml
project:
  name: "專案名稱"
  type: "slot_game"  # 專案類型，對應 projects/ 下的資料夾

confluence:
  url: "Confluence 網址"
  page_id: "頁面 ID"
  email: "帳號 Email"
  api_token: "API Token（建議使用環境變數）"
  user_account_id: "使用者 Account ID"

sync:
  target_folder: "監聽的資料夾路徑"
  watch_delay: 10  # 防抖延遲（秒）
  max_workers:
    download: 15  # 下載校驗並發數
    delete: 1     # 刪除並發數
    upload: 3     # 上傳並發數
  history_keep: 5  # 保留歷史記錄數量
  
file_patterns:
  include: ["*.png", "*.jpg", "*.jpeg"]  # 包含的檔案類型
  exclude: ["*_temp.*", "*_backup.*"]    # 排除的檔案類型

cache:
  remote_state_file: ".sync_cache.json"
  history_file: "version_history.json"
```

## 日誌說明

日誌會同時輸出到：
- 終端（即時顯示）
- 日誌文件（`logs/專案名稱_YYYYMMDD.log`）

圖示說明：
- 🏁 啟動
- 📡 連線雲端
- 🚀 開始處理
- 🔄 處理中
- ✨ 成功
- 🗑️ 刪除
- 🆕 新增
- ✅ 完成
- ❌ 錯誤
- 👁️ 監控中

## 故障排除

### API Token 無效

確認：
1. Token 是否已設定到環境變數
2. Token 是否有正確的權限
3. Email 和 Token 是否匹配

### 上傳失敗

檢查：
1. 檔案大小是否超過限制（預設 10MB）
2. 網路連線是否穩定
3. Confluence 頁面是否被鎖定

### 監聽無反應

確認：
1. `target_folder` 路徑是否正確
2. 檔案是否符合 `file_patterns.include` 規則
3. 檢查日誌中的錯誤訊息

## 開發指南

### 執行測試

```bash
pytest tests/ -v
```

### 程式碼風格檢查

```bash
flake8 core/ projects/ utils/
black core/ projects/ utils/
```

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 🎯 多專案管理

系統支援同時監聽多個專案！詳細說明請參考：

- **[多專案管理指南](MULTI_PROJECT_GUIDE.md)** - 完整的多專案配置和使用說明

### 快速開始

```bash
# 1. 創建多個專案配置
cp config/base.yaml config/project_a.yaml
cp config/base.yaml config/project_b.yaml

# 2. 編輯各專案配置（設定不同的 page_id 和 target_folder）

# 3. 創建配置清單
cat > configs.txt << 'EOL'
config/project_a.yaml
config/project_b.yaml
EOL

# 4. 啟動多專案監聽
./start_multi.sh watch

# 或直接執行
python multi_project_manager.py --config-list configs.txt --mode watch
```

支援 4 種部署方案：
- 📝 多專案管理器（推薦）
- 🖥️ 多終端分別運行
- 🐳 Docker Compose
- ⚙️ Systemd 服務

