# 🎯 多專案管理指南

本指南說明如何同時監聽和管理多個 Confluence 專案。

## 📋 目錄

- [方案選擇](#方案選擇)
- [方案一：多專案管理器（推薦）](#方案一多專案管理器推薦)
- [方案二：多終端分別運行](#方案二多終端分別運行)
- [方案三：Docker Compose](#方案三docker-compose)
- [方案四：Systemd 服務](#方案四systemd-服務)
- [效能考量](#效能考量)
- [故障排除](#故障排除)

---

## 方案選擇

| 方案 | 適用場景 | 優點 | 缺點 |
|------|---------|------|------|
| 多專案管理器 | 3-10 個專案 | 統一管理、日誌清晰 | 需要一個終端 |
| 多終端 | 2-3 個專案 | 簡單直接、獨立控制 | 終端多、管理麻煩 |
| Docker Compose | 生產環境 | 隔離性好、易部署 | 需要 Docker |
| Systemd 服務 | Linux 伺服器 | 開機自啟、穩定運行 | 僅限 Linux |

---

## 方案一：多專案管理器（推薦）

### 🎯 特點

- ✅ 單一程式管理多個專案
- ✅ 統一的日誌輸出（區分專案）
- ✅ 支援循序或並行同步
- ✅ 獨立的狀態文件（避免衝突）

### 📝 步驟

#### 1. 準備配置文件

為每個專案創建獨立的配置文件：

```bash
# 專案 A
cp config/base.yaml config/project_a.yaml
# 編輯 project_a.yaml，設定 page_id、target_folder 等

# 專案 B
cp config/base.yaml config/project_b.yaml
# 編輯 project_b.yaml，使用不同的 page_id 和 target_folder

# 專案 C
cp config/base.yaml config/project_c.yaml
```

**重要：每個專案必須有不同的：**
- `confluence.page_id` - 不同的 Confluence 頁面
- `sync.target_folder` - 不同的本地資料夾

#### 2. 創建專案資料夾

```bash
mkdir -p art_assets_a art_assets_b art_assets_c
```

#### 3. 方式 A：使用配置清單文件

創建 `configs.txt`：

```
# 多專案配置清單
config/project_a.yaml
config/project_b.yaml
config/project_c.yaml
```

執行：

```bash
# 監聽模式
python multi_project_manager.py --config-list configs.txt --mode watch

# 單次同步（循序）
python multi_project_manager.py --config-list configs.txt --mode once

# 單次同步（並行，更快）
python multi_project_manager.py --config-list configs.txt --mode once --parallel
```

#### 4. 方式 B：直接指定配置文件

```bash
# 監聽模式
python multi_project_manager.py \
  --configs config/project_a.yaml config/project_b.yaml config/project_c.yaml \
  --mode watch

# 使用萬用字元
python multi_project_manager.py \
  --configs config/project_*.yaml \
  --mode watch
```

#### 5. 使用快速啟動腳本

```bash
# 給腳本執行權限
chmod +x start_multi.sh

# 啟動（會讀取 configs.txt）
./start_multi.sh watch

# 單次同步
./start_multi.sh once

# 並行同步
./start_multi.sh once --parallel
```

### 📊 運行示例

```
🚀 開始循序同步 3 個專案...
============================================================
✅ [P1] 已載入: SlotGameA
✅ [P2] 已載入: SlotGameB
✅ [P3] 已載入: SlotGameC
============================================================
[10:30:15] 🏁 [P1] 執行初始同步...
[10:30:16] 📡 [P1] 連線雲端取得頁面結構與歷史紀錄...
[10:30:18] ✅ [P1] Wiki 推送完成 (Ver: 42)
------------------------------------------------------------
[10:30:19] 🏁 [P2] 執行初始同步...
...
============================================================
✅ 完成！成功: 3/3

📡 啟動監聽器...
✅ [P1] 監控已啟動
✅ [P2] 監控已啟動
✅ [P3] 監控已啟動

✅ 所有專案監聽已啟動
📝 日誌位置: logs/
⌨️  按 Ctrl+C 停止所有監聽
```

### 📁 檔案結構

```
confluence-sync-system/
├── config/
│   ├── project_a.yaml      # 專案 A 配置
│   ├── project_b.yaml      # 專案 B 配置
│   └── project_c.yaml      # 專案 C 配置
├── configs.txt             # 配置清單
├── art_assets_a/           # 專案 A 資源
├── art_assets_b/           # 專案 B 資源
├── art_assets_c/           # 專案 C 資源
├── logs/
│   ├── P1_SlotGameA_20240218.log
│   ├── P2_SlotGameB_20240218.log
│   └── P3_SlotGameC_20240218.log
├── P1_.sync_cache.json     # 專案 A 狀態
├── P1_version_history.json
├── P2_.sync_cache.json     # 專案 B 狀態
├── P2_version_history.json
├── P3_.sync_cache.json     # 專案 C 狀態
└── P3_version_history.json
```

---

## 方案二：多終端分別運行

### 🎯 特點

- ✅ 最簡單直接
- ✅ 每個專案獨立控制
- ❌ 需要開多個終端視窗

### 📝 步驟

```bash
# 終端 1 - 專案 A
python main.py --config config/project_a.yaml --mode watch

# 終端 2 - 專案 B
python main.py --config config/project_b.yaml --mode watch

# 終端 3 - 專案 C
python main.py --config config/project_c.yaml --mode watch
```

### 使用 tmux 管理（推薦）

```bash
# 安裝 tmux
sudo apt install tmux  # Ubuntu/Debian
brew install tmux      # macOS

# 啟動專案 A
tmux new -s sync-a -d "cd /path/to/project && python main.py --config config/project_a.yaml --mode watch"

# 啟動專案 B
tmux new -s sync-b -d "cd /path/to/project && python main.py --config config/project_b.yaml --mode watch"

# 啟動專案 C
tmux new -s sync-c -d "cd /path/to/project && python main.py --config config/project_c.yaml --mode watch"

# 查看所有會話
tmux ls

# 連接到某個會話查看日誌
tmux attach -t sync-a

# 離開會話（不停止）
按 Ctrl+B 然後按 D

# 停止某個專案
tmux kill-session -t sync-a
```

---

## 方案三：Docker Compose

### 🎯 特點

- ✅ 容器隔離，互不影響
- ✅ 易於部署和擴展
- ✅ 適合生產環境

### 📝 步驟

#### 1. 使用提供的 docker-compose.yml

```bash
# 方式 A：每個專案獨立容器
docker-compose up -d sync-project-a sync-project-b

# 方式 B：使用多專案管理器容器（推薦）
docker-compose up -d sync-multi
```

#### 2. 查看日誌

```bash
# 查看所有容器日誌
docker-compose logs -f

# 查看特定容器日誌
docker-compose logs -f sync-multi

# 查看應用程式日誌（在 logs/ 目錄）
tail -f logs/P1_SlotGameA_20240218.log
```

#### 3. 停止服務

```bash
# 停止所有容器
docker-compose down

# 停止特定容器
docker-compose stop sync-project-a
```

#### 4. 自訂 docker-compose.yml

```yaml
version: '3.8'

services:
  # 新增更多專案
  sync-project-d:
    build: .
    container_name: confluence-sync-project-d
    environment:
      - CONFLUENCE_TOKEN=${CONFLUENCE_TOKEN}
    volumes:
      - ./config/project_d.yaml:/app/config/project.yaml
      - ./art_assets_d:/app/art_assets
      - ./logs:/app/logs
    command: python main.py --config config/project.yaml --mode watch
    restart: unless-stopped
```

---

## 方案四：Systemd 服務

### 🎯 特點

- ✅ 開機自動啟動
- ✅ 崩潰自動重啟
- ✅ 適合 Linux 伺服器長期運行
- ❌ 僅限 Linux 系統

### 📝 步驟

#### 1. 編輯服務文件

```bash
sudo vim /etc/systemd/system/confluence-sync-multi.service
```

修改以下內容：

```ini
[Service]
User=your-username                                    # 你的使用者名稱
WorkingDirectory=/path/to/confluence-sync-system      # 專案路徑
Environment="CONFLUENCE_TOKEN=your_token_here"        # API Token
Environment="PATH=/path/to/venv/bin:..."              # Python 虛擬環境路徑
ExecStart=/path/to/venv/bin/python multi_project_manager.py --config-list configs.txt --mode watch
```

#### 2. 創建日誌目錄

```bash
sudo mkdir -p /var/log/confluence-sync
sudo chown your-username:your-group /var/log/confluence-sync
```

#### 3. 啟動服務

```bash
# 重新載入 systemd
sudo systemctl daemon-reload

# 啟用服務（開機自啟）
sudo systemctl enable confluence-sync-multi

# 啟動服務
sudo systemctl start confluence-sync-multi

# 查看狀態
sudo systemctl status confluence-sync-multi
```

#### 4. 管理服務

```bash
# 停止服務
sudo systemctl stop confluence-sync-multi

# 重啟服務
sudo systemctl restart confluence-sync-multi

# 查看日誌
sudo journalctl -u confluence-sync-multi -f

# 查看應用程式日誌
tail -f logs/P1_SlotGameA_20240218.log
```

#### 5. 多個服務實例

如果你想為每個專案創建獨立的服務：

```bash
# 為專案 A 創建服務
sudo cp confluence-sync-multi.service /etc/systemd/system/confluence-sync-a.service
sudo vim /etc/systemd/system/confluence-sync-a.service
# 修改 ExecStart: python main.py --config config/project_a.yaml --mode watch

# 為專案 B 創建服務
sudo cp confluence-sync-multi.service /etc/systemd/system/confluence-sync-b.service
# 修改 ExecStart 為專案 B 的配置

# 啟用並啟動
sudo systemctl enable confluence-sync-a confluence-sync-b
sudo systemctl start confluence-sync-a confluence-sync-b
```

---

## 效能考量

### 並發設定

每個專案都有獨立的並發設定，位於配置文件中：

```yaml
sync:
  max_workers:
    download: 15  # 下載校驗執行緒數
    delete: 1     # 刪除執行緒數（建議 1）
    upload: 3     # 上傳執行緒數
```

### 資源使用

假設有 5 個專案同時運行：

| 資源 | 單專案 | 5 專案總計 | 建議配置 |
|------|--------|-----------|---------|
| CPU | 10-20% | 50-100% | 4 核心 |
| 記憶體 | 100MB | 500MB | 2GB |
| 網路 | 1-5 Mbps | 5-25 Mbps | 100 Mbps |

### 優化建議

1. **並行初始同步**（啟動快 3-5 倍）

```bash
# 使用 --parallel 選項
python multi_project_manager.py \
  --config-list configs.txt \
  --mode once \
  --parallel
```

2. **減少並發數**（降低資源使用）

```yaml
sync:
  max_workers:
    download: 10  # 從 15 降到 10
    upload: 2     # 從 3 降到 2
```

3. **增加防抖延遲**（減少觸發頻率）

```yaml
sync:
  watch_delay: 30  # 從 10 秒增加到 30 秒
```

---

## 故障排除

### Q1: 多個專案衝突

**症狀：** 專案之間互相干擾，狀態混亂

**解決方法：**

檢查每個專案的配置是否有以下問題：

```yaml
# ❌ 錯誤：多個專案使用相同的 page_id
confluence:
  page_id: "123456"  # 專案 A
  page_id: "123456"  # 專案 B（相同！）

# ✅ 正確：每個專案使用不同的 page_id
confluence:
  page_id: "123456"  # 專案 A
  page_id: "789012"  # 專案 B

# ❌ 錯誤：多個專案使用相同的資料夾
sync:
  target_folder: "./art_assets"  # 專案 A
  target_folder: "./art_assets"  # 專案 B（相同！）

# ✅ 正確：每個專案使用不同的資料夾
sync:
  target_folder: "./art_assets_a"  # 專案 A
  target_folder: "./art_assets_b"  # 專案 B
```

### Q2: 某個專案失敗導致全部停止

**症狀：** 一個專案出錯，所有專案都停止運行

**解決方法：**

使用多終端或 Docker Compose 方式，讓每個專案獨立運行。

```bash
# 方式 1：分別啟動
tmux new -s sync-a -d "python main.py --config config/project_a.yaml --mode watch"
tmux new -s sync-b -d "python main.py --config config/project_b.yaml --mode watch"

# 方式 2：Docker Compose
docker-compose up -d sync-project-a sync-project-b
```

### Q3: 記憶體或 CPU 使用過高

**症狀：** 系統資源不足

**解決方法：**

1. 減少並發執行緒數
2. 分批啟動專案
3. 使用排程執行（如每小時同步一次）

```bash
# Crontab 排程執行
# 每小時執行一次全量同步
0 * * * * cd /path/to/project && python multi_project_manager.py --config-list configs.txt --mode once --parallel
```

### Q4: 日誌太多難以查看

**症狀：** 多個專案的日誌混在一起

**解決方法：**

1. 查看專案專屬日誌文件

```bash
# 每個專案有獨立的日誌文件
tail -f logs/P1_SlotGameA_20240218.log
tail -f logs/P2_SlotGameB_20240218.log
```

2. 使用 grep 過濾

```bash
# 只看專案 A 的日誌
tail -f logs/*.log | grep '\[P1\]'
```

---

## 總結

| 方案 | 推薦指數 | 適用場景 |
|------|---------|---------|
| 多專案管理器 | ⭐⭐⭐⭐⭐ | 3-10 個專案，開發/測試環境 |
| 多終端 (tmux) | ⭐⭐⭐⭐ | 2-5 個專案，需要獨立控制 |
| Docker Compose | ⭐⭐⭐⭐⭐ | 生產環境，容器化部署 |
| Systemd 服務 | ⭐⭐⭐⭐⭐ | Linux 伺服器，長期穩定運行 |

**最佳實踐建議：**

1. **開發測試階段**：使用多專案管理器或 tmux
2. **生產環境**：使用 Docker Compose 或 Systemd
3. **5 個以下專案**：多專案管理器
4. **5 個以上專案**：Docker Compose + 容器編排

有任何問題歡迎查看日誌或提 Issue！🚀
