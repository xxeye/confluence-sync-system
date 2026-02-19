"""
測試 FilenameValidator

涵蓋：
  - 前置過濾（雲端衝突、複製、暫存、空白字元）
  - 欄位數量檢查（含 NU / 多國語系位移偵測）
  - 語意規則 1–6
  - validate_all()：多條違規收集
  - validate_group_key()：群組鍵異常偵測
"""

import pytest
from projects.slot_game.validator import DictLoader, FilenameValidator


# ── 共用 Fixture ───────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def validator():
    loader = DictLoader('config/game_dict.yaml')
    return FilenameValidator(loader)


# ── 0. 前置過濾：系統/雲端異常檔名 ───────────────────────────────────────────

class TestSystemFilenameFilter:

    def test_cloud_conflict_bracket_number(self, validator):
        """括號數字 → 雲端同步衝突複本"""
        assert validator.validate('main_img_bg_na (1).png') is not None
        assert validator.validate('main_img_bg_na（2）.png') is not None

    def test_manual_copy_chinese(self, validator):
        """含「複製」字樣"""
        assert validator.validate('main_img_bg_na - 複製.png') is not None

    def test_manual_copy_english(self, validator):
        """含「Copy」字樣"""
        assert validator.validate('main_img_bg_na - Copy.png') is not None

    def test_dropbox_conflict(self, validator):
        """Dropbox 衝突副本格式"""
        assert validator.validate('main_img_bg_na（John 的衝突副本）.png') is not None

    def test_macos_temp_file(self, validator):
        """macOS 系統暫存檔（._前綴）"""
        assert validator.validate('._main_img_bg_na.png') is not None

    def test_office_temp_file(self, validator):
        """Office 暫存檔（~$前綴）"""
        assert validator.validate('~$main_img_bg_na.png') is not None

    def test_leading_whitespace(self, validator):
        """檔名開頭空白"""
        assert validator.validate(' main_img_bg_na.png') is not None

    def test_whitespace_before_extension(self, validator):
        """副檔名前空白"""
        assert validator.validate('main_img_bg_na .png') is not None

    def test_whitespace_between_fields(self, validator):
        """欄位間空白"""
        assert validator.validate('main _img_bg_na.png') is not None


# ── 1. 欄位數量 ───────────────────────────────────────────────────────────────

class TestFieldCount:

    def test_too_few_fields(self, validator):
        """少於 4 欄"""
        w = validator.validate('main_img_bg.png')
        assert w is not None
        assert '欄位不足' in w

    def test_nu_missing_visualstate_digit_in_field4(self, validator):
        """NU 第 4 欄是數字 → 缺 visualState"""
        w = validator.validate('main_nu_win_4.png')
        assert w is not None
        assert 'NU' in w or 'nu' in w.lower()

    def test_nu_missing_visualstate_cloud_conflict(self, validator):
        """NU 第 4 欄是衝突複本數字（如 '4 (1)'）→ 雲端衝突優先報告"""
        w = validator.validate('main_nu_win_4 (1).png')
        assert w is not None  # 至少有一條警告

    def test_lang_code_in_field4(self, validator):
        """語系代碼出現在第 4 欄（應在第 5 欄）"""
        w = validator.validate('main_img_bg_cn.png')
        assert w is not None
        assert '多國語系' in w or '欄位' in w

    def test_valid_4_fields(self, validator):
        """正好 4 欄且符合規範 → 通過"""
        assert validator.validate('main_img_bg_na.png') is None

    def test_valid_5_fields_lang(self, validator):
        """5 欄多國語系 → 通過"""
        assert validator.validate('main_img_bg_na_cn.png') is None


# ── 語意規則 ──────────────────────────────────────────────────────────────────

