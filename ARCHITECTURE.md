# 系統架構說明

## 概覽

Confluence Sync System 是一個模組化、可擴展的資源同步系統，採用插件式架構設計，支援多專案管理。

## 核心設計理念

### 1. 關注點分離（Separation of Concerns）

- **核心引擎（core/）**: 處理通用的同步邏輯
- **專案實現（projects/）**: 處理專案特定的業務邏輯
- **工具模組（utils/）**: 提供可重用的工具函數

### 2. 依賴倒置（Dependency Inversion）

- 核心引擎定義抽象介面（`BaseSyncEngine`）
- 具體專案實現繼承並實作介面
- 高層模組不依賴低層模組，兩者都依賴抽象

### 3. 開放封閉原則（Open-Closed Principle）

- 對擴展開放：新增專案只需實現介面
- 對修改封閉：新增功能不需修改核心代碼

## 架構圖

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                            │
│                   (應用程式入口)                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ├─ 載入配置 (ConfigLoader)
                     ├─ 初始化日誌 (SyncLogger)
                     ├─ 建立客戶端 (ConfluenceClient)
                     ├─ 建立狀態管理 (StateManager)
                     └─ 選擇專案引擎
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
┌───────▼────────┐                    ┌────────▼────────┐
│ BaseSyncEngine │◄───────────────────┤ ProjectEngine   │
│   (抽象基類)    │                    │ (具體實現)       │
└────────────────┘                    └─────────────────┘
        │                                       │
        ├─ run_sync()                          ├─ classify_assets()
        ├─ _full_cloud_sync()                  ├─ build_page_content()
        ├─ _scan_local_files()                 └─ _update_history_only()
        ├─ _calculate_diff()
        ├─ _execute_operations()
        └─ _update_page()
```

## 模組說明

### core/ - 核心模組

#### sync_engine.py
- `BaseSyncEngine`: 同步引擎抽象基類
- `SyncDiff`: 同步差異資料結構
- 實現完整的同步流程邏輯

**核心流程：**
1. 取得遠端狀態
2. 掃描本地檔案
3. 計算差異
4. 執行物理操作（刪除、上傳）
5. 更新頁面內容
6. 儲存狀態

#### confluence_client.py
- 封裝所有 Confluence REST API 操作
- 提供重試機制
- 統一錯誤處理

**主要方法：**
- `get_page_content()`: 取得頁面內容
- `update_page_content()`: 更新頁面
- `get_all_attachments()`: 取得所有附件
- `download_attachment()`: 下載附件
- `delete_attachment()`: 刪除附件
- `upload_attachment()`: 上傳附件

#### state_manager.py
- 統一管理遠端狀態快取和版本歷史
- 提供持久化功能

**主要功能：**
- 快取管理（remote_state）
- 歷史記錄管理（history）
- 自動載入與儲存

#### hash_calculator.py
- 提供 MD5 哈希計算
- 支援多種輸入格式

#### file_monitor.py
- 監聽檔案系統變更
- 防抖處理（debounce）

### projects/ - 專案模組

每個專案包含三個核心組件：

#### classifier.py
負責資源分類邏輯

**範例：SlotGameClassifier**
```python
def classify(self, asset) -> Tuple[str, Optional[str]]:
    # 返回 (分類名稱, 群組鍵)
    pass

def organize_assets(self, files) -> Dict[str, Any]:
    # 組織所有資源到分類結構
    pass
```

#### page_builder.py
負責生成 Confluence XHTML

**範例：SlotGamePageBuilder**
```python
def assemble(self, categories, history) -> str:
    # 組裝完整頁面內容
    pass

def _generate_history_table(self, history) -> str:
    # 生成歷史表格
    pass
```

#### sync_engine.py
整合分類器和頁面建構器

**範例：SlotGameSyncEngine**
```python
class SlotGameSyncEngine(BaseSyncEngine):
    def classify_assets(self, files):
        return self.classifier.organize_assets(files)
    
    def build_page_content(self, categories, history):
        return self.page_builder.assemble(categories, history)
```

### utils/ - 工具模組

#### logger.py
統一日誌系統，支援：
- 終端彩色輸出
- 檔案持久化
- 圖示化日誌

#### retry.py
重試裝飾器，提供：
- 指數退避
- 可配置重試次數
- 異常過濾

#### config_loader.py
配置載入器，支援：
- YAML 格式
- 環境變數替換
- 配置驗證

## 資料流

### 啟動同步流程

```
1. 載入配置
   ↓
2. 初始化組件
   ├─ Logger
   ├─ ConfluenceClient
   ├─ StateManager
   └─ SyncEngine
   ↓
