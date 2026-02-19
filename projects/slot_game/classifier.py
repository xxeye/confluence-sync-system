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

    # 多國語系白名單
    LANG_WHITELIST = [
        'cn', 'cm', 'jp', 'kr', 'th', 'id', 'vn',
        'es', 'pt', 'tr', 'mm', 'bd', 'en'
    ]

    # NU type 識別
    NU_TYPE = 'nu'

    def classify(self, asset: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        分類單個資源

        Returns:
            (分類名稱, 群組鍵)
        """
        filename = asset['name']
        parts = self._parse_filename(filename)

        # 1. Layout
        if 'layout' in filename.lower():
            return 'layout', None

        # 欄位不足（< 4）→ 基本分類，警告由 validate_filename 另外提供
        if len(parts) < 4:
            scene = parts[0].lower() if parts else ''
            if scene == 'free':
                return 'free', None
            elif scene == 'loading':
                return 'loading', None
            else:
                return 'main', None

        scene = parts[0].lower()

        # 2. 多國語系：index 4 在語系白名單
        if len(parts) >= 5:
            lang_tag = parts[4].lower()
            if lang_tag in self.LANG_WHITELIST:
                group_key = '_'.join(parts[:4])
                if scene == 'free':
                    return 'multi_free', group_key
                elif scene == 'loading':
                    return 'multi_loading', group_key
                else:
                    return 'multi_main', group_key

        # 3. NU 數字組：type == 'nu'
        if parts[1].lower() == self.NU_TYPE:
            group_key = '_'.join(parts[:4])   # 含 visualState
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

    def validate_filename(self, filename: str) -> Optional[str]:
        """
        驗證檔名欄位數量，回傳警告訊息。

        檢查三種異常：
        1. 一般圖片欄位不足（parts < 4）
           → 回傳 "⚠️ 欄位不足（只有 N 欄，需要 4 欄）"

        2. 多國語系欄位不足：type 非 nu、非 layout，
           且 parts[2] 或 parts[3] 本身是語系代碼
           → 代表語系代碼位移，回傳 "⚠️ 疑似多國語系檔案，欄位不足"

        3. NU 欄位不足：type == nu，但 parts < 5（缺 languageBitmapFont）
           或 parts == 4（visualState 位置被數字佔據）
           → 回傳 "⚠️ 疑似 NU 數字組檔案，欄位不足"

        無問題則回傳 None。
        """
        parts = self._parse_filename(filename)

        # Layout 不驗證
        if 'layout' in filename.lower():
            return None

        # --- 情況 1：一般圖片欄位不足 ---
        if len(parts) < 4:
            # 先判斷是否可能是多國或 NU（讓情況 2/3 優先提示）
            if len(parts) >= 2:
                if parts[1].lower() == self.NU_TYPE:
                    return '⚠️ 疑似 NU 數字組檔案，欄位不足'
                # parts[2] 或 parts[3] 是語系代碼 → 多國位移
                for i in range(2, min(len(parts), 4)):
                    if parts[i].lower() in self.LANG_WHITELIST:
                        return '⚠️ 疑似多國語系檔案，欄位不足'
            return f'⚠️ 欄位不足（只有 {len(parts)} 欄，需要 4 欄）'

        # --- 情況 2：多國語系欄位位移 ---
        # 正常多國在 index 4；若 index 3 或 index 2 是語系代碼則代表缺欄
        if parts[1].lower() != self.NU_TYPE:
            # index 3 是語系代碼 → 缺 visualState
            if parts[3].lower() in self.LANG_WHITELIST:
                return '⚠️ 疑似多國語系檔案，欄位不足（語系代碼出現在第 4 欄，應在第 5 欄）'
            # index 2 是語系代碼 → 缺 name + visualState
            if len(parts) >= 3 and parts[2].lower() in self.LANG_WHITELIST:
                return '⚠️ 疑似多國語系檔案，欄位不足（語系代碼出現在第 3 欄，應在第 5 欄）'

        # --- 情況 3：NU 欄位不足 ---
        if parts[1].lower() == self.NU_TYPE:
            # 正常 NU 有 5 欄；只有 4 欄代表缺 languageBitmapFont 或 visualState
            if len(parts) < 5:
                return '⚠️ 疑似 NU 數字組檔案，欄位不足（需要 5 欄）'

        return None

    def _parse_filename(self, filename: str) -> list:
        """解析檔名為欄位列表"""
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
        將所有資源組織到分類結構，同時附上驗證警告。

        asset 字典會新增 'warning' 欄位：
            None      → 無問題
            str       → 警告訊息，供 page_builder 渲染
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
                'orig_w': file_data['width'],
                'warning': self.validate_filename(filename),  # ← 新增警告欄位
            }

            category, group_key = self.classify(asset)

            if group_key:
                categories[category].setdefault(group_key, [])
                categories[category][group_key].append(asset)
            else:
                categories[category].append(asset)

        return categories
