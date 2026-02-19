"""
Slot Game 資源分類器

職責：純分類，不做任何檔名驗證。
驗證邏輯統一由 validator.py 負責。

檔名格式：{sceneModule}_{type}_{name}_{visualState}[_{languageBitmapFont}]
"""

from typing import Dict, Any, Tuple, Optional, List


# 多國語系語言代碼（與 DictLoader.language 一致，此處作為分類判斷用）
_LANG_CODES = {
    'cn', 'cm', 'jp', 'kr', 'th', 'id', 'vn',
    'es', 'pt', 'tr', 'mm', 'bd', 'en'
}
_NU_TYPE    = 'nu'
_EXTENSIONS = ('.png', '.jpg', '.jpeg')
# NU visualState 位移偵測用（單字元數字）
_BITMAP_FONT_DIGITS = {'0','1','2','3','4','5','6','7','8','9'}


class SlotGameClassifier:
    """
    Slot Game 資源分類器。

    classify() 回傳 (category, group_key)：
      category  : layout / main / free / loading /
                  multi_main / multi_free / multi_loading /
                  nu_main / nu_free / nu_loading
      group_key : 多國語系與 NU 群組的識別鍵（其他為 None）
                  格式為 sceneModule_type_name_visualState（前 4 欄）
    """

    def classify(self, asset: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        filename = asset['name']
        parts    = self._parse(filename)

        # 1. Layout
        if 'layout' in filename.lower():
            return 'layout', None

        # 欄位不足 → 依 sceneModule 做基本分類
        if len(parts) < 4:
            return self._by_scene(parts[0].lower() if parts else ''), None

        scene = parts[0].lower()

        # 2. 多國語系：index 4 是語言代碼
        if len(parts) >= 5 and parts[4].lower() in _LANG_CODES:
            group_key = '_'.join(parts[:4])
            return f'multi_{self._scene_suffix(scene)}', group_key

        # 3. NU 數字組：type == 'nu'
        if parts[1].lower() == _NU_TYPE:
            # parts[3] 是數字 → 缺 visualState，退化為一般分類讓 validator 顯示警告
            if len(parts) < 5 and parts[3] in _BITMAP_FONT_DIGITS:
                return self._by_scene(scene), None
            group_key = '_'.join(parts[:4])
            return f'nu_{self._scene_suffix(scene)}', group_key

        # 4. 一般資源
        return self._by_scene(scene), None

    def organize_assets(
        self,
        files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        categories = {
            'layout':         [],
            'main':           [],
            'free':           [],
            'loading':        [],
            'multi_main':     {},
            'multi_free':     {},
            'multi_loading':  {},
            'nu_main':        {},
            'nu_free':        {},
            'nu_loading':     {},
        }

        for filename, file_data in files.items():
            asset = {
                'name':   filename,
                'size':   file_data['size'],
                'orig_w': file_data['width'],
            }
            category, group_key = self.classify(asset)

            if group_key:
                categories[category].setdefault(group_key, [])
                categories[category][group_key].append(asset)
            else:
                categories[category].append(asset)

        return categories

    @staticmethod
    def _parse(filename: str) -> List[str]:
        stem = filename
        for ext in _EXTENSIONS:
            if filename.lower().endswith(ext):
                stem = filename[:-len(ext)]
                break
        return stem.split('_')

    @staticmethod
    def _scene_suffix(scene: str) -> str:
        if scene == 'free':    return 'free'
        if scene == 'loading': return 'loading'
        return 'main'

    @staticmethod
    def _by_scene(scene: str) -> str:
        if scene == 'free':    return 'free'
        if scene == 'loading': return 'loading'
        return 'main'
