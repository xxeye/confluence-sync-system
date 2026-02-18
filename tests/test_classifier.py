"""
測試 Slot Game 分類器
"""

import pytest
from projects.slot_game.classifier import SlotGameClassifier


class TestSlotGameClassifier:
    """測試 SlotGameClassifier"""
    
    def setup_method(self):
        """每個測試前執行"""
        self.classifier = SlotGameClassifier()
    
    def test_layout_classification(self):
        """測試 Layout 分類"""
        asset = {'name': 'layout_main.png', 'size': '1920x1080', 'orig_w': 1920}
        category, group = self.classifier.classify(asset)
        
        assert category == 'layout'
        assert group is None
    
    def test_main_classification(self):
        """測試主遊戲分類"""
        asset = {'name': 'main_bg_01.png', 'size': '1920x1080', 'orig_w': 1920}
        category, group = self.classifier.classify(asset)
        
        assert category == 'main'
        assert group is None
    
    def test_free_classification(self):
        """測試免費遊戲分類"""
        asset = {'name': 'free_bg_01.png', 'size': '1920x1080', 'orig_w': 1920}
        category, group = self.classifier.classify(asset)
        
        assert category == 'free'
        assert group is None
    
    def test_loading_classification(self):
        """測試載入畫面分類"""
        asset = {'name': 'loading_logo.png', 'size': '500x500', 'orig_w': 500}
        category, group = self.classifier.classify(asset)
        
        assert category == 'loading'
        assert group is None
    
    def test_multilang_main_classification(self):
        """測試主遊戲多國語系分類"""
        asset = {'name': 'main_btn_start_cn.png', 'size': '200x80', 'orig_w': 200}
        category, group = self.classifier.classify(asset)
        
        assert category == 'multi_main'
        assert group == 'main_btn_start'
    
    def test_multilang_free_classification(self):
        """測試免費遊戲多國語系分類"""
        asset = {'name': 'free_txt_bonus_en.png', 'size': '300x100', 'orig_w': 300}
        category, group = self.classifier.classify(asset)
        
        assert category == 'multi_free'
        assert group == 'free_txt_bonus'
    
    def test_nu_main_classification(self):
        """測試主遊戲位圖數字分類"""
        asset = {'name': 'main_nu_win_0.png', 'size': '50x70', 'orig_w': 50}
        category, group = self.classifier.classify(asset)
        
        assert category == 'nu_main'
        assert group == 'main_nu_win'
    
    def test_nu_free_classification(self):
        """測試免費遊戲位圖數字分類"""
        asset = {'name': 'free_nu_mult_5.png', 'size': '60x80', 'orig_w': 60}
        category, group = self.classifier.classify(asset)
        
        assert category == 'nu_free'
        assert group == 'free_nu_mult'
    
    def test_organize_assets(self):
        """測試批次組織資源"""
        files = {
            'layout_main.png': {'path': '/path/1', 'hash': 'abc', 'width': 1920, 'height': 1080, 'size': '1920x1080'},
            'main_bg.png': {'path': '/path/2', 'hash': 'def', 'width': 1920, 'height': 1080, 'size': '1920x1080'},
            'main_btn_start_cn.png': {'path': '/path/3', 'hash': 'ghi', 'width': 200, 'height': 80, 'size': '200x80'},
            'main_btn_start_en.png': {'path': '/path/4', 'hash': 'jkl', 'width': 200, 'height': 80, 'size': '200x80'},
        }
        
        result = self.classifier.organize_assets(files)
        
        assert len(result['layout']) == 1
        assert len(result['main']) == 1
        assert 'main_btn_start' in result['multi_main']
        assert len(result['multi_main']['main_btn_start']) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
