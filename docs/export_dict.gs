/**
 * export_dict.gs
 * Google Sheets Apps Script — 匯出命名字典為 game_dict.yaml
 *
 * 使用方式：
 *   1. 在 Google Sheets 開啟「擴充功能 > Apps Script」
 *   2. 貼上此程式碼
 *   3. 執行 exportDict()
 *   4. 從彈出視窗複製輸出內容，覆蓋專案內的 config/game_dict.yaml
 *
 * 對應工作表：
 *   - 參數庫/字典：sceneModule(A) / type(C) / named(E) / state(G) / bitmapFont(I) / language(J)
 *   - 禁詞清單：category(A) / forbidden_word(B)
 */

function exportDict() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // ── 讀取參數庫/字典 ──────────────────────────────────────
  const dictSheet = ss.getSheetByName('參數庫/字典');
  const dictData  = dictSheet.getDataRange().getValues();

  const sceneModule  = [];
  const type_        = [];
  const named        = [];
  const state        = [];
  const bitmapFont   = [];
  const language     = [];

  // 第 1 列是標題，從第 2 列（index 1）開始
  for (let i = 1; i < dictData.length; i++) {
    const row = dictData[i];
    if (row[0])  sceneModule.push(String(row[0]).trim());   // A: sceneModule
    if (row[2])  type_.push(String(row[2]).trim());         // C: type
    if (row[4])  named.push(String(row[4]).trim());         // E: named
    if (row[6])  state.push(String(row[6]).trim());         // G: state
    if (row[8] !== '' && row[8] !== null && row[8] !== undefined) {
      // I: bitmapFont（數字會是 number 型別，需轉字串並去小數點）
      let v = row[8];
      if (typeof v === 'number') v = String(Math.round(v));
      else v = String(v).trim();
      if (v) bitmapFont.push(v);
    }
    // J: language（從第 3 列開始，index 2，對應試算表 J3:J1000）
    if (i >= 2 && row[9]) language.push(String(row[9]).trim());
  }

  // Emptyoptions = K2（index 1, col 10）
  const emptyOption = dictData[1][10] ? String(dictData[1][10]).trim() : '';

  // ── 讀取禁詞清單 ──────────────────────────────────────────
  const forbiddenSheet = ss.getSheetByName('禁詞清單');
  const forbiddenData  = forbiddenSheet.getDataRange().getValues();
  const forbiddenWords = [];

  for (let i = 1; i < forbiddenData.length; i++) {
    const word = forbiddenData[i][1];
    if (word && typeof word === 'string') {
      forbiddenWords.push(word.trim());
    }
  }

  // ── 產生 yaml 內容 ────────────────────────────────────────
  const lines = [];

  lines.push('# game_dict.yaml');
  lines.push('# 命名規範字典 — 由 Google Sheets 匯出，請勿手動編輯');
  lines.push(`# 匯出時間：${new Date().toLocaleString('zh-TW')}`);
  lines.push('');
  lines.push(`empty_option: "${emptyOption}"`);
  lines.push('');

  lines.push('scene_module:');
  sceneModule.forEach(v => lines.push(`  - ${v}`));
  lines.push('');

  lines.push('type:');
  type_.forEach(v => lines.push(`  - ${v}`));
  lines.push('');

  lines.push('named:');
  named.forEach(v => lines.push(`  - ${v}`));
  lines.push('');

  lines.push('state:');
  state.forEach(v => lines.push(`  - ${v}`));
  lines.push('');

  lines.push('language:');
  language.forEach(v => lines.push(`  - ${v}`));
  lines.push('');

  lines.push('bitmap_font:');
  bitmapFont.forEach(v => {
    // 數字與特殊符號加引號
    const needsQuote = /^[0-9$₽¥₩€฿৳₫₺]/.test(v);
    lines.push(needsQuote ? `  - "${v}"` : `  - ${v}`);
  });
  lines.push('');

  lines.push('forbidden_words:');
  forbiddenWords.forEach(v => lines.push(`  - ${v}`));

  // ── 顯示結果 ──────────────────────────────────────────────
  const output = lines.join('\n');

  // 用 UI 彈窗顯示（方便複製）
  const ui = SpreadsheetApp.getUi();
  const htmlOutput = HtmlService
    .createHtmlOutput(
      `<style>
        textarea { width:100%; height:400px; font-family:monospace; font-size:12px; }
        p { font-size:13px; color:#555; }
      </style>
      <p>複製以下內容，覆蓋專案內的 <code>config/game_dict.yaml</code></p>
      <textarea>${output}</textarea>`
    )
    .setWidth(700)
    .setHeight(520);

  ui.showModalDialog(htmlOutput, '匯出 game_dict.yaml');
}
