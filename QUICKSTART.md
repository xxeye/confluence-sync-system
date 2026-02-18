# 🚀 快速入門指南

恭喜！你已經下載了重構後的 Confluence Sync System v2.0

## 📦 解壓縮

```bash
tar -xzf confluence-sync-system.tar.gz
cd confluence-sync-system
```

## ⚙️ 環境設定

### 1. 安裝 Python 依賴

```bash
# 方法一：使用虛擬環境（建議）
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

pip install -r requirements.txt

# 方法二：直接安裝
pip install -r requirements.txt
```

### 2. 配置專案

```bash
# 複製配置範本
cp config/base.yaml config/my_project.yaml

# 編輯配置文件
vim config/my_project.yaml  # 或使用你喜歡的編輯器
```

**必須修改的配置項：**

```yaml
confluence:
  url: "https://your-domain.atlassian.net"  # 你的 Confluence 網域
  page_id: "123456789"                       # 目標頁面 ID
  email: "your-email@example.com"            # 你的帳號
  api_token: "${CONFLUENCE_TOKEN}"           # API Token（見下方）
  user_account_id: "your-account-id"         # 你的 Account ID

sync:
  target_folder: "./art_assets"              # 要監聽的資料夾
```

### 3. 設定環境變數

```bash
# Linux/Mac
export CONFLUENCE_TOKEN="你的_API_Token"

# Windows (CMD)
set CONFLUENCE_TOKEN=你的_API_Token

# Windows (PowerShell)
$env:CONFLUENCE_TOKEN="你的_API_Token"
```

**如何取得 API Token：**
1. 登入 Atlassian: https://id.atlassian.com/manage-profile/security/api-tokens
2. 點擊「Create API token」
3. 複製生成的 Token

**如何取得 Page ID：**
1. 開啟目標 Confluence 頁面
2. 點擊右上角的「⋯」→「Page Information」
3. 查看網址，ID 在 `pageId=` 後面

**如何取得 Account ID：**
1. 開啟 Confluence 任一頁面
2. 點擊右上角你的頭像 → 「Profile」
3. 查看網址中的 `accountId=` 參數

## 🎯 開始使用

### 快速啟動（使用腳本）

```bash
# 給腳本執行權限
chmod +x start.sh

# 啟動（預設監聽模式）
./start.sh

# 或指定參數
./start.sh --config config/my_project.yaml --mode once
```

### 手動啟動

```bash
# 監聽模式（持續運行，自動同步）
python main.py --config config/my_project.yaml --mode watch

# 單次執行模式（執行一次後結束）
python main.py --config config/my_project.yaml --mode once

# Dry-run 模式（僅預覽變更，不實際執行）
python main.py --config config/my_project.yaml --mode once --dry-run
```

## 📁 準備資源資料夾

```bash
# 創建資源資料夾（與配置中的 target_folder 對應）
mkdir -p art_assets

# 將你的圖片放入資料夾
cp /path/to/your/images/* art_assets/
```

**支援的檔案格式：**
- PNG (.png)
- JPEG (.jpg, .jpeg)

## 🧪 測試

```bash
# 執行所有測試
pytest tests/ -v

# 執行特定測試
pytest tests/test_classifier.py -v

# 查看測試覆蓋率
pytest tests/ --cov=core --cov=projects --cov=utils
```

## 📊 查看日誌

```bash
# 即時查看日誌（監聽模式下）
tail -f logs/專案名稱_20240218.log

# 查看最近的日誌
cat logs/專案名稱_20240218.log
```

## 🔧 常見問題

### Q1: 無法連線到 Confluence

**檢查清單：**
- [ ] Confluence URL 是否正確（包含 `https://`）
- [ ] API Token 是否已設定到環境變數
- [ ] Email 和 Token 是否匹配
- [ ] 網路是否正常

```bash
# 測試連線
curl -u "your-email@example.com:$CONFLUENCE_TOKEN" \
  "https://your-domain.atlassian.net/wiki/rest/api/space"
```

### Q2: 找不到頁面

**檢查清單：**
- [ ] Page ID 是否正確
- [ ] 你的帳號是否有該頁面的編輯權限

### Q3: 上傳失敗

**可能原因：**
- 檔案太大（預設限制 10MB）
- 網路不穩定
- 頁面被鎖定

**解決方法：**
- 等待系統自動重試（最多 3 次）
- 檢查日誌了解詳細錯誤訊息

### Q4: 監聽無反應

**檢查清單：**
- [ ] `target_folder` 路徑是否正確
- [ ] 檔案是否符合 `file_patterns.include` 規則
- [ ] 是否有檔案權限問題

## 🎨 自訂專案類型

如果你的專案不是 Slot Game，需要自訂分類邏輯：

1. 參考 `ARCHITECTURE.md` 的「擴展指南」章節
2. 在 `projects/` 下創建新專案資料夾
3. 實現 `classifier.py`、`page_builder.py`、`sync_engine.py`
4. 在 `main.py` 註冊新專案類型

## 📚 進階使用

### 多專案同時運行

```bash
# 終端 1 - 專案 A
python main.py --config config/project_a.yaml --mode watch

# 終端 2 - 專案 B
python main.py --config config/project_b.yaml --mode watch

# 使用 tmux 或 screen 在背景運行
tmux new -s sync-a "python main.py --config config/project_a.yaml --mode watch"
tmux new -s sync-b "python main.py --config config/project_b.yaml --mode watch"
```

### 定時同步（使用 cron）

```bash
# 編輯 crontab
crontab -e

# 每小時執行一次同步
0 * * * * cd /path/to/confluence-sync-system && python main.py --config config/my_project.yaml --mode once >> logs/cron.log 2>&1
```

### Docker 部署（進階）

```dockerfile
# Dockerfile（自行創建）
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py", "--config", "config/project_a.yaml", "--mode", "watch"]
```

```bash
# 建置映像
docker build -t confluence-sync .

# 運行容器
docker run -d \
  -e CONFLUENCE_TOKEN="your_token" \
  -v $(pwd)/art_assets:/app/art_assets \
  -v $(pwd)/logs:/app/logs \
  --name sync-container \
  confluence-sync
```

## 📞 支援與回饋

如果遇到問題：

1. 查看 `README.md` 的「故障排除」章節
2. 查看 `ARCHITECTURE.md` 了解系統架構
3. 查看 `logs/` 目錄的日誌文件
4. 開啟 GitHub Issue 回報問題

## 🎉 完成！

你已經完成所有設定，現在可以開始使用了！

**下一步：**
- 將你的美術資源放入 `art_assets/` 資料夾
- 運行 `python main.py --config config/my_project.yaml --mode watch`
- 系統會自動監聽並同步到 Confluence

祝使用愉快！ 🚀
