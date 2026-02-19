# 系統架構說明

## 概覽

Confluence Sync System 是一個模組化、可擴展的資源自動同步系統，採用插件式架構設計，支援多專案並行管理。

核心功能：監聽本地資料夾 → 計算差異 → 同步到 Confluence → 重新渲染頁面。

---

## 核心設計理念

### 1. 關注點分離（Separation of Concerns）
- **核心引擎（core/）**：通用同步邏輯，不含任何專案業務邏輯
- **專案實現（projects/）**：專案特定的分類、驗證、頁面生成邏輯
- **工具模組（utils/）**：可跨專案重用的工具函數

### 2. 依賴倒置（Dependency Inversion）
- 核心引擎定義抽象介面（`BaseSyncEngine`）
- 具體專案繼承並實作介面
- 高層模組不依賴低層模組，兩者皆依賴抽象

### 3. 開放封閉原則（Open-Closed Principle）
- 對擴展開放：新增專案類型只需在 `projects/` 實作介面
- 對修改封閉：新增功能不需修改核心代碼

---

## 架構圖

```
┌──────────────────────────────────────────────────────────────┐
│                  multi_project_manager.py                    │
│                    （多專案管理入口）                           │
└──────────────────────┬───────────────────────────────────────┘
                       │  為每個專案建立獨立執行緒
          ┌────────────┴────────────┐
          │                        │
   ┌──────▼──────┐          ┌──────▼──────┐
   │  Project A  │          │  Project B  │  ...
   └──────┬──────┘          └──────┬──────┘
          │                        │
          └───────────┬────────────┘
                      │
        ┌─────────────▼──────────────┐
        │       BaseSyncEngine       │
        │        （抽象基類）          │
        └─────────────┬──────────────┘
                      │ 繼承
        ┌─────────────▼──────────────┐
        │    ProjectSyncEngine       │
        │      （具體實現）            │
        ├────────────────────────────┤
        │  + classifier              │
        │  + page_builder            │
        │  + validator（可選）        │
        │  + note_loader（可選）      │
        └────────────────────────────┘
```

---

## 模組說明

### core/ — 核心模組

#### sync_engine.py
- `BaseSyncEngine`：同步引擎抽象基類，定義完整的同步流程骨架
- `SyncDiff`：同步差異資料結構（to_add / to_update / to_delete）

**核心流程：**
1. 取得遠端狀態（首次或啟動時執行完整雲端同步）
2. 掃描本地檔案並計算 MD5
3. 計算差異（新增 / 更新 / 刪除）
4. 執行物理操作（刪除 → 上傳，並發執行）
5. 重新渲染頁面並推送
6. 儲存狀態快取

支援 `dry_run` 模式（僅預覽差異，不實際執行）。

#### confluence_client.py
封裝所有 Confluence REST API 操作，提供重試機制與統一錯誤處理。

主要方法：`get_page_content()` / `update_page_content()` / `get_all_attachments()` / `upload_attachment()` / `delete_attachment()` / `download_attachment()`

#### state_manager.py
管理遠端狀態快取（`sync_cache.json`）與版本歷史（`version_history.json`），提供持久化功能。

#### hash_calculator.py
MD5 哈希計算，用於本地與遠端的精確差異比對。

#### file_monitor.py
監聽檔案系統變更，內建防抖處理（預設 10 秒延遲），避免頻繁觸發同步。

---

### projects/ — 專案模組

每個專案包含以下組件：

#### classifier.py
負責資源分類，將檔案列表組織成頁面渲染所需的結構。

```python
def classify(self, asset) -> Tuple[str, Optional[str]]:
    # 回傳 (分類名稱, 群組鍵)
    # 群組鍵用於 NU 數字組與多國語系的分組
    pass

def organize_assets(self, files) -> Dict[str, Any]:
    # 回傳各分類的資源字典
    pass
```

#### page_builder.py
生成 Confluence XHTML，包含：
- 版本更新紀錄表格
- 命名異常彙整區塊（若啟用 validator）
- TOC 目錄
- Jira 任務清單（可選）
- Layout 版型格狀排列
- 一般素材表格（含圖片、檔名、尺寸、說明欄）
- 多國語系群組格狀排列
- NU 數字組格狀排列

命名警告以橘色 `<span>` 渲染（Confluence Cloud 不支援 `<td>` 上的 `color` style，橘色需放在內容層級）。

#### validator.py（slot_game 專屬）
檔名驗證器，依序執行：

| 層級 | 說明 |
|------|------|
| 0. 前置過濾 | 雲端同步衝突複本、系統暫存檔、空白字元等異常檔名 |
| 1. 欄位數量 | 欄數不足、NU 缺少 visualState、多國語系欄位位移偵測 |
| 2. name 空值 | name 欄不得為空 |
| 3. 底線檢查 | 各欄位值內不得含底線 |
| 4. 保留字重複 | name 不得與字典其他欄位已定義字詞重複 |
| 5. 禁詞 | name 不得為禁詞（完整比對，不分大小寫） |
| 6. NU 後綴 | type=nu 時第 5 欄必須是 bitmap_font |
| 7. 語系後綴 | type≠nu 時第 5 欄若有值必須是 language |

字典資料從 `config/game_dict.yaml` 載入（由 Google Sheets Apps Script 匯出）。

驗證器為可選功能，`validator.enabled=false` 時對同步與頁面渲染完全無影響。

#### sync_engine.py
整合分類器、頁面建構器、驗證器、說明文件載入器。

