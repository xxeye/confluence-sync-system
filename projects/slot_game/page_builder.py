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


def _note_for(filename: str, notes: Dict[str, str]) -> str:
    """取得資產備註。

    優先使用完整檔名，其次使用去副檔名（stem）對應。
    這讓 notes 可以同時支援：
      - btn_start.png  -> "..."
      - btn_start      -> "..."（不含副檔名）
    """
    return notes.get(filename, notes.get(_stem(filename), ''))


class SlotGamePageBuilder:

    # 圖片在各區塊的顯示大小（ac:image 會依 Confluence 版面自動調整）
    IMG = {
        'layout': {'max_w': 200, 'max_h': 9999},
        'normal': {'max_w': 120, 'max_h': 9999},
        'multi':  {'max_w': 90,  'max_h': 9999},
        'nu':     {'max_w': 60,  'max_h': 9999},
        'warn':   {'max_w': 80,  'max_h': 60},
    }

    @staticmethod
    def _generate_page_summary_table(image_count: int, has_warnings: bool) -> str:
        """
        更新紀錄下方的頁面摘要（單欄表格）：
        - 本頁面引用圖片數量
        - 若有命名異常，顯示提醒
        """
        warn_line = (
            '<p style="margin:6px 0 0 0;color:#e65100;font-weight:bold;font-size:12px;">'
            '⚠️ 本次同步存在命名異常的元件，列表請見頁面最底部。'
            '</p>'
            if has_warnings else ''
        )

        return (
            '<table><tbody><tr>'
            '<td style="background:#f5f5f5;padding:8px 12px;">'
            f'<p style="margin:0;font-weight:bold;font-size:12px;">'
            f'📦 本頁面引用圖片數量：{image_count}（包含：各區塊素材 + 命名異常列表中的素材）'
            '</p>'
            f'{warn_line}'
            '</td></tr></tbody></table>'
        )

    @staticmethod
    def get_ac_image_tag(
        filename: str,
        orig_w: int,
        orig_h: int,
        max_w: int,
        max_h: int,
    ) -> str:
        """
        產生 Confluence ac:image 標籤。

        策略：只在「原始高度已知且超過 max_h」時，才設定 ac:width 進行等比例縮小。
        其他情況不設尺寸，讓 Confluence 以原圖大小呈現（避免放大造成模糊）。
        """
        # 原始高度已知且超過 max_h → 等比例縮小並設 ac:width
        # 其他情況不設任何尺寸，讓 Confluence 自動顯示原始大小
        if orig_h > 0 and max_h > 0 and orig_h > max_h:
            scale   = max_h / orig_h
            final_w = max(1, int((orig_w or orig_h) * scale))
            return (
                f'<ac:image ac:width="{final_w}">'
                f'<ri:attachment ri:filename="{_escape_xml(filename)}" />'
                f'</ac:image>'
            )
        return (
            f'<ac:image>'
            f'<ri:attachment ri:filename="{_escape_xml(filename)}" />'
            f'</ac:image>'
        )

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
        # 包含 unknown 分類的檔案（classifier 無法歸類）
        warnings: Dict[str, List[str]] = {}  # {filename: [warning, ...]}
        if validator:
            for asset in self._iter_all_assets(categories):
                ws = validator.validate_all(asset['name'])
                if ws:
                    warnings[asset['name']] = ws
        # unknown 分類即使 validator 未啟用也納入警告
        for asset in categories.get('unknown', []):
            if asset['name'] not in warnings:
                warnings[asset['name']] = ['⚠️ 命名不符合規範，無法自動分類']

        # ── 在過濾前先建立 asset_map，確保 warned assets 的尺寸/size 資料不遺失 ──
        pre_filter_asset_map: Dict[str, Dict] = {}
        for asset in self._iter_all_assets(categories):
            pre_filter_asset_map[asset['name']] = asset

        # ✅ 新增：本頁面引用圖片數量（以「過濾前」為準，包含命名異常列表的圖）
        image_count = len(pre_filter_asset_map)

        # ── 有警告的檔案從一般分類移除，統一在命名異常列表顯示 ──
        warned = set(warnings.keys())
        if warned:
            for key in list(categories.keys()):
                if isinstance(categories[key], list):
                    categories[key] = [
                        a for a in categories[key]
                        if a['name'] not in warned
                    ]
                elif isinstance(categories[key], dict):
                    for gk in list(categories[key].keys()):
                        categories[key][gk] = [
                            a for a in categories[key][gk]
                            if a['name'] not in warned
                        ]
                        if not categories[key][gk]:
                            del categories[key][gk]

        body_parts: List[str] = []
        body_parts.append(self._generate_history_table(history))

        # ✅ 合併：資產數量 + 命名異常提醒（同一個單欄表格）
        body_parts.append(self._generate_page_summary_table(image_count, has_warnings=bool(warnings)))
        body_parts.append(self._generate_top_toc())

        if jira_filter_url:
            body_parts.append(self._generate_jira_block(jira_filter_url))

        body_parts.append(self._generate_layout_grid(categories.get('layout', []), notes))

        body_parts.append(self._generate_normal_table(
            '🎰 2. 主遊戲 (Main Game) 素材列表',
            categories.get('main', []), notes, validator,
        ))
        body_parts.append(self._generate_multi_grid(
            '🌐 主遊戲—多國語系版',
            categories.get('multi_main', {}), notes, validator,
        ))
        body_parts.append(self._generate_nu_grid(
            '🔢 主遊戲—數字組 (NU)',
            categories.get('nu_main', {}), notes, validator,
        ))

        body_parts.append(self._generate_normal_table(
            '🎁 3. 免費遊戲 (Free Game) 素材列表',
            categories.get('free', []), notes, validator,
        ))
        body_parts.append(self._generate_multi_grid(
            '🌐 免費遊戲—多國語系版',
            categories.get('multi_free', {}), notes, validator,
        ))
        body_parts.append(self._generate_nu_grid(
            '🔢 免費遊戲—數字組 (NU)',
            categories.get('nu_free', {}), notes, validator,
        ))

        body_parts.append(self._generate_normal_table(
            '⏳ 4. 載入畫面 (Loading) 素材列表',
            categories.get('loading', []), notes, validator,
        ))
        body_parts.append(self._generate_multi_grid(
            '🌐 載入畫面—多國語系版',
            categories.get('multi_loading', {}), notes, validator,
        ))
        body_parts.append(self._generate_nu_grid(
            '🔢 載入畫面—數字組 (NU)',
            categories.get('nu_loading', {}), notes, validator,
        ))

        # 命名異常列表移至最後
        if warnings:
            body_parts.append(self._generate_warning_summary(warnings, naming_doc_url, pre_filter_asset_map, notes))

        return ''.join(body_parts)

    # ── 頂部命名錯誤彙總 ──────────────────────────────────────
    def _generate_warning_summary(
        self,
        warnings: Dict[str, List[str]],
        naming_doc_url: Optional[str],
        asset_map: Dict[str, Dict],
        notes: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        命名異常列表，放在頁面最後。
        每檔一列：圖片 | 檔名＋違規規則 | 尺寸 | 說明（同 notes）
        asset_map 須在過濾前建立，確保 warned assets 的資料完整。
        """
        if notes is None:
            notes = {}

        # ── 標題 ──────────────────────────────────────────────
        link_html = ''
        if naming_doc_url:
            link_html = (
                f'，請參照 <a href="{_escape_xml(naming_doc_url)}">命名規範文件</a> 修正'
            )
        title_html = (
            f'<p style="{_WARN_SUMMARY_TITLE}">' +
            f'⚠️ 本次同步發現命名異常{link_html}</p>'
        )

        # ── 樣式 ──────────────────────────────────────────────
        th = ('background:#ffe0b2;color:#bf360c;font-size:11px;'
              'font-weight:bold;padding:4px 8px;text-align:left;')
        td = 'padding:4px 8px;vertical-align:top;font-size:11px;'

        rows = ''
        for fn, msgs in sorted(warnings.items()):
            asset   = asset_map.get(fn, {'name': fn, 'size': '-', 'orig_w': 0, 'orig_h': 0})
            ow      = asset.get('orig_w', 0)
            oh      = asset.get('orig_h', 0)
            multi   = len(msgs) > 1
            fn_clr  = 'color:#e65100;font-weight:bold;' if multi else 'font-weight:bold;'

            # 圖片欄
            img_cell = (
                f'<td style="{td};text-align:center;">' +
                self.get_ac_image_tag(fn, ow, oh, **self.IMG['warn']) +
                '</td>'
            )

            # 檔名＋違規規則欄
            rules_html = ''
            for msg in msgs:
                # 保留 ⚠️ emoji，文字改為橘色（與觸犯兩條規則的橘色相同）
                rules_html += (
                    f'<p style="margin:2px 0;font-size:10px;color:#e65100;font-weight:bold;">' +
                    _escape_xml(msg) + '</p>'
                )
            name_cell = (
                f'<td style="{td}">' +
                f'<span style="{fn_clr}">{_escape_xml(fn)}</span>' +
                rules_html + '</td>'
            )

            # 尺寸欄（與主遊戲/免費遊戲素材列表一致，顯示檔案大小）
            size_val  = asset.get('size', '-') or '-'
            size_cell = f'<td style="{td};white-space:nowrap;">{_escape_xml(str(size_val))}</td>'

            # 說明欄（同 notes）
            note      = _note_for(fn, notes)
            note_cell = f'<td style="{td}">{_escape_xml(note)}</td>'

            rows += f'<tr>{img_cell}{name_cell}{size_cell}{note_cell}</tr>'

        inner_table = (
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr>'
            f'<th style="{th}">圖片</th>'
            f'<th style="{th}">檔名</th>'
            f'<th style="{th}">尺寸</th>'
            f'<th style="{th}">說明</th>'
            f'</tr></thead>'
            f'<tbody>{rows}</tbody>'
            f'</table>'
        )

        return (
            '<h2>⚠️ 命名異常列表</h2>'
            '<table><tbody><tr>'
            f'<td style="{_WARN_SUMMARY_TD}">' +
            title_html + inner_table +
            '</td></tr></tbody></table>'
        )

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
                xhtml += f"<td>{self.get_ac_image_tag(a['name'], a.get('orig_w',0), a.get('orig_h',0), **self.IMG['layout'])}</td>"
            xhtml += '<td></td>' * pad + '</tr>'

            has_notes = any(_note_for(a['name'], notes) for a in chunk)
            if has_notes:
                xhtml += '<tr>'
                for a in chunk:
                    note = _note_for(a['name'], notes)
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
            note      = _note_for(asset['name'], notes)
            all_warns = validator.validate_all(asset['name']) if validator else []
            warning   = all_warns[0] if all_warns else None

            if warning:
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
                f"<td>{self.get_ac_image_tag(asset['name'], asset.get('orig_w',0), asset.get('orig_h',0), **self.IMG['normal'])}</td>"
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
                        group_warn = w.lstrip('⚠️').strip()
                        break

            xhtml += (
                f'<p style="font-size:16px;font-weight:bold;margin-top:20px;">'
                f'群組：{_escape_xml(group_key)}_{{language}}</p>'
            )
            if group_warn:
                xhtml += (f'<p style="margin:2px 0 6px 0;">'
                          f'<span style="color:#e65100; font-size:12px; font-weight:bold;">'
                          f' {_escape_xml(group_warn)}</span></p>')

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
                    xhtml += f"<td style='text-align:center;'>{self.get_ac_image_tag(a['name'], a.get('orig_w',0), a.get('orig_h',0), **self.IMG['multi'])}</td>"
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
                xhtml += (f'<p style="margin:2px 0 6px 0;">'
                          f'<span style="color:#e65100; font-size:12px; font-weight:bold;">'
                          f'{_escape_xml(group_warn)}</span></p>')

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
                    xhtml += f"<td style='text-align:center;'>{self.get_ac_image_tag(a['name'], a.get('orig_w',0), a.get('orig_h',0), **self.IMG['nu'])}</td>"
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