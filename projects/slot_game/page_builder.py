"""
Slot Game 頁面建構器
生成 Confluence XHTML 格式的頁面內容
"""

from typing import Dict, List, Any


class SlotGamePageBuilder:
    """Slot Game 頁面建構器"""
    
    @staticmethod
    def get_ac_image_tag(filename: str, img_w: int, target_max: int) -> str:
        """
        生成 Confluence 專用圖片標籤
        
        Args:
            filename: 檔案名稱
            img_w: 原始寬度
            target_max: 最大顯示寬度
        
        Returns:
            Confluence 圖片標籤
        """
        final_w = min(img_w, target_max)
        return f'<ac:image ac:width="{final_w}"><ri:attachment ri:filename="{filename}" /></ac:image>'
    
    def assemble(
        self,
        categories: Dict[str, Any],
        history: List[Dict[str, str]]
    ) -> str:
        """
        組裝完整頁面內容
        
        Args:
            categories: 分類結果
            history: 版本歷史
        
        Returns:
            完整的 XHTML 內容
        """
        xhtml = '<p><ac:structured-macro ac:name="toc" /></p>'  # 自動目錄
        
        # 版本歷史
        xhtml += self._generate_history_table(history)
        
        # Layout 專案示意圖
        xhtml += self._generate_layout_grid(categories['layout'])
        
        # 主遊戲資源 (Main)
        xhtml += self._generate_normal_table(
            "🏠 2. 主遊戲 (Main Game) 資源清單",
            categories['main']
        )
        xhtml += self._generate_multi_grid(
            "🌏 主遊戲：多國語系對照",
            categories['multi_main']
        )
        xhtml += self._generate_nu_grid(
            "🔢 主遊戲：位圖數字 (NU)",
            categories['nu_main']
        )
        
        # 免費遊戲資源 (Free)
        xhtml += self._generate_normal_table(
            "🎁 3. 免費遊戲 (Free Game) 資源清單",
            categories['free']
        )
        xhtml += self._generate_multi_grid(
            "🌏 免費遊戲：多國語系對照",
            categories['multi_free']
        )
        xhtml += self._generate_nu_grid(
            "🔢 免費遊戲：位圖數字 (NU)",
            categories['nu_free']
        )
        
        # 載入資源 (Loading)
        xhtml += self._generate_normal_table(
            "⏳ 4. 載入畫面 (Loading) 資源清單",
            categories['loading']
        )
        xhtml += self._generate_multi_grid(
            "🌏 載入畫面：多國語系對照",
            categories['multi_loading']
        )
        xhtml += self._generate_nu_grid(
            "🔢 載入畫面：位圖數字 (NU)",
            categories['nu_loading']
        )
        
        return xhtml
    
    def _generate_history_table(self, history: List[Dict[str, str]]) -> str:
        """生成版本更新說明表格"""
        if not history:
            return ""
        
        xhtml = (
            "<h2>📝 版本更新說明</h2>"
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
            user_tag = f'<ac:link><ri:user ri:account-id="{h["user_id"]}" /></ac:link>'
            xhtml += (
                f"<tr>"
                f"<td>{h['date']}</td>"
                f"<td>{h['log']}</td>"
                f"<td>{user_tag}</td>"
                f"</tr>"
            )
        
        xhtml += "</tbody></table>"
        return xhtml
    
    def _generate_layout_grid(self, assets: List[Dict[str, Any]]) -> str:
        """生成 Layout 專案示意圖"""
        if not assets:
            return ""
        
        xhtml = "<h2>📐 1. Layout 專案示意圖</h2><table><tbody>"
        sorted_assets = sorted(assets, key=lambda x: x['name'])
        
        # 每行 4 個
        for i in range(0, len(sorted_assets), 4):
            chunk = sorted_assets[i:i + 4]
            
            # 檔名行
            xhtml += "<tr>"
            for asset in chunk:
                xhtml += f"<td style='background:#f1f3f5; font-size:11px; font-weight:bold;'>{asset['name']}</td>"
            xhtml += "</tr>"
            
            # 圖片行
            xhtml += "<tr>"
            for asset in chunk:
                xhtml += f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 250)}</td>"
            xhtml += "</tr>"
        
        xhtml += "</tbody></table>"
        return xhtml
    
    def _generate_normal_table(
        self,
        title: str,
        assets: List[Dict[str, Any]]
    ) -> str:
        """生成一般資源清單表格"""
        if not assets:
            return ""
        
        xhtml = (
            f"<h2>{title}</h2>"
            "<table>"
            "<thead>"
            "<tr><th>預覽</th><th>名稱</th><th>尺寸</th></tr>"
            "</thead>"
            "<tbody>"
        )
        
        for asset in sorted(assets, key=lambda x: x['name']):
            xhtml += (
                f"<tr>"
                f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 120)}</td>"
                f"<td>{asset['name']}</td>"
                f"<td>{asset['size']}</td>"
                f"</tr>"
            )
        
        xhtml += "</tbody></table>"
        return xhtml
    
    def _generate_multi_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """生成多國語系對照資源"""
        if not groups:
            return ""
        
        xhtml = f"<h3>{title}</h3>"
        
        for group_key, assets in sorted(groups.items()):
            xhtml += (
                f'<p style="font-size: 16px; font-weight: bold; margin-top: 20px;">'
                f'組別：{group_key}_{{language}}'
                f'</p>'
                '<table><tbody>'
            )
            
            sorted_assets = sorted(assets, key=lambda x: x['name'])
            
            # 每行 7 個
            for i in range(0, len(sorted_assets), 7):
                chunk = sorted_assets[i:i + 7]
                
                # 語系標籤行
                xhtml += "<tr>"
                for asset in chunk:
                    lang_code = asset['name'].split('_')[4].upper()
                    xhtml += f"<td style='background:#f1f3f5; font-size:10px;'>{lang_code}</td>"
                xhtml += "</tr>"
                
                # 圖片行
                xhtml += "<tr>"
                for asset in chunk:
                    xhtml += f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 100)}</td>"
                xhtml += "</tr>"
            
            xhtml += "</tbody></table>"
        
        return xhtml
    
    def _generate_nu_grid(
        self,
        title: str,
        groups: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """生成位圖數字資源"""
        if not groups:
            return ""
        
        xhtml = f"<h3>{title}</h3>"
        
        for group_key, assets in sorted(groups.items()):
            xhtml += (
                f"<h4>組別：{group_key}</h4>"
                "<table><tbody>"
                "<tr><th colspan='8' style='background:#fffde7; text-align:left;'>備註說明：</th></tr>"
            )
            
            sorted_assets = sorted(assets, key=lambda x: x['name'])
            
            # 每行 8 個
            for i in range(0, len(sorted_assets), 8):
                chunk = sorted_assets[i:i + 8]
                
                # 數字標籤行
                xhtml += "<tr>"
                for asset in chunk:
                    # 取最後一個部分（移除副檔名）
                    label = asset['name'].split('_')[-1].replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
                    xhtml += f"<td style='background:#f1f3f5; font-size:10px;'>{label}</td>"
                xhtml += "</tr>"
                
                # 圖片行
                xhtml += "<tr>"
                for asset in chunk:
                    xhtml += f"<td>{self.get_ac_image_tag(asset['name'], asset['orig_w'], 80)}</td>"
                xhtml += "</tr>"
            
            xhtml += "</tbody></table>"
        
        return xhtml
