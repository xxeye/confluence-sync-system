"""
測試 Slot Game 資源分類器

檔名格式：{sceneModule}_{type}_{name}_{visualState}[_{languageBitmapFont}]
"""

import pytest
from projects.slot_game.classifier import SlotGameClassifier


class TestSlotGameClassifier:
    """測試 SlotGameClassifier"""

    def setup_method(self):
        """每個測試前初始化"""
        self.classifier = SlotGameClassifier()

    def test_layout_classification(self):
        """測試 Layout 分類"""
        asset = {'name': 'layout_main.png', 'size': '1920x1080', 'orig_w': 1920}
        category, group = self.classifier.classify(asset)

        assert category == 'layout'
        assert group is None

    def test_main_classification(self):
        """測試主遊戲一般分類"""
        asset = {'name': 'base_img_bg_normal.png', 'size': '1920x1080', 'orig_w': 1920}
        category, group = self.classifier.classify(asset)

        assert category == 'main'
        assert group is None

    def test_free_classification(self):
        """測試免費遊戲分類"""
        asset = {'name': 'free_img_bg_normal.png', 'size': '1920x1080', 'orig_w': 1920}
        category, group = self.classifier.classify(asset)

        assert category == 'free'
        assert group is None

    def test_loading_classification(self):
        """測試載入畫面分類"""
        asset = {'name': 'loading_img_logo_na.png', 'size': '500x500', 'orig_w': 500}
        category, group = self.classifier.classify(asset)

        assert category == 'loading'
        assert group is None

    def test_multilang_main_classification(self):
        """測試主遊戲多國語系分類"""
        asset = {'name': 'base_btn_start_normal_cn.png', 'size': '200x80', 'orig_w': 200}
        category, group = self.classifier.classify(asset)

        assert category == 'multi_main'
        assert group == 'base_btn_start_normal'   # sceneModule_type_name_visualState

    def test_multilang_free_classification(self):
        """測試免費遊戲多國語系分類"""
        asset = {'name': 'free_text_bonus_na_en.png', 'size': '300x100', 'orig_w': 300}
        category, group = self.classifier.classify(asset)

        assert category == 'multi_free'
        assert group == 'free_text_bonus_na'      # sceneModule_type_name_visualState

    def test_nu_main_classification(self):
        """
        測試主遊戲 NU 數字組分類
        ✅ group_key 必須包含 visualState（前 4 欄）
        """
        asset = {'name': 'base_nu_win_na_0.png', 'size': '50x70', 'orig_w': 50}
        category, group = self.classifier.classify(asset)

        assert category == 'nu_main'
        assert group == 'base_nu_win_na'          # ✅ 含 visualState，非舊版的 base_nu_win

    def test_nu_free_classification(self):
        """測試免費遊戲 NU 數字組分類"""
        asset = {'name': 'free_nu_mult_na_5.png', 'size': '60x80', 'orig_w': 60}
        category, group = self.classifier.classify(asset)

        assert category == 'nu_free'
        assert group == 'free_nu_mult_na'         # ✅ 含 visualState

    def test_nu_different_visualstate_different_group(self):
        """
        測試相同 name 但不同 visualState 的 NU 應分到不同群組
        例：base_nu_win_na 與 base_nu_win_confirm 應該是兩個獨立群組
        """
        asset_na = {'name': 'base_nu_win_na_0.png', 'size': '50x70', 'orig_w': 50}
        asset_confirm = {'name': 'base_nu_win_confirm_0.png', 'size': '50x70', 'orig_w': 50}

        _, group_na = self.classifier.classify(asset_na)
        _, group_confirm = self.classifier.classify(asset_confirm)

        assert group_na == 'base_nu_win_na'
        assert group_confirm == 'base_nu_win_confirm'
        assert group_na != group_confirm           # ✅ 兩組不同

    def test_organize_assets(self):
        """測試完整資源組織"""
        files = {
            'layout_base.png': {'path': '/p/1', 'hash': 'a', 'width': 1920, 'height': 1080, 'size': '1920x1080'},
            'base_img_bg_normal.png': {'path': '/p/2', 'hash': 'b', 'width': 1920, 'height': 1080, 'size': '1920x1080'},
            'base_btn_start_normal_cn.png': {'path': '/p/3', 'hash': 'c', 'width': 200, 'height': 80, 'size': '200x80'},
            'base_btn_start_normal_en.png': {'path': '/p/4', 'hash': 'd', 'width': 200, 'height': 80, 'size': '200x80'},
            'base_nu_win_na_0.png': {'path': '/p/5', 'hash': 'e', 'width': 50, 'height': 70, 'size': '50x70'},
            'base_nu_win_na_1.png': {'path': '/p/6', 'hash': 'f', 'width': 50, 'height': 70, 'size': '50x70'},
        }

        result = self.classifier.organize_assets(files)

        assert len(result['layout']) == 1
        assert len(result['main']) == 1

        # 多國語系群組 key 含 visualState
        assert 'base_btn_start_normal' in result['multi_main']
        assert len(result['multi_main']['base_btn_start_normal']) == 2

        # NU 群組 key 含 visualState
        assert 'base_nu_win_na' in result['nu_main']
        assert len(result['nu_main']['base_nu_win_na']) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
