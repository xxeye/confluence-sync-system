# 快速開始指南

5 分鐘完成第一次同步。

---

## 前置需求

- Python 3.8+
- Confluence Cloud 帳號與 API Token
- 目標頁面的編輯權限

---

## 步驟一：安裝

```bash
pip install -r requirements.txt
```

---

## 步驟二：取得 Confluence 資訊

需要以下四項資訊，填入配置文件：

| 欄位 | 取得方式 |
|------|---------|
| `url` | 你的 Confluence 網址，如 `https://yourteam.atlassian.net` |
| `page_id` | 打開目標頁面 → 網址列的數字 ID |
| `email` | 登入 Confluence 的 Email |
| `api_token` | [Atlassian 帳號設定](https://id.atlassian.com/manage-profile/security/api-tokens) → 建立 API Token |
| `user_account_id` | Confluence 個人資料頁網址中的 `accountId` 參數 |

---

## 步驟三：設定環境變數

```bash
# Windows
set CONFLUENCE_TOKEN=your_api_token_here

# macOS / Linux
export CONFLUENCE_TOKEN=your_api_token_here
```

---

## 步驟四：建立配置文件

```bash
cp config/base.yaml config/my_project.yaml
```

編輯 `config/my_project.yaml`，填入你的資訊：

```yaml
project:
  name: "MyProject"
  type: "slot_game"

confluence:
  url: "https://yourteam.atlassian.net"
  page_id: "123456789"
  email: "you@example.com"
  api_token: "${CONFLUENCE_TOKEN}"
  user_account_id: "YOUR_ACCOUNT_ID"

sync:
  target_folder: "./art_assets"   # 改成你的資料夾路徑
```

---

## 步驟五：建立資料夾並放入圖片

```bash
mkdir art_assets
# 將 .png / .jpg 圖片放入 art_assets/
```

---

## 步驟六：執行

```bash
# 單次同步
python multi_project_manager.py --configs config/my_project.yaml --mode once

# 持續監聽（推薦）
python multi_project_manager.py --configs config/my_project.yaml --mode watch
```

看到 `✅ 同步完成` 即代表成功。

---

## 後續設定（可選）

### 啟用命名驗證器

在配置文件加入：

```yaml
validator:
  enabled: true
  dict_file: "config/game_dict.yaml"
  naming_doc_url: "https://你的規範文件連結"
```

字典文件 `game_dict.yaml` 由 Google Sheets 匯出，使用 `docs/export_dict.gs`。

### 加入圖片說明

在資料夾旁放置 `asset_notes.xlsx`，格式說明請參考 [docs/README.md](docs/README.md)。

配置文件加入：

```yaml
confluence:
  notes_file: "./asset_notes.xlsx"
```

### 多專案同時運行

```bash
# configs.txt 填入多個配置文件路徑
python multi_project_manager.py --config-list configs.txt --mode watch
```

---

## 常見問題

**Q：第一次執行很慢？**
A：首次會下載並校驗所有雲端附件建立快取，之後只處理差異。

**Q：想先確認會做什麼操作再執行？**
A：加上 `--dry-run` 參數，只預覽差異不實際執行。

**Q：不小心刪除了 Confluence 附件怎麼辦？**
A：重新將圖片放回本地資料夾，下次同步會重新上傳。
