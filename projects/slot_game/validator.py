"""
Slot Game 檔名驗證器

對應 Google Sheets CHECK_NAMING_RULES(A, B, C, D, E) 的 6 條規則：
  規則 1：name 欄不得為空
  規則 2：任一欄位值內不得包含底線
  規則 3：name 不得與其他欄位已定義字詞重複（exact match）
  規則 4：name 不得是禁詞（完整比對，不分大小寫）
  規則 5：type=nu 時，第 5 欄必須是 bitmap_font（數字規範）
  規則 6：type≠nu 時，第 5 欄若有值必須是 language（語系規範）

欄位數量不足的警告也統一在此處處理。
字典資料從 config 指定的 yaml 檔載入，方便定期從 Google Sheets 更新。
"""

import yaml
from pathlib import Path
from typing import Optional, Set, List


# ── 常數 ──────────────────────────────────────────────────────
_EXTENSIONS = ('.png', '.jpg', '.jpeg')


class DictLoader:
    """
    從 yaml 字典檔載入所有命名範圍資料。

    對應 Google Sheets 命名範圍：
      sceneModule / type / Named / State /
      Language / number(bitmap_font) / ForbiddenWords / Emptyoptions
    """

    def __init__(self, dict_file: str):
        """
        Args:
            dict_file: yaml 字典檔路徑（來自 config validator.dict_file）
        
        Raises:
            FileNotFoundError: 字典檔不存在
            ValueError: yaml 格式錯誤或缺少必要欄位
        """
        path = Path(dict_file)
        if not path.exists():
            raise FileNotFoundError(f"[DictLoader] 字典檔不存在：{dict_file}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self.scene_module: Set[str]  = self._load_set(data, 'scene_module')
        self.type_:        Set[str]  = self._load_set(data, 'type')
        self.named:        Set[str]  = self._load_set(data, 'named')
        self.state:        Set[str]  = self._load_set(data, 'state')
        self.language:     Set[str]  = self._load_set(data, 'language')
        self.bitmap_font:  Set[str]  = self._load_set(data, 'bitmap_font')

        # languageBitmapFont = Language ∪ bitmap_font（第 5 欄驗證總集）
        self.language_bitmap_font: Set[str] = self.language | self.bitmap_font

        # 禁詞統一轉小寫後比對
        self.forbidden_words: Set[str] = {
            str(w).lower()
            for w in data.get('forbidden_words', [])
            if w is not None
        }

        # 空值標記（下拉選單留空選項的實際儲存值）
        self.empty_option: str = str(data.get('empty_option', ''))

        # 規則 3 的重複比對集合：sceneModule ∪ type ∪ bitmap_font ∪ State ∪ Language
        # named 白名單本身就是合法的 name 值，不納入重複比對
        # 對應 Google Sheets：COUNTIF(sceneModule/type/number/State/Language)
        self.reserved_names: Set[str] = (
            self.scene_module
            | self.type_
            | self.bitmap_font
            | self.state
            | self.language
        )

    @staticmethod
    def _load_set(data: dict, key: str) -> Set[str]:
        """讀取 yaml list 轉為字串 set，值為 None 時略過"""
        return {
            str(v)
            for v in data.get(key, [])
            if v is not None
        }


class FilenameValidator:
    """
    Slot Game 檔名驗證器。

    對應 Google Sheets CHECK_NAMING_RULES，依序執行 6 條規則，
    前置另有欄位數量檢查。

    使用方式：
        loader = DictLoader("config/slot_game_dict.yaml")
        validator = FilenameValidator(loader)
        warning = validator.validate("base_btn_start_normal_cn.png")
        # None = 通過，str = 警告訊息
    """

    def __init__(self, dict_loader: DictLoader):
        self.d = dict_loader

    def validate(self, filename: str) -> Optional[str]:
        """
        驗證單一檔名，回傳第一個命中的警告訊息，通過則回傳 None。

        Args:
            filename: 含副檔名的檔名，如 base_btn_start_normal_cn.png

        Returns:
            警告訊息字串，或 None（通過）
        """
        parts = self._parse(filename)

        # ── 前置：欄位數量檢查 ────────────────────────────────
        field_warning = self._check_field_count(filename, parts)
        if field_warning:
            return field_warning

        # ── 取得各欄位值 ──────────────────────────────────────
        A = parts[0]   # sceneModule
        B = parts[1]   # type
        C = parts[2]   # name
        D = parts[3]   # visualState
        E = parts[4] if len(parts) >= 5 else self.d.empty_option

        # ── 6 條語意規則（依優先順序，第一個命中即回傳）──────────
        return (
            self._rule1_name_empty(C)
            or self._rule2_underscore(A, B, C, D, E)
            or self._rule3_name_duplicate(C)
            or self._rule4_forbidden(C)
            or self._rule5_nu_suffix(B, E)
            or self._rule6_lang_suffix(B, E)
        )

    # ── 前置：欄位數量 ────────────────────────────────────────
    def _check_field_count(self, filename: str, parts: List[str]) -> Optional[str]:
        """
        欄位數量前置檢查，同時偵測疑似多國/NU 被誤放欄位。

        正常檔名：4 欄（一般）或 5 欄（多國/NU）
        """
        if 'layout' in filename.lower():
            return None   # layout 不驗證

        n = len(parts)

        if n < 4:
            # 檢查是否有 type=nu → 疑似 NU
            if n >= 2 and parts[1].lower() == 'nu':
                return '⚠️ 疑似 NU 數字組檔案，欄位不足（需要 5 欄）'
            # 檢查 index 2~3 是否有語系代碼 → 疑似多國
            for i in range(2, min(n, 4)):
                if parts[i] in self.d.language:
                    return '⚠️ 疑似多國語系檔案，欄位不足（語系代碼位置錯誤）'
            return f'⚠️ 欄位不足（只有 {n} 欄，需要 4 欄）'

        if n >= 4:
            # NU：parts[3]（visualState 位置）是 bitmap_font 值
            # → 代表缺少 visualState，數字直接跑到第 4 欄
            # 例：autostart_nu_auto_0.png（應為 autostart_nu_auto_na_0.png）
            if parts[1].lower() == 'nu' and parts[3] in self.d.bitmap_font:
                return '⚠️ 疑似 NU 數字組檔案，欄位不足（缺少 visualState，數字出現在第 4 欄）'

            # 多國：語系代碼出現在 index 3（應在 index 4）→ 缺 visualState
            if parts[3] in self.d.language:
                return '⚠️ 疑似多國語系檔案，欄位不足（語系代碼出現在第 4 欄，應在第 5 欄）'

        if n >= 2 and parts[1].lower() == 'nu' and n < 5:
            return '⚠️ 疑似 NU 數字組檔案，欄位不足（需要 5 欄）'

        return None

    # ── 規則 1：name 不得為空 ─────────────────────────────────
    @staticmethod
    def _rule1_name_empty(name: str) -> Optional[str]:
        if not name or not name.strip():
            return '⚠️ 命名不能為空'
        return None

    # ── 規則 2：欄位值內不得包含底線 ─────────────────────────
    @staticmethod
    def _rule2_underscore(*fields: str) -> Optional[str]:
        for f in fields:
            if f and '_' in f:
                return '⚠️ 格式錯誤：各區塊內不得包含底線 [_] 符號'
        return None

    # ── 規則 3：name 不得與字典已定義字詞重複（exact match）────
    def _rule3_name_duplicate(self, name: str) -> Optional[str]:
        if name in self.d.reserved_names:
            return '⚠️ [命名] 不可與其他區塊已定義字詞重複'
        return None

    # ── 規則 4：name 不得是禁詞（完整比對，不分大小寫）──────────
    def _rule4_forbidden(self, name: str) -> Optional[str]:
        if name.lower() in self.d.forbidden_words:
            return '⚠️ [命名] 包含禁詞'
        return None

    # ── 規則 5：type=nu 時，第 5 欄必須符合數字規範 ───────────
    def _rule5_nu_suffix(self, type_: str, e: str) -> Optional[str]:
        if type_.lower() == 'nu':
            # E 為空值標記或不在 bitmap_font 中 → 不合規
            if e == self.d.empty_option or e not in self.d.bitmap_font:
                return '⚠️ [nu] 須符合數字規範，不得使用語系尾綴取名'
        return None

    # ── 規則 6：type≠nu 時，第 5 欄若有值必須是語系代碼 ─────────
    def _rule6_lang_suffix(self, type_: str, e: str) -> Optional[str]:
        if type_.lower() != 'nu':
            # E 有值（非空值標記）且不在 language 中 → 不合規
            if e and e != self.d.empty_option and e not in self.d.language:
                return '⚠️ 若為多語系物件須符合規範，不得使用數字尾綴取名'
        return None

    # ── 工具：解析檔名 ────────────────────────────────────────
    @staticmethod
    def _parse(filename: str) -> List[str]:
        """移除副檔名後以底線分割"""
        stem = filename
        for ext in _EXTENSIONS:
            if filename.lower().endswith(ext):
                stem = filename[:-len(ext)]
                break
        return stem.split('_')
