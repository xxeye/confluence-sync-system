"""
Slot Game 頁面建構器 — 生成 Confluence XHTML 頁面內容
"""

from typing import Dict, List, Any, Optional
from urllib.parse import unquote, urlparse, parse_qs


# ── 全域欄數設定 ──────────────────────────────────────────────
LAYOUT_COLS = 8    # Layout 格狀排列欄數
MULTI_COLS  = 13   # 多國語系格狀排列欄數
NU_COLS     = 16   # 數字組格狀排列欄數

# ── 警告樣式 ──────────────────────────────────────────────────
# 所有警告統一顯示在檔名欄下方，橘底標示
_WARN_NAME_STYLE  = "background:#fff3e0; color:#e65100; font-size:11px; font-weight:bold;"


def _escape_xml(text: str) -> str:
    """將字串中的 XML 特殊字元 escape，確保 XHTML 合法"""
    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;')
    )


class SlotGamePageBuilder:
    """Slot Game 頁面建構器"""

    @staticmethod
    def get_ac_image_tag(filename: str, img_w: int, target_max: int) -> str:
        """生成 Confluence 附件圖片標籤"""
        final_w = min(img_w, target_max)
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
    ) -> str:
        """組裝完整頁面內容"""
        if notes is None:
            notes = {}

        body = ""
        body += self._generate_history_table(history)
        body += self._generate_top_toc()

        if jira_filter_url:
            body += self._generate_jira_block(jira_filter_url)

        body += self._generate_layout_grid(categories['layout'], notes)

        body += self._generate_normal_table(
            "🎰 2. 主遊戲 (Main Game) 素材列表",
            categories['main'], notes,
        )
        body += self._generate_multi_grid(
            "🌐 主遊戲—多國語系版",
            categories['multi_main'], notes,
        )
        body += self._generate_nu_grid(
            "🔢 主遊戲—數字組 (NU)",
            categories['nu_main'], notes,
        )

        body += self._generate_normal_table(
            "🎁 3. 免費遊戲 (Free Game) 素材列表",
            categories['free'], notes,
        )
        body += self._generate_multi_grid(
            "🌐 免費遊戲—多國語系版",
            categories['multi_free'], notes,
        )
        body += self._generate_nu_grid(
            "🔢 免費遊戲—數字組 (NU)",
            categories['nu_free'], notes,
        )

        body += self._generate_normal_table(
            "⏳ 4. 載入畫面 (Loading) 素材列表",
            categories['loading'], notes,
        )
        body += self._generate_multi_grid(
            "🌐 載入畫面—多國語系版",
            categories['multi_loading'], notes,
        )
        body += self._generate_nu_grid(
            "🔢 載入畫面—數字組 (NU)",
            categories['nu_loading'], notes,
        )

        return body

    # ── 目錄（TOC）────────────────────────────────────────────
    @staticmethod
    def _generate_top_toc() -> str:
        return (
            '<p>'
            '<ac:structured-macro ac:name="toc">'
            '<ac:parameter ac:name="minLevel">2</ac:parameter>'
            '<ac:parameter ac:name="maxLevel">6</ac:parameter>'
            '<ac:parameter ac:name="printable">false</ac:parameter>'
            '</ac:structured-macro>'
            '</p>'
            '<hr />'
        )

    @staticmethod
    def _generate_section_toc() -> str:
        return (
            '<hr />'
            '<p>'
            '<ac:structured-macro ac:name="toc">'
            '<ac:parameter ac:name="minLevel">2</ac:parameter>'
            '<ac:parameter ac:name="maxLevel">2</ac:parameter>'
            '<ac:parameter ac:name="type">flat</ac:parameter>'
            '<ac:parameter ac:name="separator">brackets</ac:parameter>'
            '<ac:parameter ac:name="printable">false</ac:parameter>'
            '</ac:structured-macro>'
            '</p>'
        )

    # ── Jira 清單 ─────────────────────────────────────────────
    @staticmethod
    def _parse_jira_params(jira_url: str) -> Dict[str, str]:
        params      = parse_qs(urlparse(jira_url).query)
        jql_list    = params.get('jql', [])
        filter_list = params.get('filter', [])
        if jql_list:
            return {'type': 'jqlQuery', 'value': unquote(jql_list[0])}
        if filter_list:
            fid = filter_list[0]
            if fid.lstrip('-').isdigit() and int(fid) > 0:
                return {'type': 'filterId', 'value': fid}
        return {'type': 'jqlQuery', 'value': jira_url}

    @staticmethod
    def _generate_jira_block(jira_filter_url: str) -> str:
        p       = SlotGamePageBuilder._parse_jira_params(jira_filter_url)
        columns = 'issuetype,key,summary,assignee,reporter,priority,status,resolution,created,updated,due'
        return (
            '<h2>📋 0. Jira 任務清單</h2>'
            + '<ac:structured-macro ac:name="jira">'
            + f'<ac:parameter ac:name="{p["type"]}">{p["value"]}</ac:parameter>'
            + f'<ac:parameter ac:name="columns">{columns}</ac:parameter>'
            + '<ac:parameter ac:name="maximumIssues">50</ac:parameter>'
            + '</ac:structured-macro>'
        )

    # ── 更新歷史表格 ───────────────────────────────────────────
    @staticmethod
    def _generate_history_table(history: List[Dict[str, str]]) -> str:
        if not history:
            return ""
        xhtml = (
            "<h2>📝 更新紀錄</h2>"
            "<table><thead><tr>"
            "<th style='background:#f1f3f5;'>日期</th>"
            "<th style='background:#f1f3f5;'>內容</th>"
            "<th style='background:#f1f3f5;'>更新者</th>"
            "</tr></thead><tbody>"
        )
        for h in history:
            user_tag = f'<ac:link><ri:user ri:account-id="{h["user_id"]}" /></ac:link>'
            xhtml += (
                f"<tr>"
                f"<td>{h['date']}</td>"
                f"<td>{_escape_xml(h['log'])}</td>"
                f"<td>{user_tag}</td>"
                f"</tr>"
            )
        xhtml += "</tbody></table>"
        return xhtml

    # ── Layout 格狀排列（8 欄）────────────────────────────────
    def _generate_layout_grid(
        self,
        assets: List[Dict[str, Any]],
        notes: Dict[str, str],
    ) -> str:
        if not assets:
            return ""

        cols  = LAYOUT_COLS
        xhtml = (
            "<h2>🖼 1. Layout 版型排列</h2>"
            + self._generate_section_toc()
            + "<table><tbody>"
        )
        sorted_assets = sorted(assets, key=lambda x: x['name'])

        for i in range(0, len(sorted_assets), cols):
            chunk = sorted_assets[i:i + cols]
            pad   = cols - len(chunk)

            xhtml += "<tr>"
            for asset in chunk:
                xhtml += (
                    f"<td style='background:#f1f3f5; font-size:11px; font-weight:bold;'>"
                    f"{_escape_xml(asset['name'])}</td>"
                )
            xhtml += "<td></td>" * pad + "</tr>"

            xhtml += "<tr>"
            for asset in chunk:
                xhtml += f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 200)}</td>"
            xhtml += "<td></td>" * pad + "</tr>"

            has_notes = any(notes.get(a['name'], notes.get(_stem(a['name']), '')) for a in chunk)
            if has_notes:
                xhtml += "<tr>"
                for asset in chunk:
                    note = notes.get(asset['name'], notes.get(_stem(asset['name']), ''))
                    xhtml += (
                        f"<td style='font-size:11px; color:#555;'>"
                        f"{_escape_xml(note)}</td>"
                    )
                xhtml += "<td></td>" * pad + "</tr>"

        xhtml += "</tbody></table>"
        return xhtml

    # ── 一般圖片表格 ──────────────────────────────────────────
    def _generate_normal_table(
        self,
        title: str,
        assets: List[Dict[str, Any]],
        notes: Dict[str, str],
    ) -> str:
        """
        一般圖片表格：圖片 / 檔名 / 尺寸 / 說明

        警告渲染規則：
          任何警告（欄位不足 / 疑似多國 / 疑似 NU）
          → 檔名欄橘底，警告文字顯示在檔名下方；說明欄正常顯示
        """
        if not assets:
            return ""

        xhtml = (
            f"<h2>{title}</h2>"
            + self._generate_section_toc()
            + "<table>"
            "<thead>"
            "<tr><th>圖片</th><th>檔名</th><th>尺寸</th><th>說明</th></tr>"
            "</thead>"
            "<tbody>"
        )

        for asset in sorted(assets, key=lambda x: x['name']):
            warning = asset.get('warning')
            note    = notes.get(asset['name'], notes.get(_stem(asset['name']), ''))

            # 檔名欄：有警告（任何類型）→ 橘底 + 警告說明顯示在檔名下方
            if warning:
                name_cell = (
                    f"<td style='{_WARN_NAME_STYLE}'>"
                    f"{_escape_xml(asset['name'])}<br/>"
                    f"<span style='font-size:10px; font-weight:normal;'>"
                    f"{_escape_xml(warning)}</span>"
                    f"</td>"
                )
            else:
                name_cell = f"<td>{_escape_xml(asset['name'])}</td>"

            # 說明欄：有警告時留空（警告已在檔名欄顯示），否則顯示 notes
            note_cell = f"<td>{_escape_xml(note)}</td>"

            xhtml += (
                f"<tr>"
                f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 120)}</td>"
                f"{name_cell}"
                f"<td>{asset['size']}</td>"
                f"{note_cell}"
                f"</tr>"
            )

        xhtml += "</tbody></table>"
        return xhtml

    # ── 多國語系格狀排列（13 欄）──────────────────────────────
    def _generate_multi_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]],
        notes: Dict[str, str],
    ) -> str:
        if not groups:
            return ""

        cols  = MULTI_COLS
        xhtml = f"<h3>{title}</h3>"

        for group_key, assets in sorted(groups.items()):
            group_note = notes.get(group_key, '')
            xhtml += (
                f'<p style="font-size:16px; font-weight:bold; margin-top:20px;">'
                f'群組：{_escape_xml(group_key)}_{{language}}'
                f'</p>'
                f'<table><tbody>'
                f"<tr>"
                f"<th colspan='{cols}' style='background:#fffde7; text-align:left;'>"
                f"備註說明：{_escape_xml(group_note)}</th>"
                f"</tr>"
            )

            sorted_assets = sorted(assets, key=lambda x: x['name'])

            for i in range(0, len(sorted_assets), cols):
                chunk = sorted_assets[i:i + cols]
                pad   = cols - len(chunk)

                xhtml += "<tr>"
                for asset in chunk:
                    parts     = asset['name'].rsplit('.', 1)[0].split('_')
                    lang_code = parts[4].upper() if len(parts) > 4 else "?"
                    xhtml += (
                        f"<td style='background:#f1f3f5; font-size:10px; text-align:center;'>"
                        f"{lang_code}</td>"
                    )
                xhtml += "<td></td>" * pad + "</tr>"

                xhtml += "<tr>"
                for asset in chunk:
                    xhtml += (
                        f"<td style='text-align:center;'>"
                        f"{self.get_ac_image_tag(asset['name'], asset['orig_w'], 90)}"
                        f"</td>"
                    )
                xhtml += "<td></td>" * pad + "</tr>"

            xhtml += "</tbody></table>"

        return xhtml

    # ── 數字組格狀排列（16 欄）────────────────────────────────
    def _generate_nu_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]],
        notes: Dict[str, str],
    ) -> str:
        if not groups:
            return ""

        cols  = NU_COLS
        xhtml = f"<h3>{title}</h3>"

        for group_key, assets in sorted(groups.items()):
            group_note = notes.get(group_key, '')
            xhtml += (
                f"<h4>{_escape_xml(group_key)}</h4>"
                f"<table><tbody>"
                f"<tr>"
                f"<th colspan='{cols}' style='background:#fffde7; text-align:left;'>"
                f"備註說明：{_escape_xml(group_note)}</th>"
                f"</tr>"
            )

            sorted_assets = sorted(assets, key=lambda x: x['name'])

            for i in range(0, len(sorted_assets), cols):
                chunk = sorted_assets[i:i + cols]
                pad   = cols - len(chunk)

                xhtml += "<tr>"
                for asset in chunk:
                    label = asset['name'].rsplit('.', 1)[0].split('_')[-1]
                    xhtml += (
                        f"<td style='background:#f1f3f5; font-size:10px; text-align:center;'>"
                        f"{_escape_xml(label)}</td>"
                    )
                xhtml += "<td></td>" * pad + "</tr>"

                xhtml += "<tr>"
                for asset in chunk:
                    xhtml += (
                        f"<td style='text-align:center;'>"
                        f"{self.get_ac_image_tag(asset['name'], asset['orig_w'], 60)}"
                        f"</td>"
                    )
                xhtml += "<td></td>" * pad + "</tr>"

            xhtml += "</tbody></table>"

        return xhtml


# ── 私有工具函式 ──────────────────────────────────────────────
def _stem(filename: str) -> str:
    """取得不含副檔名的檔名，供 notes 查詢 fallback 使用"""
    from pathlib import Path
    return Path(filename).stem