---

### utils/ — 工具模組

#### logger.py
統一日誌系統，支援終端彩色輸出與檔案持久化，圖示化日誌。

#### retry.py
重試裝飾器，提供指數退避與可配置重試次數。

#### config_loader.py
YAML 配置載入，支援環境變數替換（`${ENV_VAR}` 語法）。

#### note_loader.py
讀取 `asset_notes.xlsx` 說明文件，提供 `{key: 說明文字}` 對照表給 page_builder 使用。支援三種 key 格式：完整檔名、群組名（多國/NU），找不到時回傳空字串，不影響同步流程。

---

## 資料流

### 啟動同步流程

```
1. 載入配置（ConfigLoader）
   ↓
2. 初始化組件
   ├─ SyncLogger
   ├─ ConfluenceClient
   ├─ StateManager
   ├─ NoteLoader（可選）
   ├─ FilenameValidator（可選）
   └─ ProjectSyncEngine
   ↓
3. 完整雲端同步
   ├─ 並發下載所有附件（15 執行緒）
   ├─ 計算 MD5 哈希
   └─ 建立遠端狀態快照
   ↓
4. 掃描本地檔案
   ├─ 遞迴掃描 target_folder
   ├─ 計算本地 MD5
   └─ 建立本地狀態快照
   ↓
5. 計算差異（to_add / to_update / to_delete）
   ↓
6. 執行物理操作
   ├─ 並發刪除雲端冗餘（1 執行緒）
   └─ 並發上傳本地變更（3 執行緒）
   ↓
7. 重新渲染頁面
   ├─ 分類資源（classifier）
   ├─ 驗證檔名（validator，可選）
   ├─ 讀取說明（note_loader，可選）
   ├─ 生成 XHTML（page_builder）
   └─ 推送到 Confluence
   ↓
8. 儲存狀態快取與版本歷史
```

### 監聽模式流程

```
1. 執行啟動同步
   ↓
2. 啟動 FileMonitor
   ↓
3. 偵測到檔案變更
   ├─ 防抖處理（10 秒）
   └─ 過濾符合 file_patterns 的檔案
   ↓
4. 增量同步
   ├─ 沿用快取的遠端狀態
   ├─ 重新掃描本地
   └─ 計算差異並同步
   ↓
5. 回到步驟 3（循環）
```

---

## 擴展指南：新增專案類型

以新增 `card_game` 為例：

### 1. 建立專案目錄

```bash
mkdir -p projects/card_game
touch projects/card_game/__init__.py
```

### 2. 實作分類器

```python
# projects/card_game/classifier.py
class CardGameClassifier:
    def classify(self, asset):
        # 回傳 (分類名稱, 群組鍵)
        pass

    def organize_assets(self, files):
        # 回傳分類結果字典
        pass
```

### 3. 實作頁面建構器

```python
# projects/card_game/page_builder.py
class CardGamePageBuilder:
    def assemble(self, categories, history, **kwargs) -> str:
        # 回傳 Confluence XHTML
        pass
```

### 4. 實作同步引擎

```python
# projects/card_game/sync_engine.py
from core.sync_engine import BaseSyncEngine
from .classifier import CardGameClassifier
from .page_builder import CardGamePageBuilder

class CardGameSyncEngine(BaseSyncEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.classifier = CardGameClassifier()
        self.page_builder = CardGamePageBuilder()

    def classify_assets(self, files):
        return self.classifier.organize_assets(files)

    def build_page_content(self, categories, history):
        return self.page_builder.assemble(categories, history)
```

### 5. 建立配置文件

```yaml
# config/my_card_game.yaml
project:
  name: "CardGameX"
  type: "card_game"
confluence:
  url: "https://your-domain.atlassian.net"
  page_id: "YOUR_PAGE_ID"
  # ...
```

---

## 設計模式應用

| 模式 | 應用場景 | 實現方式 |
|------|---------|---------|
| 策略模式 | 專案分類邏輯 | 每個專案提供不同的 `Classifier` |
| 模板方法模式 | 同步流程 | `BaseSyncEngine.run_sync()` 定義骨架，子類實作細節 |
| 工廠模式 | 專案引擎建立 | `PROJECT_ENGINES` 映射表 + 動態載入 |
| 裝飾器模式 | 重試機制 | `@retry` 裝飾器 |

---

## 效能設定

| 操作 | 預設並發數 | 說明 |
|------|-----------|------|
| 下載校驗 | 15 執行緒 | 啟動時完整雲端同步 |
| 刪除操作 | 1 執行緒 | 避免 API 衝突 |
| 上傳操作 | 3 執行緒 | 平衡速度與穩定性 |

防抖延遲：檔案變更後 10 秒才觸發同步，避免頻繁操作。

---

## 安全性

- API Token 使用環境變數（`${CONFLUENCE_TOKEN}`），不得硬寫在配置文件
- 配置文件（含真實 `page_id`、`email`、路徑）列入 `.gitignore`，不提交版本控制
- 日誌檔案含本機路徑，同樣列入 `.gitignore`

---

## 監控與日誌

日誌同時輸出至終端與 `logs/專案名稱_YYYYMMDD.log`。

| 級別 | 用途 |
|------|------|
| INFO | 正常操作流程 |
| WARNING | 可恢復的異常（如驗證器配置缺失） |
| ERROR | 嚴重錯誤（如 API 失敗、頁面渲染錯誤） |
