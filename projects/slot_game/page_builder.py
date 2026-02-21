"""
Slot Game 頁面建構器 — 生成 Confluence XHTML 頁面內容
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from urllib.parse import unquote, urlparse, parse_qs

if TYPE_CHECKING:
    from .validator import FilenameValidator


LAYOUT_COLS = 8
MULTI_COLS  = 13
NU_COLS     = 16

# 警告樣式（橘底 + 橘色文字，span 也明確設色避免 Confluence 覆蓋）
_WARN_TD   = "background:#fff3e0; color:#e65100; font-size:11px; font-weight:bold;"
_WARN_SPAN = "font-size:10px; font-weight:normal; color:#e65100;"
# 群組標題下方警告（無背景，只有橘色文字）
_WARN_GROUP = "color:#e65100; font-size:11px; font-weight:bold;"
# 頁面頂部彙總區塊
_WARN_SUMMARY_TD = "background:#fff3e0; padding:10px;"
_WARN_SUMMARY_TITLE = "font-size:13px; font-weight:bold; color:#e65100;"
_WARN_SUMMARY_ITEM  = "font-size:11px; color:#e65100; margin:2px 0;"


def _escape_xml(text: str) -> str:
    return (
        text.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;')
            .replace("'", '&apos;')
    )


def _stem(filename: str) -> str:
    from pathlib import Path
    return Path(filename).stem


class SlotGamePageBuilder:

    @staticmethod
    def get_ac_image_tag(filename: str, img_w: int, target_max: int) -> str:
        final_w = min(img_w, target_max)
        return (
            f'<ac:image ac:width="{final_w}">'
            f'<ri:attachment ri:filename="{_escape_xml(filename)}" />'
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
        naming_doc_url: Optional[str] = None,
    ) -> str:
        if notes is None:
            notes = {}

        # ── 收集所有警告（供頁面頂部彙總用）──────────────────
        warnings: Dict[str, List[str]] = {}  # {filename: [warning, ...]}
        if validator:
            for asset in self._iter_all_assets(categories):
                ws = validator.validate_all(asset['name'])
                if ws:
                    warnings[asset['name']] = ws

        body = ''
        body += self._generate_history_table(history)

        # 頂部命名錯誤彙總（更新紀錄後、TOC 前）
        if warnings:
            body += self._generate_warning_summary(warnings, naming_doc_url)

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
            categories['multi_main'], notes, validator,
        )
        body += self._generate_nu_grid(
            '🔢 主遊戲—數字組 (NU)',
            categories['nu_main'], notes, validator,
        )

        body += self._generate_normal_table(
            '🎁 3. 免費遊戲 (Free Game) 素材列表',
            categories['free'], notes, validator,
        )
        body += self._generate_multi_grid(
            '🌐 免費遊戲—多國語系版',
            categories['multi_free'], notes, validator,
        )
        body += self._generate_nu_grid(
            '🔢 免費遊戲—數字組 (NU)',
            categories['nu_free'], notes, validator,
        )

        body += self._generate_normal_table(
            '⏳ 4. 載入畫面 (Loading) 素材列表',
            categories['loading'], notes, validator,
        )
        body += self._generate_multi_grid(
            '🌐 載入畫面—多國語系版',
            categories['multi_loading'], notes, validator,
        )
        body += self._generate_nu_grid(
            '🔢 載入畫面—數字組 (NU)',
            categories['nu_loading'], notes, validator,
        )

        return body

    # ── 頂部命名錯誤彙總 ──────────────────────────────────────
    @staticmethod
    def _generate_warning_summary(
        warnings: Dict[str, str],
        naming_doc_url: Optional[str],
    ) -> str:
        """
        更新紀錄後、TOC 前的橘色彙總區塊。
        警告依類型分成三欄：雲端/複製異常 / 欄位不足 / 語意規則違反。
        """
        # ── 分欄設定 ──────────────────────────────────────────
        COLS = [
            ('🔁 雲端／複製異常',  ['衝突複本', '複製', 'Copy', 'Dropbox', '暫存', '空白']),
            ('📐 欄位不足',       ['欄位不足', '疑似 NU', '疑似多國']),
            ('🚫 語意規則違反',   ['命名', '禁詞', '底線', 'nu', '多語系']),
        ]

        def classify(msg: str) -> int:
            for idx, (_, keywords) in enumerate(COLS):
                if any(k in msg for k in keywords):
                    return idx
            return 2  # 未能分類歸到語意欄

        buckets: List[List[tuple]] = [[] for _ in COLS]
        for fn, msgs in sorted(warnings.items()):
            multi = len(msgs) > 1  # 違反多條規則
            for msg in msgs:
                buckets[classify(msg)].append((fn, msg, multi))

        # ── 標題 ──────────────────────────────────────────────
        link_html = ''
        if naming_doc_url:
            safe_url = _escape_xml(naming_doc_url)
            link_html = f'，請參照 <a href="{safe_url}">命名規範文件</a> 修正'

        title = (
            f'<p style="{_WARN_SUMMARY_TITLE}">'
            f'⚠️ 本次同步發現命名異常{link_html}</p>'
        )

        # ── 內部分欄表格 ──────────────────────────────────────
        th_style = (
            'background:#ffe0b2; color:#bf360c; font-size:11px; font-weight:bold; text-align:left; padding:4px 8px; white-space:nowrap;'
        )
        td_style = 'font-size:11px; vertical-align:top; padding:3px 8px; white-space:nowrap;'

        header_cells = ''.join(
            f'<th style="{th_style}">{_escape_xml(col_title)}</th>'
            for col_title, _ in COLS
        )

        max_rows = max((len(b) for b in buckets), default=0)
        body_rows = ''
        for row_idx in range(max_rows):
            body_rows += '<tr>'
            for bucket in buckets:
                if row_idx < len(bucket):
                    fn, msg, multi = bucket[row_idx]
                    fn_color = 'color:#e65100;font-weight:bold;' if multi else 'font-weight:bold;'
                    body_rows += (
                        f'<td style="{td_style}">'
                        f'<span style="{fn_color}">{_escape_xml(fn)}</span>'
                        f'</td>'
                    )
                else:
                    body_rows += '<td></td>'
            body_rows += '</tr>'

        inner_table = (
            f'<table style="width:100%; border-collapse:collapse;">'
            f'<thead><tr>{header_cells}</tr></thead>'
            f'<tbody>{body_rows}</tbody>'
            f'</table>'
        )

        return (
            '<h2>⚠️ 命名異常列表</h2>'
            '<table><tbody><tr>'
            f'<td style="{_WARN_SUMMARY_TD}">'
            f'{title}{inner_table}'
            f'</td>'
            '</tr></tbody></table>'
        )

    # ── TOC ──────────────────────────────────────────────────
    @staticmethod
    def _generate_top_toc() -> str:
        return (
            '<p><ac:structured-macro ac:name="toc">'
            '<ac:parameter ac:name="minLevel">2</ac:parameter>'
            '<ac:parameter ac:name="maxLevel">6</ac:parameter>'
            '<ac:parameter ac:name="printable">false</ac:parameter>'
            '</ac:structured-macro></p><hr />'
        )

    @staticmethod
    def _generate_section_toc() -> str:
        return (
            '<hr /><p><ac:structured-macro ac:name="toc">'
            '<ac:parameter ac:name="minLevel">2</ac:parameter>'
            '<ac:parameter ac:name="maxLevel">2</ac:parameter>'
            '<ac:parameter ac:name="type">flat</ac:parameter>'
            '<ac:parameter ac:name="separator">brackets</ac:parameter>'
            '<ac:parameter ac:name="printable">false</ac:parameter>'
            '</ac:structured-macro></p>'
        )

    # ── Jira ─────────────────────────────────────────────────
    @staticmethod
    def _parse_jira_params(jira_url: str) -> Dict[str, str]:
        params = parse_qs(urlparse(jira_url).query)
        jql = params.get('jql', [])
        fid = params.get('filter', [])
        if jql:
            return {'type': 'jqlQuery', 'value': unquote(jql[0])}
        if fid and fid[0].lstrip('-').isdigit() and int(fid[0]) > 0:
            return {'type': 'filterId', 'value': fid[0]}
        return {'type': 'jqlQuery', 'value': jira_url}

    @staticmethod
    def _generate_jira_block(url: str) -> str:
        p = SlotGamePageBuilder._parse_jira_params(url)
        cols = 'issuetype,key,summary,assignee,reporter,priority,status,resolution,created,updated,due'
        return (
            '<h2>📋 0. Jira 任務清單</h2>'
            '<ac:structured-macro ac:name="jira">'
            f'<ac:parameter ac:name="{p["type"]}">{p["value"]}</ac:parameter>'
            f'<ac:parameter ac:name="columns">{cols}</ac:parameter>'
            '<ac:parameter ac:name="maximumIssues">50</ac:parameter>'
            '</ac:structured-macro>'
        )

    # ── 更新歷史 ──────────────────────────────────────────────
    @staticmethod
    def _generate_history_table(history: List[Dict[str, str]]) -> str:
        if not history:
            return ''
        xhtml = (
            '<h2>📝 更新紀錄</h2><table><thead><tr>'
            "<th style='background:#f1f3f5;'>日期</th>"
            "<th style='background:#f1f3f5;'>內容</th>"
            "<th style='background:#f1f3f5;'>更新者</th>"
            '</tr></thead><tbody>'
        )
        for h in history:
            user = f'<ac:link><ri:user ri:account-id="{h["user_id"]}" /></ac:link>'
            xhtml += (
                f'<tr><td>{h["date"]}</td>'
                f'<td>{_escape_xml(h["log"])}</td>'
                f'<td>{user}</td></tr>'
            )
        return xhtml + '</tbody></table>'

    # ── Layout ────────────────────────────────────────────────
    def _generate_layout_grid(
        self,
        assets: List[Dict[str, Any]],
        notes: Dict[str, str],
    ) -> str:
        if not assets:
            return ''
        cols  = LAYOUT_COLS
        xhtml = '<h2>🖼 1. Layout 版型排列</h2>' + self._generate_section_toc() + '<table><tbody>'
        sorted_assets = sorted(assets, key=lambda x: x['name'])

        for i in range(0, len(sorted_assets), cols):
            chunk = sorted_assets[i:i + cols]
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
        if not assets:
            return ''
        xhtml = (
            f'<h2>{title}</h2>' + self._generate_section_toc()
            + '<table><thead>'
            '<tr><th>圖片</th><th>檔名</th><th>尺寸</th><th>說明</th></tr>'
            '</thead><tbody>'
        )
        for asset in sorted(assets, key=lambda x: x['name']):
            note    = notes.get(asset['name'], notes.get(_stem(asset['name']), ''))
            warning = validator.validate(asset['name']) if validator else None

            if warning:
                all_warns = validator.validate_all(asset['name']) if validator else [warning]
                extra = len(all_warns) - 1
                extra_html = (
                    f' <span style="color:#e65100;font-weight:bold;">+{extra}</span>'
                    if extra > 0 else ''
                )
                # 橘底 td + span 明確設橘色（避免 Confluence 覆蓋繼承）
                name_cell = (
                    f"<td style='{_WARN_TD}'>"
                    f"{_escape_xml(asset['name'])}<br/>"
                    f"<span style='{_WARN_SPAN}'>{_escape_xml(warning)}{extra_html}</span>"
                    f"</td>"
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
        validator: Optional['FilenameValidator'] = None,
    ) -> str:
        if not groups:
            return ''
        cols  = MULTI_COLS
        xhtml = f'<h3>{title}</h3>'

        for group_key, assets in sorted(groups.items()):
            group_note = notes.get(group_key, '')

            # 群組警告：group_key 本身異常（如括號數字）
            group_warn = validator.validate_group_key(group_key) if validator else None

            # 群組警告：群組內任一檔案有問題（如欄位不足、語意違規）
            if not group_warn and validator:
                for a in assets:
                    w = validator.validate(a['name'])
                    if w:
                        group_warn = f'{w}（例：{a["name"]}）'
                        break

            xhtml += (
                f'<p style="font-size:16px;font-weight:bold;margin-top:20px;">'
                f'群組：{_escape_xml(group_key)}_{{language}}</p>'
            )
            if group_warn:
                xhtml += (f'<p style="margin:2px 0 6px 0;">'f'<span style="color:#e65100; font-size:12px; font-weight:bold;">'f'⚠️ {_escape_xml(group_warn)}</span></p>')

            xhtml += (
                f'<table><tbody>'
                f"<tr><th colspan='{cols}' style='background:#fffde7;text-align:left;'>"
                f'備註說明：{_escape_xml(group_note)}</th></tr>'
            )

            sorted_assets = sorted(assets, key=lambda x: x['name'])
            for i in range(0, len(sorted_assets), cols):
                chunk = sorted_assets[i:i + cols]
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

                xhtml += '<tr>'
                for a in chunk:
                    w, h = a.get('orig_w', 0), a.get('orig_h', 0)
                    size_str = f'{w}x{h}' if w and h else '-'
                    xhtml += f"<td style='font-size:9px;text-align:center;color:#868e96;'>{size_str}</td>"
                xhtml += '<td></td>' * pad + '</tr>'

            xhtml += '</tbody></table>'
        return xhtml

    # ── NU 數字組格狀排列（16 欄）────────────────────────────
    def _generate_nu_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]],
        notes: Dict[str, str],
        validator: Optional['FilenameValidator'] = None,
    ) -> str:
        if not groups:
            return ''
        cols  = NU_COLS
        xhtml = f'<h3>{title}</h3>'

        for group_key, assets in sorted(groups.items()):
            group_note = notes.get(group_key, '')
            # 群組 key 異常警告
            group_warn = validator.validate_group_key(group_key) if validator else None

            xhtml += f'<h4>{_escape_xml(group_key)}</h4>'
            if group_warn:
                xhtml += (f'<p style="margin:2px 0 6px 0;">'f'<span style="color:#e65100; font-size:12px; font-weight:bold;">'f'{_escape_xml(group_warn)}</span></p>')

            xhtml += (
                f'<table><tbody>'
                f"<tr><th colspan='{cols}' style='background:#fffde7;text-align:left;'>"
                f'備註說明：{_escape_xml(group_note)}</th></tr>'
            )

            sorted_assets = sorted(assets, key=lambda x: x['name'])
            for i in range(0, len(sorted_assets), cols):
                chunk = sorted_assets[i:i + cols]
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

                xhtml += '<tr>'
                for a in chunk:
                    w, h = a.get('orig_w', 0), a.get('orig_h', 0)
                    size_str = f'{w}x{h}' if w and h else '-'
                    xhtml += f"<td style='font-size:9px;text-align:center;color:#868e96;'>{size_str}</td>"
                xhtml += '<td></td>' * pad + '</tr>'

            xhtml += '</tbody></table>'
        return xhtml

    # ── 工具：收集所有 asset（供彙總警告用）──────────────────
    @staticmethod
    def _iter_all_assets(categories: Dict[str, Any]):
        for v in categories.values():
            if isinstance(v, list):
                yield from v
            elif isinstance(v, dict):
                for group in v.values():
                    yield from group
