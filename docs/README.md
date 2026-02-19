# asset_notes.xlsx 說明文件使用指南

`asset_notes.xlsx` 是給美術人員填寫的圖片說明對照表。  
程式在同步時會自動讀取此檔案，將說明內容填入 Confluence 頁面對應的欄位。

---

## 檔案位置範例

```
C:/專案/
├── asset_notes.xlsx     ← 說明文件
└── 99/                  ← 監聽資料夾
    └── ...
```

Config 中對應設定：

```yaml
confluence:
  notes_file: "C:/專案/asset_notes.xlsx"
```

---

## 試算表格式

| 欄位 | 說明 |
|------|------|
| **A 欄** | 圖片識別 key（見下方三種填法） |
| **B 欄** | 說明文字，會顯示在 Confluence 頁面的說明欄位 |

- 第一列直接開始填資料，**不需要標題列**
- B 欄留空代表該圖片沒有說明，Confluence 欄位會留白
- A 欄大小寫不影響比對（程式會自動處理）

---

## A 欄的三種填法

### 1. 一般圖片 — 填完整檔名

```
A 欄                    B 欄
main_bg.png             主遊戲背景，1920x1080，含動態光效層
free_bg.png             免費遊戲背景，色調偏金色
loading_logo.png        載入畫面 Logo，需對齊中央
layout_base.png         版型底圖，所有場景共用
```

> **提示**：副檔名可填可不填，`main_bg` 和 `main_bg.png` 都能正確對應。

---

### 2. 多國語系與數字圖片 — 填群組名（不含語系代碼與副檔名）

檔案命名規則為 `{場景}_{類型}_{命名}_{狀態}_{語系/位圖數字}.png`，  
A 欄填前四段組成的群組名，說明會套用到整個語系群組。

```
A 欄                    B 欄
main_btn_start_na          開始按鈕文字，13 種語系
main_txt_win_na            Win 文字，顯示於中獎動畫上方
free_txt_bonus_na          Bonus 字樣，免費遊戲觸發時顯示
loading_txt_loading_na     Loading 提示文字
```

對應的實際檔案範例（這些檔案 **不需要** 個別填寫）：
```
main_btn_start_na_cn.png
main_btn_start_na_en.png
main_btn_start_na_jp.png
...（共 13 個語系）
```

---

## 完整範例

| A 欄 | B 欄 |
|------|------|
| layout_base.png | 版型底圖，所有場景共用基底 |
| main_bg.png | 主遊戲背景，含夜晚燈光氛圍 |
| main_btn_spin.png | Spin 按鈕，點擊後播放旋轉動畫 |
| main_btn_start_na | 開始按鈕多國文字，13 種語系版本 |
| main_nu_win_na | 中獎金額數字組，0–9 共 10 張 |
| free_bg.png | 免費遊戲背景，金色基調 |
| free_txt_bonus_na | Bonus 觸發字樣，多國語系 |
| free_nu_mult_na | 免費遊戲倍率數字，1x–10x |
| loading_logo.png | 載入畫面品牌 Logo |
| loading_txt_loading_na | Loading 提示文字，多國語系 |

---

## 注意事項

- 此檔案由美術人員**手動維護**，程式只負責讀取，不會自動新增或刪除列
- 當新增圖片時，請同步在此檔案補充說明；刪除圖片後對應列可保留或刪除，不影響程式運作
- 若此檔案不存在或路徑設定錯誤，程式會略過說明功能，**不影響正常同步流程**
- 同一個 key 在 A 欄重複出現時，以最後一筆為準