3. 執行全量雲端同步
   ├─ 並發下載所有附件
   ├─ 計算哈希值
   └─ 建立遠端狀態快照
   ↓
4. 掃描本地檔案
   ├─ 遞迴掃描目標資料夾
   ├─ 計算本地檔案哈希
   └─ 建立本地狀態快照
   ↓
5. 計算差異
   ├─ to_add (新增)
   ├─ to_update (更新)
   └─ to_delete (刪除)
   ↓
6. 執行物理操作
   ├─ 並發刪除雲端冗餘
   └─ 並發上傳本地變更
   ↓
7. 更新頁面內容
   ├─ 分類資源
   ├─ 生成 XHTML
   └─ 推送到 Confluence
   ↓
8. 儲存狀態
   └─ 寫入快取和歷史
```

### 監聽模式流程

```
1. 執行啟動同步
   ↓
2. 啟動檔案監聽器
   ↓
3. 偵測檔案變更
   ├─ 防抖處理 (10秒)
   └─ 過濾檔案類型
   ↓
4. 觸發增量同步
   ├─ 使用快取的遠端狀態
   ├─ 重新掃描本地檔案
   └─ 計算差異並同步
   ↓
5. 回到步驟 3 (循環)
```

## 擴展指南

### 新增專案類型

假設要新增 `card_game` 專案：

1. **創建專案目錄**
```bash
mkdir -p projects/card_game
```

2. **實現分類器**
```python
# projects/card_game/classifier.py
class CardGameClassifier:
    def classify(self, asset):
        # 實現你的分類邏輯
        pass
    
    def organize_assets(self, files):
        # 實現資源組織邏輯
        pass
```

3. **實現頁面建構器**
```python
# projects/card_game/page_builder.py
class CardGamePageBuilder:
    def assemble(self, categories, history):
        # 實現頁面生成邏輯
        pass
```

4. **實現同步引擎**
```python
# projects/card_game/sync_engine.py
from core import BaseSyncEngine

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

5. **註冊專案類型**
```python
# main.py
PROJECT_ENGINES = {
    'slot_game': SlotGameSyncEngine,
    'card_game': CardGameSyncEngine,  # 新增這行
}
```

6. **創建配置文件**
```yaml
# config/card_game_project.yaml
project:
  name: "CardGameX"
  type: "card_game"  # 使用新類型
# ... 其他配置
```

完成！現在可以運行：
```bash
python main.py --config config/card_game_project.yaml --mode watch
```

## 設計模式應用

### 1. 策略模式（Strategy Pattern）
- **應用場景**: 專案分類邏輯
- **實現**: 每個專案提供不同的 `Classifier`

### 2. 模板方法模式（Template Method Pattern）
- **應用場景**: 同步流程
- **實現**: `BaseSyncEngine.run_sync()` 定義骨架，子類實現細節

### 3. 工廠模式（Factory Pattern）
- **應用場景**: 專案引擎創建
- **實現**: `PROJECT_ENGINES` 映射表 + 動態載入

### 4. 裝飾器模式（Decorator Pattern）
- **應用場景**: 重試機制
- **實現**: `@retry` 裝飾器

## 效能優化

### 1. 並發處理
- 下載校驗：15 執行緒
- 刪除操作：1 執行緒（避免衝突）
- 上傳操作：3 執行緒

### 2. 快取機制
- 遠端狀態快取：避免重複下載
- 增量同步：只處理變更檔案

### 3. 防抖處理
- 檔案變更觸發：10 秒延遲
- 避免頻繁同步

## 安全性考量

### 1. 敏感資訊保護
- API Token 使用環境變數
- 配置文件不提交到版本控制

### 2. 錯誤處理
- 所有 API 調用都有異常處理
- 重試機制避免偶發性失敗

### 3. 並發安全
- 使用鎖機制防止並發同步
- 狀態檔案原子化寫入

## 監控與日誌

### 日誌級別
- **INFO**: 正常操作流程
- **WARNING**: 可恢復的異常
- **ERROR**: 嚴重錯誤

### 日誌輸出
- 終端：即時顯示
- 檔案：持久化記錄（logs/專案名稱_日期.log）

### 關鍵指標
- 同步耗時
- 檔案變更數量
- API 調用次數
- 失敗率

## 未來擴展方向

1. **增強監控**
   - Prometheus 指標匯出
   - Grafana 儀表板

2. **通知系統**
   - Slack 通知
   - Email 通知
   - Webhook 支援

3. **多雲支援**
   - Google Drive
   - OneDrive
   - S3

4. **Web 管理介面**
   - 配置管理
   - 即時監控
   - 歷史查詢

5. **非同步處理**
   - 改用 asyncio
   - 提升並發效能
