"""
Slot Game 頁面建構器 — 生成 Confluence XHTML 頁面內容

警告渲染：
  assemble() 接收可選的 FilenameValidator 實例，
  渲染一般表格時對每個 asset 呼叫 validator.validate()，
  有警告則在檔名欄橘底顯示，說明欄正常顯示 notes。
  validator=None（未啟用）時完全不影響渲染邏輯。
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from urllib.parse import unquote, urlparse, parse_qs

if TYPE_CHECKING:
    from .validator import FilenameValidator


# ── 全域欄數設定 ──────────────────────────────────────────────
LAYOUT_COLS = 8
MULTI_COLS  = 13
NU_COLS     = 16

# ── 警告樣式（橘底，統一顯示在檔名下方）──────────────────────
_WARN_STYLE = "background:#fff3e0; color:#e65100; font-size:11px; font-weight:bold;"


def _escape_xml(text: str) -> str:
    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;')
    )


def _stem(filename: str) -> str:
    from pathlib import Path
    return Path(filename).stem


class SlotGamePageBuilder:

    @staticmethod
    def get_ac_image_tag(filename: str, img_w: int, target_max: int) -> str:
        final_w   = min(img_w, target_max)
        safe_name = _escape_xml(filename)
        return (
            f'<ac:image ac:width="{final_w}">'
            f'<ri:attachment ri:filename="{safe_name}" />'
            f'</ac:image>'
        )

    # ── 頁面組裝入口 ──────────────────────────────────────────
    def assemble(
        self,
        categories: Dict[str, Any],
        history: List[Dict[str, str]],
        jira_filter_url: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None,
        validator: Optional['FilenameValidator'] = None,
    ) -> str:
        """
        組裝完整頁面內容。

        Args:
            categories:      分類後的資源字典
            history:         更新歷史列表
            jira_filter_url: Jira filter URL（可選）
            notes:           圖片說明對照表 {key: note}（可選）
            validator:       FilenameValidator 實例（可選，None 代表停用驗證）
        """
        if notes is None:
            notes = {}

        body = ''
        body += self._generate_history_table(history)
        body += self._generate_top_toc()

        if jira_filter_url:
            body += self._generate_jira_block(jira_filter_url)

        body += self._generate_layout_grid(categories['layout'], notes)

        body += self._generate_normal_table(
            '🎰 2. 主遊戲 (Main Game) 素材列表',
            categories['main'], notes, validator,
        )
        body += self._generate_multi_grid(
            '🌐 主遊戲—多國語系版',
            categories['multi_main'], notes,
        )
        body += self._generate_nu_grid(
            '🔢 主遊戲—數字組 (NU)',
            categories['nu_main'], notes,
        )

        body += self._generate_normal_table(
            '🎁 3. 免費遊戲 (Free Game) 素材列表',
            categories['free'], notes, validator,
        )
        body += self._generate_multi_grid(
            '🌐 免費遊戲—多國語系版',
            categories['multi_free'], notes,
        )
        body += self._generate_nu_grid(
            '🔢 免費遊戲—數字組 (NU)',
            categories['nu_free'], notes,
        )

        body += self._generate_normal_table(
            '⏳ 4. 載入畫面 (Loading) 素材列表',
            categories['loading'], notes, validator,
        )
        body += self._generate_multi_grid(
            '🌐 載入畫面—多國語系版',
            categories['multi_loading'], notes,
        )
        body += self._generate_nu_grid(
            '🔢 載入畫面—數字組 (NU)',
            categories['nu_loading'], notes,
        )

        return body

    # ── TOC ──────────────────────────────────────────────────
    @staticmethod
    def _generate_top_toc() -> str:
        return (
            '<p>'
            '<ac:structured-macro ac:name="toc">'
            '<ac:parameter ac:name="minLevel">2</ac:parameter>'
            '<ac:parameter ac:name="maxLevel">6</ac:parameter>'
            '<ac:parameter ac:name="printable">false</ac:parameter>'
            '</ac:structured-macro>'
            '</p><hr />'
        )

    @staticmethod
    def _generate_section_toc() -> str:
        return (
            '<hr /><p>'
            '<ac:structured-macro ac:name="toc">'
            '<ac:parameter ac:name="minLevel">2</ac:parameter>'
            '<ac:parameter ac:name="maxLevel">2</ac:parameter>'
            '<ac:parameter ac:name="type">flat</ac:parameter>'
            '<ac:parameter ac:name="separator">brackets</ac:parameter>'
            '<ac:parameter ac:name="printable">false</ac:parameter>'
            '</ac:structured-macro>'
            '</p>'
        )

    # ── Jira ─────────────────────────────────────────────────
    @staticmethod
    def _parse_jira_params(jira_url: str) -> Dict[str, str]:
        params = parse_qs(urlparse(jira_url).query)
        jql    = params.get('jql', [])
        fid    = params.get('filter', [])
        if jql:
            return {'type': 'jqlQuery', 'value': unquote(jql[0])}
        if fid and fid[0].lstrip('-').isdigit() and int(fid[0]) > 0:
            return {'type': 'filterId', 'value': fid[0]}
        return {'type': 'jqlQuery', 'value': jira_url}

    @staticmethod
    def _generate_jira_block(url: str) -> str:
        p       = SlotGamePageBuilder._parse_jira_params(url)
        columns = 'issuetype,key,summary,assignee,reporter,priority,status,resolution,created,updated,due'
        return (
            '<h2>📋 0. Jira 任務清單</h2>'
            '<ac:structured-macro ac:name="jira">'
            f'<ac:parameter ac:name="{p["type"]}">{p["value"]}</ac:parameter>'
            f'<ac:parameter ac:name="columns">{columns}</ac:parameter>'
            '<ac:parameter ac:name="maximumIssues">50</ac:parameter>'
            '</ac:structured-macro>'
        )

    # ── 更新歷史 ──────────────────────────────────────────────
    @staticmethod
    def _generate_history_table(history: List[Dict[str, str]]) -> str:
        if not history:
            return ''
        xhtml = (
            '<h2>📝 更新紀錄</h2>'
            '<table><thead><tr>'
            "<th style='background:#f1f3f5;'>日期</th>"
            "<th style='background:#f1f3f5;'>內容</th>"
            "<th style='background:#f1f3f5;'>更新者</th>"
            '</tr></thead><tbody>'
        )
        for h in history:
            user = f'<ac:link><ri:user ri:account-id="{h["user_id"]}" /></ac:link>'
            xhtml += (
                f'<tr>'
                f'<td>{h["date"]}</td>'
                f'<td>{_escape_xml(h["log"])}</td>'
                f'<td>{user}</td>'
                f'</tr>'
            )
        return xhtml + '</tbody></table>'

    # ── Layout 格狀排列（8 欄）────────────────────────────────
    def _generate_layout_grid(
        self,
        assets: List[Dict[str, Any]],
        notes: Dict[str, str],
    ) -> str:
        if not assets:
            return ''

        cols  = LAYOUT_COLS
        xhtml = '<h2>🖼 1. Layout 版型排列</h2>' + self._generate_section_toc() + '<table><tbody>'

        for i in range(0, len(sorted(assets, key=lambda x: x['name'])), cols):
            chunk = sorted(assets, key=lambda x: x['name'])[i:i + cols]
            pad   = cols - len(chunk)

            xhtml += '<tr>'
            for a in chunk:
                xhtml += f"<td style='background:#f1f3f5;font-size:11px;font-weight:bold;'>{_escape_xml(a['name'])}</td>"
            xhtml += '<td></td>' * pad + '</tr>'

            xhtml += '<tr>'
            for a in chunk:
                xhtml += f"<td>{self.get_ac_image_tag(a['name'], a['orig_w'], 200)}</td>"
            xhtml += '<td></td>' * pad + '</tr>'

            has_notes = any(notes.get(a['name'], notes.get(_stem(a['name']), '')) for a in chunk)
            if has_notes:
                xhtml += '<tr>'
                for a in chunk:
                    note = notes.get(a['name'], notes.get(_stem(a['name']), ''))
                    xhtml += f"<td style='font-size:11px;color:#555;'>{_escape_xml(note)}</td>"
                xhtml += '<td></td>' * pad + '</tr>'

        return xhtml + '</tbody></table>'

    # ── 一般圖片表格 ──────────────────────────────────────────
    def _generate_normal_table(
        self,
        title: str,
        assets: List[Dict[str, Any]],
        notes: Dict[str, str],
        validator: Optional['FilenameValidator'] = None,
    ) -> str:
        """
        一般圖片表格：圖片 / 檔名 / 尺寸 / 說明

        validator 不為 None 時，對每個 asset 執行驗證：
          有警告 → 檔名欄橘底，警告文字顯示在檔名下方
          說明欄永遠正常顯示 notes（不受警告影響）
        """
        if not assets:
            return ''

        xhtml = (
            f'<h2>{title}</h2>'
            + self._generate_section_toc()
            + '<table><thead>'
            '<tr><th>圖片</th><th>檔名</th><th>尺寸</th><th>說明</th></tr>'
            '</thead><tbody>'
        )

        for asset in sorted(assets, key=lambda x: x['name']):
            note    = notes.get(asset['name'], notes.get(_stem(asset['name']), ''))
            warning = validator.validate(asset['name']) if validator else None

            if warning:
                name_cell = (
                    f"<td style='{_WARN_STYLE}'>"
                    f"{_escape_xml(asset['name'])}<br/>"
                    f"<span style='font-size:10px;font-weight:normal;'>{_escape_xml(warning)}</span>"
                    f'</td>'
                )
            else:
                name_cell = f"<td>{_escape_xml(asset['name'])}</td>"

            xhtml += (
                f'<tr>'
                f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 120)}</td>"
                f'{name_cell}'
                f"<td>{asset['size']}</td>"
                f'<td>{_escape_xml(note)}</td>'
                f'</tr>'
            )

        return xhtml + '</tbody></table>'

    # ── 多國語系格狀排列（13 欄）──────────────────────────────
    def _generate_multi_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]],
        notes: Dict[str, str],
    ) -> str:
        if not groups:
            return ''

        cols  = MULTI_COLS
        xhtml = f'<h3>{title}</h3>'

        for group_key, assets in sorted(groups.items()):
            group_note = notes.get(group_key, '')
            xhtml += (
                f'<p style="font-size:16px;font-weight:bold;margin-top:20px;">'
                f'群組：{_escape_xml(group_key)}_{{language}}</p>'
                f'<table><tbody>'
                f"<tr><th colspan='{cols}' style='background:#fffde7;text-align:left;'>"
                f'備註說明：{_escape_xml(group_note)}</th></tr>'
            )

            for i in range(0, len(sorted(assets, key=lambda x: x['name'])), cols):
                chunk = sorted(assets, key=lambda x: x['name'])[i:i + cols]
                pad   = cols - len(chunk)

                xhtml += '<tr>'
                for a in chunk:
                    parts = a['name'].rsplit('.', 1)[0].split('_')
                    code  = parts[4].upper() if len(parts) > 4 else '?'
                    xhtml += f"<td style='background:#f1f3f5;font-size:10px;text-align:center;'>{code}</td>"
                xhtml += '<td></td>' * pad + '</tr>'

                xhtml += '<tr>'
                for a in chunk:
                    xhtml += f"<td style='text-align:center;'>{self.get_ac_image_tag(a['name'], a['orig_w'], 90)}</td>"
                xhtml += '<td></td>' * pad + '</tr>'

            xhtml += '</tbody></table>'

        return xhtml

    # ── NU 數字組格狀排列（16 欄）────────────────────────────
    def _generate_nu_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]],
        notes: Dict[str, str],
    ) -> str:
        if not groups:
            return ''

        cols  = NU_COLS
        xhtml = f'<h3>{title}</h3>'

        for group_key, assets in sorted(groups.items()):
            group_note = notes.get(group_key, '')
            xhtml += (
                f'<h4>{_escape_xml(group_key)}</h4>'
                f'<table><tbody>'
                f"<tr><th colspan='{cols}' style='background:#fffde7;text-align:left;'>"
                f'備註說明：{_escape_xml(group_note)}</th></tr>'
            )

            for i in range(0, len(sorted(assets, key=lambda x: x['name'])), cols):
                chunk = sorted(assets, key=lambda x: x['name'])[i:i + cols]
                pad   = cols - len(chunk)

                xhtml += '<tr>'
                for a in chunk:
                    label = a['name'].rsplit('.', 1)[0].split('_')[-1]
                    xhtml += f"<td style='background:#f1f3f5;font-size:10px;text-align:center;'>{_escape_xml(label)}</td>"
                xhtml += '<td></td>' * pad + '</tr>'

                xhtml += '<tr>'
                for a in chunk:
                    xhtml += f"<td style='text-align:center;'>{self.get_ac_image_tag(a['name'], a['orig_w'], 60)}</td>"
                xhtml += '<td></td>' * pad + '</tr>'

            xhtml += '</tbody></table>'

        return xhtml
