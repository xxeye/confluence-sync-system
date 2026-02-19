"""
Slot Game 頁面建構器
生成 Confluence XHTML 格式的頁面內容
"""

from typing import Dict, List, Any, Optional
from urllib.parse import unquote, urlparse, parse_qs


# ── 欄位寬度常數 ──────────────────────────────────────────
LAYOUT_COLS = 8    # Layout 示意圖每行欄數
MULTI_COLS  = 13   # 多國語系對照每行欄數
NU_COLS     = 16   # 位圖數字每行欄數


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
        """生成 Confluence 專用圖片標籤"""
        final_w = min(img_w, target_max)
        # filename 可能含特殊字元（如貨幣符號），需 escape
        safe_name = _escape_xml(filename)
        return (
            f'<ac:image ac:width="{final_w}">'
            f'<ri:attachment ri:filename="{safe_name}" />'
            f'</ac:image>'
        )

    # ── 公開組裝入口 ─────────────────────────────────────
    def assemble(
        self,
        categories: Dict[str, Any],
        history: List[Dict[str, str]],
        jira_filter_url: Optional[str] = None,
    ) -> str:
        """組裝完整頁面內容"""
        body = ""

        # ① 版本歷史
        body += self._generate_history_table(history)

        # ② 頂部大目錄（H2~H6，直式）—— 緊接版本說明下方
        body += self._generate_top_toc()

        # ③ Jira 工作列表（在 Layout 之前）
        if jira_filter_url:
            body += self._generate_jira_block(jira_filter_url)

        # ④ Layout 專案示意圖
        body += self._generate_layout_grid(categories['layout'])

        # ⑤ 主遊戲
        body += self._generate_normal_table(
            "🏠 2. 主遊戲 (Main Game) 資源清單",
            categories['main'],
        )
        body += self._generate_multi_grid(
            "🌏 主遊戲：多國語系對照",
            categories['multi_main'],
        )
        body += self._generate_nu_grid(
            "🔢 主遊戲：位圖數字 (NU)",
            categories['nu_main'],
        )

        # ⑥ 免費遊戲
        body += self._generate_normal_table(
            "🎁 3. 免費遊戲 (Free Game) 資源清單",
            categories['free'],
        )
        body += self._generate_multi_grid(
            "🌏 免費遊戲：多國語系對照",
            categories['multi_free'],
        )
        body += self._generate_nu_grid(
            "🔢 免費遊戲：位圖數字 (NU)",
            categories['nu_free'],
        )

        # ⑦ 載入畫面
        body += self._generate_normal_table(
            "⏳ 4. 載入畫面 (Loading) 資源清單",
            categories['loading'],
        )
        body += self._generate_multi_grid(
            "🌏 載入畫面：多國語系對照",
            categories['multi_loading'],
        )
        body += self._generate_nu_grid(
            "🔢 載入畫面：位圖數字 (NU)",
            categories['nu_loading'],
        )

        return body

    # ── 頂部大目錄（H2~H6，直式）───────────────────────────
    @staticmethod
    def _generate_top_toc() -> str:
        """
        頁面頂部完整目錄，H2~H6，直式列表。
        不帶 type 參數預設即為直式（垂直列表）。
        """
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

    # ── 每個 H2 下方的區塊快速目錄（H2，水平）────────────────
    @staticmethod
    def _generate_section_toc() -> str:
        """
        每個 H2 區塊下方的快速跳轉目錄，只列 H2，水平排列。
        Confluence Cloud TOC macro 用 type=flat 呈現水平列表，
        各項目以 [ ] 括號分隔顯示在同一行。
        """
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

    # ── Jira 工作列表 ────────────────────────────────────
    @staticmethod
    def _parse_jira_params(jira_url: str) -> Dict[str, str]:
        """
        從 Jira 篩選器網址解析 macro 參數。
        回傳 {'type': 'filterId' | 'jqlQuery', 'value': ...}
        """
        params      = parse_qs(urlparse(jira_url).query)
        jql_list    = params.get('jql', [])
        filter_list = params.get('filter', [])

        if jql_list:
            return {'type': 'jqlQuery', 'value': unquote(jql_list[0])}

        if filter_list:
            fid = filter_list[0]
            if fid.lstrip('-').isdigit() and int(fid) > 0:
                return {'type': 'filterId', 'value': fid}

        # fallback：整個 URL 當 jqlQuery
        return {'type': 'jqlQuery', 'value': jira_url}

    @staticmethod
    def _generate_jira_block(jira_filter_url: str) -> str:
        """
        生成 Jira macro（注意：macro 名稱是 "jira"，不是 "jiraissues"）。
        URL 解析成 jqlQuery 或 filterId 參數後直接放文字，不用 ri:url 包裝。
        macro 參數值為純文字，不需要 XML escape（Confluence 自行處理）。
        """
        p       = SlotGamePageBuilder._parse_jira_params(jira_filter_url)
        columns = 'issuetype,key,summary,assignee,reporter,priority,status,resolution,created,updated,due'

        return (
            '<h2>📋 0. Jira 工作列表</h2>'
            + '<ac:structured-macro ac:name="jira">'
            + f'<ac:parameter ac:name="{p["type"]}">{p["value"]}</ac:parameter>'
            + f'<ac:parameter ac:name="columns">{columns}</ac:parameter>'
            + '<ac:parameter ac:name="maximumIssues">50</ac:parameter>'
            + '</ac:structured-macro>'
        )

    # ── 版本歷史表格 ─────────────────────────────────────
    @staticmethod
    def _generate_history_table(history: List[Dict[str, str]]) -> str:
        """生成版本更新說明表格"""
        if not history:
            return ""

        xhtml = (
            "<h2>📝 版本更新</h2>"
            "<table>"
            "<thead>"
            "<tr>"
            "<th style='background:#f1f3f5;'>時間</th>"
            "<th style='background:#f1f3f5;'>內容</th>"
            "<th style='background:#f1f3f5;'>人員</th>"
            "</tr>"
            "</thead>"
            "<tbody>"
        )

        for h in history:
            user_tag = (
                f'<ac:link><ri:user ri:account-id="{h["user_id"]}" /></ac:link>'
            )
            xhtml += (
                f"<tr>"
                f"<td>{h['date']}</td>"
                f"<td>{_escape_xml(h['log'])}</td>"
                f"<td>{user_tag}</td>"
                f"</tr>"
            )

        xhtml += "</tbody></table>"
        return xhtml

    # ── Layout 示意圖（8 欄）────────────────────────────
    def _generate_layout_grid(self, assets: List[Dict[str, Any]]) -> str:
        """生成 Layout 專案示意圖，每行 LAYOUT_COLS 欄，最後一行補空格"""
        if not assets:
            return ""

        cols  = LAYOUT_COLS
        xhtml = (
            "<h2>📐 1. Layout 專案示意圖</h2>"
            + self._generate_section_toc()
            + "<table><tbody>"
        )
        sorted_assets = sorted(assets, key=lambda x: x['name'])

        for i in range(0, len(sorted_assets), cols):
            chunk = sorted_assets[i:i + cols]
            pad   = cols - len(chunk)

            # 檔名行
            xhtml += "<tr>"
            for asset in chunk:
                xhtml += (
                    f"<td style='background:#f1f3f5; font-size:11px; font-weight:bold;'>"
                    f"{_escape_xml(asset['name'])}</td>"
                )
            xhtml += "<td></td>" * pad + "</tr>"

            # 圖片行
            xhtml += "<tr>"
            for asset in chunk:
                xhtml += f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 200)}</td>"
            xhtml += "<td></td>" * pad + "</tr>"

        xhtml += "</tbody></table>"
        return xhtml

    # ── 一般資源清單表格 ─────────────────────────────────
    def _generate_normal_table(
        self,
        title: str,
        assets: List[Dict[str, Any]],
    ) -> str:
        """生成一般資源清單（預覽 / 名稱 / 尺寸 / 說明）"""
        if not assets:
            return ""

        xhtml = (
            f"<h2>{title}</h2>"
            + self._generate_section_toc()
            + "<table>"
            "<thead>"
            "<tr><th>預覽</th><th>名稱</th><th>尺寸</th><th>說明</th></tr>"
            "</thead>"
            "<tbody>"
        )

        for asset in sorted(assets, key=lambda x: x['name']):
            xhtml += (
                f"<tr>"
                f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 120)}</td>"
                f"<td>{_escape_xml(asset['name'])}</td>"
                f"<td>{asset['size']}</td>"
                f"<td></td>"  # 說明欄位（留空，供人工填寫）
                f"</tr>"
            )

        xhtml += "</tbody></table>"
        return xhtml

    # ── 多國語系對照（13 欄，補滿最後一行）────────────────
    def _generate_multi_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """生成多國語系對照表，每行 MULTI_COLS 欄，最後一行補空格"""
        if not groups:
            return ""

        cols  = MULTI_COLS
        xhtml = f"<h3>{title}</h3>"

        for group_key, assets in sorted(groups.items()):
            xhtml += (
                f'<p style="font-size:16px; font-weight:bold; margin-top:20px;">'
                f'組別：{_escape_xml(group_key)}_{{language}}'
                f'</p>'
                f'<table><tbody>'
                f"<tr>"
                f"<th colspan='{cols}' style='background:#fffde7; text-align:left;'>"
                f"備註說明：</th>"
                f"</tr>"
            )

            sorted_assets = sorted(assets, key=lambda x: x['name'])

            for i in range(0, len(sorted_assets), cols):
                chunk = sorted_assets[i:i + cols]
                pad   = cols - len(chunk)

                # 語系標籤行
                xhtml += "<tr>"
                for asset in chunk:
                    parts     = asset['name'].rsplit('.', 1)[0].split('_')
                    lang_code = parts[4].upper() if len(parts) > 4 else "?"
                    xhtml += (
                        f"<td style='background:#f1f3f5; font-size:10px; text-align:center;'>"
                        f"{lang_code}</td>"
                    )
                xhtml += "<td></td>" * pad + "</tr>"

                # 圖片行
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

    # ── 位圖數字（16 欄，補滿最後一行）─────────────────────
    def _generate_nu_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """生成位圖數字表，每行 NU_COLS 欄，最後一行補空格"""
        if not groups:
            return ""

        cols  = NU_COLS
        xhtml = f"<h3>{title}</h3>"

        for group_key, assets in sorted(groups.items()):
            xhtml += (
                f"<h4>組別：{_escape_xml(group_key)}</h4>"
                f"<table><tbody>"
                f"<tr>"
                f"<th colspan='{cols}' style='background:#fffde7; text-align:left;'>"
                f"備註說明：</th>"
                f"</tr>"
            )

            sorted_assets = sorted(assets, key=lambda x: x['name'])

            for i in range(0, len(sorted_assets), cols):
                chunk = sorted_assets[i:i + cols]
                pad   = cols - len(chunk)

                # 數字標籤行
                xhtml += "<tr>"
                for asset in chunk:
                    label = asset['name'].rsplit('.', 1)[0].split('_')[-1]
                    xhtml += (
                        f"<td style='background:#f1f3f5; font-size:10px; text-align:center;'>"
                        f"{_escape_xml(label)}</td>"
                    )
                xhtml += "<td></td>" * pad + "</tr>"

                # 圖片行
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
