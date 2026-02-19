"""
Slot Game 資源分類器
根據檔名規則將資源分類到不同類別

檔名格式：{sceneModule}_{type}_{name}_{visualState}[_{languageBitmapFont}]
  必填欄位：sceneModule(0) / type(1) / name(2) / visualState(3)
  選填欄位：languageBitmapFont(4)
"""

from typing import Dict, Any, Tuple, Optional


class SlotGameClassifier:
    """Slot Game 資源分類器"""

    # 多國語系白名單（languageBitmapFont 欄位為語系代碼時）
    LANG_WHITELIST = [
        'cn', 'cm', 'jp', 'kr', 'th', 'id', 'vn',
        'es', 'pt', 'tr', 'mm', 'bd', 'en'
    ]

    def classify(self, asset: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        分類單個資源

        Args:
            asset: 資源字典，包含 name, size, width, height 等

        Returns:
            (分類名稱, 群組鍵)
            - 分類名稱: layout, main, free, loading,
                       multi_main, multi_free, multi_loading,
                       nu_main, nu_free, nu_loading
            - 群組鍵: 多國語系與 NU 數字組使用，其他為 None

        檔名解析範例：
            base_nu_win_na_0.png
              parts[0]=base  parts[1]=nu  parts[2]=win  parts[3]=na  parts[4]=0
              → nu_main，group_key = "base_nu_win_na"（含 visualState）

            base_text_paytableTitle_normal_cn.png
              parts[0]=base  parts[1]=text  parts[2]=paytableTitle
              parts[3]=normal  parts[4]=cn
              → multi_main，group_key = "base_text_paytableTitle_normal"
        """
        filename = asset['name']
        parts = self._parse_filename(filename)

        # 1. Layout 判斷（檔名含 layout 關鍵字）
        if 'layout' in filename.lower():
            return 'layout', None

        # 需要至少 4 欄才能正確解析
        if len(parts) < 4:
            # 欄位不足，依 sceneModule 做基本分類，不分群組
            scene = parts[0].lower() if parts else ''
            if scene == 'free':
                return 'free', None
            elif scene == 'loading':
                return 'loading', None
            else:
                return 'main', None

        scene = parts[0].lower()  # sceneModule
        # type = parts[1]
        # name = parts[2]
        # visualState = parts[3]

        # 2. 多國語系判斷
        #    條件：有第 5 欄（index 4）且值在語系白名單
        #    group_key = sceneModule_type_name_visualState（前 4 欄）
        if len(parts) >= 5:
            lang_tag = parts[4].lower()
            if lang_tag in self.LANG_WHITELIST:
                group_key = "_".join(parts[:4])
                if scene == 'free':
                    return 'multi_free', group_key
                elif scene == 'loading':
                    return 'multi_loading', group_key
                else:
                    return 'multi_main', group_key

        # 3. 位圖數字（NU）判斷
        #    條件：type（parts[1]）== 'nu'
        #    group_key = sceneModule_type_name_visualState（前 4 欄，含 visualState）
        #    ✅ 修正：舊版只取 parts[:3]，漏掉了 visualState（parts[3]）
        if parts[1].lower() == 'nu':
            group_key = "_".join(parts[:4])   # 含 visualState
            if scene == 'free':
                return 'nu_free', group_key
            elif scene == 'loading':
                return 'nu_loading', group_key
            else:
                return 'nu_main', group_key

        # 4. 一般資源
        if scene == 'free':
            return 'free', None
        elif scene == 'loading':
            return 'loading', None
        else:
            return 'main', None

    def _parse_filename(self, filename: str) -> list:
        """解析檔名為欄位列表（去除副檔名後用底線分割）"""
        name_without_ext = filename
        for ext in ['.png', '.jpg', '.jpeg']:
            if filename.lower().endswith(ext):
                name_without_ext = filename[:-len(ext)]
                break
        return name_without_ext.split('_')

    def organize_assets(
        self,
        files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        將所有資源組織到分類結構

        Args:
            files: 檔案字典 {filename: {path, hash, width, height, size}}

        Returns:
            分類結果字典
        """
        categories = {
            'layout': [],
            'main': [],
            'free': [],
            'loading': [],
            'multi_main': {},
            'multi_free': {},
            'multi_loading': {},
            'nu_main': {},
            'nu_free': {},
            'nu_loading': {}
        }

        for filename, file_data in files.items():
            asset = {
                'name': filename,
                'size': file_data['size'],
                'orig_w': file_data['width']
            }

            category, group_key = self.classify(asset)

            if group_key:
                categories[category].setdefault(group_key, [])
                categories[category][group_key].append(asset)
            else:
                categories[category].append(asset)

        return categories
