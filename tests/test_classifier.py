"""
測試 Slot Game 資源分類器

檔名格式：{sceneModule}_{type}_{name}_{visualState}[_{languageBitmapFont}]
"""

import pytest
from projects.slot_game.classifier import SlotGameClassifier


def _asset(name, w=100, h=100):
    """建立測試用 asset dict 的輔助函式"""
    return {'name': name, 'size': f'{w}x{h}', 'orig_w': w, 'orig_h': h}


class TestSlotGameClassifier:

    def setup_method(self):
        self.classifier = SlotGameClassifier()

    # ── 基本分類 ──────────────────────────────────────────────

    def test_layout_classification(self):
        cat, grp = self.classifier.classify(_asset('layout_main.png'))
        assert cat == 'layout'
        assert grp is None

    def test_main_classification(self):
        cat, grp = self.classifier.classify(_asset('base_img_bg_normal.png'))
        assert cat == 'main'
        assert grp is None

    def test_free_classification(self):
        cat, grp = self.classifier.classify(_asset('free_img_bg_normal.png'))
        assert cat == 'free'
        assert grp is None

    def test_loading_classification(self):
        cat, grp = self.classifier.classify(_asset('loading_img_logo_na.png'))
        assert cat == 'loading'
        assert grp is None

    # ── 多國語系 ──────────────────────────────────────────────

    def test_multilang_main_classification(self):
        cat, grp = self.classifier.classify(_asset('base_btn_start_normal_cn.png'))
        assert cat == 'multi_main'
        assert grp == 'base_btn_start_normal'

    def test_multilang_free_classification(self):
        cat, grp = self.classifier.classify(_asset('free_text_bonus_na_en.png'))
        assert cat == 'multi_free'
        assert grp == 'free_text_bonus_na'

    def test_multilang_loading_classification(self):
        cat, grp = self.classifier.classify(_asset('loading_text_tip_na_jp.png'))
        assert cat == 'multi_loading'
        assert grp == 'loading_text_tip_na'

    # ── NU 數字組 ─────────────────────────────────────────────

    def test_nu_main_classification(self):
        cat, grp = self.classifier.classify(_asset('base_nu_win_na_0.png'))
        assert cat == 'nu_main'
        assert grp == 'base_nu_win_na'

    def test_nu_free_classification(self):
        cat, grp = self.classifier.classify(_asset('free_nu_mult_na_5.png'))
        assert cat == 'nu_free'
        assert grp == 'free_nu_mult_na'

    def test_nu_different_visualstate_different_group(self):
        """相同 name 不同 visualState 的 NU 應分到不同群組"""
        _, grp_na      = self.classifier.classify(_asset('base_nu_win_na_0.png'))
        _, grp_confirm = self.classifier.classify(_asset('base_nu_win_confirm_0.png'))
        assert grp_na      == 'base_nu_win_na'
        assert grp_confirm == 'base_nu_win_confirm'
        assert grp_na != grp_confirm

    # ── NU 退化：欄位不足 → 一般分類 ─────────────────────────

    def test_nu_missing_visualstate_degrades(self):
        """NU 第 4 欄是數字（缺 visualState）→ 退化為一般分類"""
        cat, grp = self.classifier.classify(_asset('autostart_nu_auto_4.png'))
        assert cat == 'main'
        assert grp is None

    def test_nu_cloud_conflict_degrades(self):
        """雲端衝突複本 '4 (1)' 應退化為一般分類，不被誤判為 NU 群組"""
        cat, grp = self.classifier.classify(_asset('autostart_nu_auto_4 (1).png'))
        assert cat == 'main'
        assert grp is None

    def test_nu_cloud_conflict_various(self):
        """多種雲端衝突格式都應退化"""
        for name in ['autostart_nu_auto_5 (1).png', 'autostart_nu_auto_9（2）.png']:
            cat, grp = self.classifier.classify(_asset(name))
            assert cat == 'main', f'{name} 應退化為 main，實際: {cat}'
            assert grp is None

    # ── 欄位不足（非 NU）──────────────────────────────────────

    def test_insufficient_fields_falls_back_to_scene(self):
        cat, grp = self.classifier.classify(_asset('loading_bar.png'))
        assert cat == 'loading'
        assert grp is None

    def test_insufficient_fields_main(self):
        cat, grp = self.classifier.classify(_asset('base_img.png'))
        assert cat == 'main'
        assert grp is None

    # ── lang_codes 從外部傳入 ─────────────────────────────────

    def test_custom_lang_codes(self):
        """從外部傳入 lang_codes 時，分類結果以傳入集合為準"""
        custom = SlotGameClassifier(lang_codes={'cn', 'en'})
        cat, _ = custom.classify(_asset('base_btn_start_na_cn.png'))
        assert cat == 'multi_main'
        cat, _ = custom.classify(_asset('base_btn_start_na_jp.png'))
        assert cat == 'main'  # jp 不在自訂集合

    def test_default_lang_codes_covers_all_standard_languages(self):
        """未傳入 lang_codes 時，預設值應涵蓋所有標準語系"""
        for lang in ['cn', 'cm', 'jp', 'kr', 'th', 'id', 'vn', 'es', 'pt', 'tr', 'mm', 'bd', 'en']:
            cat, _ = self.classifier.classify(_asset(f'base_btn_start_na_{lang}.png'))
            assert cat == 'multi_main', f'語系 {lang} 應被識別為 multi_main'

    # ── organize_assets ───────────────────────────────────────

    def test_organize_assets(self):
        files = {
            'layout_base.png':              {'path': '/p/1', 'hash': 'a', 'width': 1920, 'height': 1080, 'size': '1920x1080'},
            'base_img_bg_normal.png':       {'path': '/p/2', 'hash': 'b', 'width': 1920, 'height': 1080, 'size': '1920x1080'},
            'base_btn_start_normal_cn.png': {'path': '/p/3', 'hash': 'c', 'width': 200,  'height': 80,   'size': '200x80'},
            'base_btn_start_normal_en.png': {'path': '/p/4', 'hash': 'd', 'width': 200,  'height': 80,   'size': '200x80'},
            'base_nu_win_na_0.png':         {'path': '/p/5', 'hash': 'e', 'width': 50,   'height': 70,   'size': '50x70'},
            'base_nu_win_na_1.png':         {'path': '/p/6', 'hash': 'f', 'width': 50,   'height': 70,   'size': '50x70'},
        }
        result = self.classifier.organize_assets(files)
        assert len(result['layout']) == 1
        assert len(result['main'])   == 1
        assert 'base_btn_start_normal' in result['multi_main']
        assert len(result['multi_main']['base_btn_start_normal']) == 2
        assert 'base_nu_win_na' in result['nu_main']
        assert len(result['nu_main']['base_nu_win_na']) == 2

    def test_organize_assets_includes_orig_h(self):
        """organize_assets 產生的 asset 必須包含 orig_h"""
        files = {'base_img_bg_normal.png': {'path': '/p/1', 'hash': 'a', 'width': 1920, 'height': 1080, 'size': '1920x1080'}}
        result = self.classifier.organize_assets(files)
        asset  = result['main'][0]
        assert 'orig_h' in asset
        assert asset['orig_h'] == 1080

    def test_organize_assets_nu_degraded_goes_to_main(self):
        """欄位不足的 NU 檔案（含雲端衝突複本）應進入 main 而非 nu_main"""
        files = {
            'autostart_nu_auto_4.png':     {'path': '/p/1', 'hash': 'a', 'width': 100, 'height': 100, 'size': '100x100'},
            'autostart_nu_auto_4 (1).png': {'path': '/p/2', 'hash': 'b', 'width': 100, 'height': 100, 'size': '100x100'},
        }
        result = self.classifier.organize_assets(files)
        assert len(result['main'])    == 2
        assert len(result['nu_main']) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