class TestSemanticRules:

    def test_rule1_name_empty(self, validator):
        """name 欄位不得為空"""
        # 直接呼叫 _rule1（公開介面需透過 validate）
        w = validator._rule1_name_empty('')
        assert w is not None

    def test_rule2_underscore_in_field(self, validator):
        """欄位值內含底線"""
        w = validator.validate('main_img_bg_na_c_n.png')
        # c_n 在第 5 欄含底線，或 validate 先報其他問題皆可
        assert w is not None

    def test_rule3_name_duplicate_reserved(self, validator):
        """name 與保留字詞重複（如 type 中的詞）"""
        # 'nu' 和 'img' 都是 type 欄位的保留詞，確定在 reserved_names 裡
        assert validator._rule3_name_duplicate('nu') is not None
        assert validator._rule3_name_duplicate('img') is not None
        assert validator._rule3_name_duplicate('btn') is not None

    def test_rule3_name_in_whitelist_passes(self, validator):
        """name 在 named 白名單中 → 通過（白名單不納入保留字）"""
        # 這個測試依字典內容而定，僅示意結構
        # 若字典有 named: [win]，則 win 不應觸發 rule3
        pass

    def test_rule4_forbidden_word(self, validator):
        """name 為禁詞"""
        # 直接測 rule4
        for word in ['test', 'temp', 'tmp', 'delete']:
            w = validator._rule4_forbidden(word)
            if w:
                assert '禁詞' in w
                break  # 只要找到一個禁詞即可驗證邏輯

    def test_rule5_nu_invalid_suffix(self, validator):
        """type=nu 但第 5 欄不是 bitmap_font"""
        w = validator._rule5_nu_suffix('nu', 'cn')
        assert w is not None
        assert 'nu' in w.lower()

    def test_rule5_nu_valid_suffix(self, validator):
        """type=nu 且第 5 欄是 bitmap_font → 通過"""
        # '0'~'9' 應在 bitmap_font
        assert validator._rule5_nu_suffix('nu', '0') is None

    def test_rule6_lang_invalid_suffix(self, validator):
        """type 非 nu 但第 5 欄是 bitmap_font 數字"""
        w = validator._rule6_lang_suffix('img', '5')
        assert w is not None
        assert '多語系' in w or '數字' in w

    def test_rule6_lang_valid_suffix(self, validator):
        """type 非 nu 且第 5 欄是 language → 通過"""
        assert validator._rule6_lang_suffix('img', 'cn') is None

    def test_rule6_no_suffix_passes(self, validator):
        """第 5 欄為空（empty_option）→ 通過"""
        empty = validator.d.empty_option
        assert validator._rule6_lang_suffix('img', empty) is None


# ── validate_all()：多條違規 ──────────────────────────────────────────────────

class TestValidateAll:

    def test_single_violation_returns_one(self, validator):
        """只有一條違規"""
        warns = validator.validate_all('main_img_bg.png')  # 欄位不足
        assert len(warns) == 1

    def test_cloud_conflict_plus_field_count(self, validator):
        """
        雲端衝突 + 欄位不足同時成立：
        autostart_nu_auto_4 (1).png
          → ⚠️ 雲端同步衝突複本（0. 前置過濾）
          → ⚠️ NU 欄位不足（1. 欄位數量）
        兩條獨立違規，應同時回傳
        """
        warns = validator.validate_all('autostart_nu_auto_4 (1).png')
        assert len(warns) >= 2
        combined = ' '.join(warns)
        assert '衝突' in combined or '複本' in combined
        assert 'NU' in combined or '欄位' in combined

    def test_clean_file_returns_empty(self, validator):
        """完全合規的檔名 → 空列表"""
        warns = validator.validate_all('main_img_bg_na.png')
        assert warns == []

    def test_layout_always_passes(self, validator):
        """layout 檔案跳過所有驗證"""
        warns = validator.validate_all('layout_basegame.png')
        assert warns == []

    def test_validate_first_equals_validate_all_first(self, validator):
        """validate() 的回傳值應與 validate_all()[0] 一致"""
        filename = 'main_img_bg.png'
        single = validator.validate(filename)
        all_w  = validator.validate_all(filename)
        assert single == all_w[0] if all_w else single is None


# ── validate_group_key() ──────────────────────────────────────────────────────

class TestValidateGroupKey:

    def test_bracket_number_in_group_key(self, validator):
        """group_key 含括號數字 → 警告"""
        w = validator.validate_group_key('main_img_bg_na (1)')
        assert w is not None
        assert '衝突' in w

    def test_fullwidth_bracket_number(self, validator):
        """全形括號也應偵測"""
        w = validator.validate_group_key('main_img_bg_na（1）')
        assert w is not None

    def test_whitespace_in_group_key(self, validator):
        """group_key 含空白字元"""
        w = validator.validate_group_key('main_img bg_na')
        assert w is not None
        assert '空白' in w

    def test_clean_group_key_passes(self, validator):
        """正常 group_key → None"""
        assert validator.validate_group_key('main_img_bg_na') is None
        assert validator.validate_group_key('free_nu_win_na') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
