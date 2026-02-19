"""
Slot Game 資源分類器

職責：純分類，不做任何檔名驗證。
驗證邏輯統一由 validator.py 負責。

檔名格式：{sceneModule}_{type}_{name}_{visualState}[_{languageBitmapFont}]
"""

from typing import Dict, Any, Tuple, Optional, List, Set


_NU_TYPE    = 'nu'
_EXTENSIONS = ('.png', '.jpg', '.jpeg')

# 預設語言代碼（與 game_dict.yaml language 欄位一致）
# validator 啟用時由 sync_engine 傳入 DictLoader.language 覆蓋，確保單一來源
_DEFAULT_LANG_CODES: Set[str] = {
    'cn', 'cm', 'jp', 'kr', 'th', 'id', 'vn',
    'es', 'pt', 'tr', 'mm', 'bd', 'en'
}

# 預設 NU 數字/符號集合（與 game_dict.yaml bitmap_font 數字部分一致）
# validator 啟用時由 sync_engine 傳入 DictLoader.bitmap_font 覆蓋，確保單一來源
_DEFAULT_BITMAP_FONT_DIGITS: Set[str] = {'0','1','2','3','4','5','6','7','8','9'}


class SlotGameClassifier:
    """
    Slot Game 資源分類器。

    嚴格模式：各欄位值必須符合 yaml 字典定義才能正確分類，
    不符合的檔案落到 'unknown' 分類，由 page_builder 集中顯示。

    classify() 回傳 (category, group_key)：
      category  : layout / main / free / loading /
                  multi_main / multi_free / multi_loading /
                  nu_main / nu_free / nu_loading /
                  unknown
      group_key : 多國語系與 NU 群組的識別鍵（其他為 None）
                  格式為 sceneModule_type_name_visualState（前 4 欄）
    """

    def __init__(
        self,
        lang_codes: Optional[Set[str]] = None,
        bitmap_font_digits: Optional[Set[str]] = None,
        scene_modules: Optional[Set[str]] = None,
    ):
        """
        Args:
            lang_codes:         語言代碼集合，建議從 DictLoader.language 取得。
            bitmap_font_digits: NU 數字集合，建議從 DictLoader.bitmap_font 取得。
            scene_modules:      場景模組集合，建議從 DictLoader.scene_module 取得。
                                三者未傳入時使用預設值。
        """
        self._lang_codes = (
            {c.lower() for c in lang_codes}
            if lang_codes is not None
            else _DEFAULT_LANG_CODES
        )
        self._bitmap_font_digits = (
            {str(v) for v in bitmap_font_digits}
            if bitmap_font_digits is not None
            else _DEFAULT_BITMAP_FONT_DIGITS
        )
        self._scene_modules = (
            {s.lower() for s in scene_modules}
            if scene_modules is not None
            else None  # None 表示不做 sceneModule 驗證（向下相容）
        )

    def classify(self, asset: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        filename = asset['name']
        parts    = self._parse(filename)

        # 1. Layout
        if 'layout' in filename.lower():
            return 'layout', None

        # 2. 欄位不足 → 退化為 scene 分類（classifier 不做驗證，由 validator 負責標記）
        if len(parts) < 4:
            scene = parts[0].lower() if parts else 'base'
            return self._scene_suffix(scene), None

        scene = parts[0].lower()

        # 3. sceneModule 驗證（有傳入字典時才驗證，不符合退化為 main 讓 validator 標記）
        if self._scene_modules is not None and scene not in self._scene_modules:
            return 'unknown', None  # sceneModule 完全不認識才是 unknown

        # 4. NU 數字組（嚴格）：type=nu 且第 5 欄在 bitmap_font
        if parts[1].lower() == _NU_TYPE:
            if len(parts) >= 5 and parts[4] in self._bitmap_font_digits:
                group_key = '_'.join(parts[:4])
                return f'nu_{self._scene_suffix(scene)}', group_key
            # type=nu 但不符合 NU 規範 → 退化為 scene 分類（由 validator 標記異常）
            return self._scene_suffix(scene), None

        # 5. 多國語系：第 5 欄在 language
        if len(parts) >= 5 and parts[4].lower() in self._lang_codes:
            group_key = '_'.join(parts[:4])
            return f'multi_{self._scene_suffix(scene)}', group_key

        # 6. 一般資源：恰好 4 欄
        if len(parts) == 4:
            return self._scene_suffix(scene), None

        # 7. 其他（5 欄但第 5 欄既不是語系也不是數字）→ 退化為一般資源（由 validator 標記）
        return self._scene_suffix(scene), None

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
            'unknown':        [],  # 命名異常：無法歸類的檔案
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
                categories[category].setdefault(group_key, [])\
                    if isinstance(categories[category], dict) else None
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

