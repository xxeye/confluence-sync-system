"""
Slot Game 檔名驗證器

執行順序：
  0. 前置過濾：系統/雲端產生的異常檔名（衝突複本、暫存、空白字元）
  1. 前置檢查：欄位數量不足
  2-7. 語意規則：對應 Google Sheets CHECK_NAMING_RULES 的 6 條規則
"""

import re
import yaml
from pathlib import Path
from typing import Optional, Set, List, Tuple


_EXTENSIONS = ('.png', '.jpg', '.jpeg')


class DictLoader:
    """從 yaml 字典檔載入所有命名範圍資料"""

    def __init__(self, dict_file: str):
        path = Path(dict_file)
        if not path.exists():
            raise FileNotFoundError(f"[DictLoader] 字典檔不存在：{dict_file}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self.scene_module: Set[str] = self._load_set(data, 'scene_module')
        self.type_:        Set[str] = self._load_set(data, 'type')
        self.named:        Set[str] = self._load_set(data, 'named')
        self.state:        Set[str] = self._load_set(data, 'state')
        self.language:     Set[str] = self._load_set(data, 'language')
        self.bitmap_font:  Set[str] = self._load_set(data, 'bitmap_font')

        self.language_bitmap_font: Set[str] = self.language | self.bitmap_font

        self.forbidden_words: Set[str] = {
            str(w).lower()
            for w in data.get('forbidden_words', [])
            if w is not None
        }

        self.empty_option: str = str(data.get('empty_option', ''))

        # 規則 3 比對集合（named 白名單不納入）
        self.reserved_names: Set[str] = (
            self.scene_module | self.type_ | self.bitmap_font
            | self.state | self.language
        )

    @staticmethod
    def _load_set(data: dict, key: str) -> Set[str]:
        return {str(v) for v in data.get(key, []) if v is not None}


class FilenameValidator:
    """
    Slot Game 檔名驗證器

    validate(filename) → Optional[str]
        None  = 通過
        str   = 第一個命中的警告訊息

    validate_group_key(group_key) → Optional[str]
        用於 NU / 多國語系群組標題的異常偵測
    """

    def __init__(self, dict_loader: DictLoader):
        self.d = dict_loader

    # ── 公開介面 ──────────────────────────────────────────────

    def validate(self, filename: str) -> Optional[str]:
        """驗證單一檔名"""
        # layout 不驗證（格式自由，不適用命名規範）
        if 'layout' in filename.lower():
            return None

        # 0. 前置過濾：系統/雲端異常檔名（最優先）
        system_warn = self._check_system_filename(filename)
        if system_warn:
            return system_warn

        parts = self._parse(filename)

        # 1. 欄位數量檢查（不足時直接回傳，避免後續 index 錯誤）
        field_warn = self._check_field_count(filename, parts)
        if field_warn:
            return field_warn

        # 欄位數量已確認 >= 4，安全取值
        A = parts[0]
        B = parts[1]
        C = parts[2]
        D = parts[3]
        E = parts[4] if len(parts) >= 5 else self.d.empty_option

        return (
            self._rule1_name_empty(C)
            or self._rule2_underscore(A, B, C, D, E)
            or self._rule3_name_duplicate(C)
            or self._rule4_forbidden(C)
            or self._rule5_nu_suffix(B, E)
            or self._rule6_lang_suffix(B, E)
        )

    def validate_all(self, filename: str) -> List[str]:
        """回傳所有違反規則的警告列表（不在第一個命中就停）"""
        warnings = []

        # 0. 前置過濾：系統/雲端異常（獨立於語意規則）
        system_warn = self._check_system_filename(filename)
        if system_warn:
            warnings.append(system_warn)

        # layout 不驗證語意規則
        if 'layout' in filename.lower():
            return warnings

        parts = self._parse(filename)

        # 1. 欄位數量（若有問題，語意規則無法執行，直接回傳）
        field_warn = self._check_field_count(filename, parts)
        if field_warn:
            warnings.append(field_warn)
            return warnings

        # 2–7. 語意規則（全部跑完，收集所有違規）
        A, B, C, D = parts[0], parts[1], parts[2], parts[3]
        E = parts[4] if len(parts) >= 5 else self.d.empty_option

        for check in [
            self._rule1_name_empty(C),
            self._rule2_underscore(A, B, C, D, E),
            self._rule3_name_duplicate(C),
            self._rule4_forbidden(C),
            self._rule5_nu_suffix(B, E),
            self._rule6_lang_suffix(B, E),
        ]:
            if check:
                warnings.append(check)

        return warnings

    def validate_group_key(self, group_key: str) -> Optional[str]:
        """
        驗證 NU / 多國語系的群組鍵是否含有異常字元。
        group_key 是由 classifier 從檔名解析出的前 4 欄，
        若原始檔名含有雲端衝突符號，group_key 也會帶入異常字元。
        """
        # 括號數字：(1), (2), （1）
        if re.search(r'[（(]\s*\d+\s*[）)]', group_key):
            return '⚠️ 組別名稱異常，疑似包含雲端同步衝突檔案'
        # 空白字元
        if ' ' in group_key or '\u3000' in group_key:
            return '⚠️ 組別名稱異常，疑似包含空白字元'
        return None

    # ── 前置過濾 0：系統/雲端異常檔名 ────────────────────────

    # 偵測規則對照表（依序比對，第一個命中即回傳）
    _SYSTEM_PATTERNS: List[Tuple[re.Pattern, str]] = [
        # 雲端同步衝突複本
        (re.compile(r'\s*[（(]\s*\d+\s*[）)]\s*\.', re.IGNORECASE),
         '⚠️ 疑似雲端同步衝突複本（含括號數字）'),
        (re.compile(r'\s*-\s*複製\s*\.', re.IGNORECASE),
         '⚠️ 疑似手動複製檔案（含「複製」字樣）'),
        (re.compile(r'\s*-\s*Copy\s*\.', re.IGNORECASE),
         '⚠️ 疑似手動複製檔案（含「Copy」字樣）'),
        (re.compile(r'[（(][^）)]*衝突副本[^）)]*[）)]', re.IGNORECASE),
         '⚠️ 疑似 Dropbox 衝突複本'),
        # macOS / Office 暫存
        (re.compile(r'^[._]{2}'),
         '⚠️ 疑似 macOS 系統暫存檔（._前綴）'),
        (re.compile(r'^~\$'),
         '⚠️ 疑似 Office 暫存檔（~$前綴）'),
        # 空白字元
        (re.compile(r'^\s|\s(?=\.)'),
         '⚠️ 檔名含有開頭或結尾空白字元'),
        (re.compile(r'_\s|\s_'),
         '⚠️ 檔名欄位間含有空白字元'),
    ]

    @classmethod
    def _check_system_filename(cls, filename: str) -> Optional[str]:
        for pattern, message in cls._SYSTEM_PATTERNS:
            if pattern.search(filename):
                return message
        return None

    # ── 前置檢查 1：欄位數量 ──────────────────────────────────

    def _check_field_count(self, filename: str, parts: List[str]) -> Optional[str]:
        if 'layout' in filename.lower():
            return None

        n = len(parts)

        if n < 4:
            if n >= 2 and parts[1].lower() == 'nu':
                return '⚠️ 疑似 NU 數字組檔案，欄位不足（需要 5 欄）'
            for i in range(2, min(n, 4)):
                if parts[i] in self.d.language:
                    return '⚠️ 疑似多國語系檔案，欄位不足（語系代碼位置錯誤）'
            return f'⚠️ 欄位不足（只有 {n} 欄，需要 4 欄）'

        if n >= 4:
            if parts[1].lower() == 'nu' and parts[3] in self.d.bitmap_font:
                return '⚠️ 疑似 NU 數字組檔案，欄位不足（缺少 visualState，數字出現在第 4 欄）'
            if parts[3] in self.d.language:
                return '⚠️ 疑似多國語系檔案，欄位不足（語系代碼出現在第 4 欄，應在第 5 欄）'

        if n >= 2 and parts[1].lower() == 'nu' and n < 5:
            return '⚠️ 疑似 NU 數字組檔案，欄位不足（需要 5 欄）'

        return None

    # ── 語意規則 2–7 ──────────────────────────────────────────

    @staticmethod
    def _rule1_name_empty(name: str) -> Optional[str]:
        if not name or not name.strip():
            return '⚠️ 命名不能為空'
        return None

    @staticmethod
    def _rule2_underscore(*fields: str) -> Optional[str]:
        for f in fields:
            if f and '_' in f:
                return '⚠️ 格式錯誤：各欄位內不得包含底線 [_] 符號'
        return None

    def _rule3_name_duplicate(self, name: str) -> Optional[str]:
        if name in self.d.reserved_names:
            return '⚠️ [命名] 不可與其他欄位已定義字詞重複'
        return None

    def _rule4_forbidden(self, name: str) -> Optional[str]:
        if name.lower() in self.d.forbidden_words:
            return '⚠️ [命名] 包含禁詞'
        return None

    def _rule5_nu_suffix(self, type_: str, e: str) -> Optional[str]:
        if type_.lower() == 'nu':
            if e == self.d.empty_option or e not in self.d.bitmap_font:
                return '⚠️ [nu] 須符合數字規範，不得使用語系尾綴取名'
        return None

    def _rule6_lang_suffix(self, type_: str, e: str) -> Optional[str]:
        if type_.lower() != 'nu':
            if e and e != self.d.empty_option and e not in self.d.language:
                return '⚠️ 若為多語系物件須符合規範，不得使用數字尾綴取名'
        return None

    # ── 工具 ──────────────────────────────────────────────────

    @staticmethod
    def _parse(filename: str) -> List[str]:
        stem = filename
        for ext in _EXTENSIONS:
            if filename.lower().endswith(ext):
                stem = filename[:-len(ext)]
                break
        return stem.split('_')
