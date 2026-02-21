"""
Slot Game 資源分類器

職責：純分類，不做任何檔名驗證。
驗證邏輯統一由 validator.py 負責。

檔名格式：{sceneModule}_{type}_{name}_{visualState}[_{languageBitmapFont}]
"""

from typing import Dict, Any, Tuple, Optional, List, Set


_NU_TYPE    = 'nu'
_EXTENSIONS = ('.png', '.jpg', '.jpeg')
# NU visualState 位移偵測用（單字元數字）
_BITMAP_FONT_DIGITS = {'0','1','2','3','4','5','6','7','8','9'}

# 預設語言代碼（與 game_dict.yaml language 欄位一致）
# validator 啟用時由 sync_engine 傳入 DictLoader.language 覆蓋，確保單一來源
_DEFAULT_LANG_CODES: Set[str] = {
    'cn', 'cm', 'jp', 'kr', 'th', 'id', 'vn',
    'es', 'pt', 'tr', 'mm', 'bd', 'en'
}


class SlotGameClassifier:
    """
    Slot Game 資源分類器。

    語言代碼集合從外部傳入（由 DictLoader.language 提供），
    避免與 validator.py 維護兩份相同資料。
    未傳入時使用 _DEFAULT_LANG_CODES，確保向下相容。

    classify() 回傳 (category, group_key)：
      category  : layout / main / free / loading /
                  multi_main / multi_free / multi_loading /
                  nu_main / nu_free / nu_loading
      group_key : 多國語系與 NU 群組的識別鍵（其他為 None）
                  格式為 sceneModule_type_name_visualState（前 4 欄）
    """

    def __init__(self, lang_codes: Optional[Set[str]] = None):
        """
        Args:
            lang_codes: 語言代碼集合，建議從 DictLoader.language 取得。
                        未傳入時使用預設值 _DEFAULT_LANG_CODES。
        """
        self._lang_codes = (
            {c.lower() for c in lang_codes}
            if lang_codes is not None
            else _DEFAULT_LANG_CODES
        )

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
        if len(parts) >= 5 and parts[4].lower() in self._lang_codes:
            group_key = '_'.join(parts[:4])
            return f'multi_{self._scene_suffix(scene)}', group_key

        # 3. NU 數字組：type == 'nu'
        if parts[1].lower() == _NU_TYPE:
            # parts[3] 開頭是數字 → 缺 visualState（含雲端衝突複本如 "4 (1)"）
            # 退化為一般分類，讓 validator 顯示警告
            if len(parts) < 5 and parts[3][:1] in _BITMAP_FONT_DIGITS:
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
                'orig_h': file_data['height'],
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