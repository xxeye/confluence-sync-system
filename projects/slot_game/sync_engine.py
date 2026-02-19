"""
Slot Game 同步引擎
整合分類器和頁面建構器的具體實現
"""

from typing import Dict, List, Any
from bs4 import BeautifulSoup

from core import BaseSyncEngine
from .classifier import SlotGameClassifier
from .page_builder import SlotGamePageBuilder


class SlotGameSyncEngine(BaseSyncEngine):
    """Slot Game 同步引擎"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.classifier = SlotGameClassifier()
        self.page_builder = SlotGamePageBuilder()
    
    def classify_assets(
        self,
        files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分類資源
        
        Args:
            files: 檔案字典 {filename: {path, hash, width, height, size}}
        
        Returns:
            分類結果字典
        """
        return self.classifier.organize_assets(files)
    
    def build_page_content(
        self,
        categories: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> str:
        """
        建構頁面內容

        Args:
            categories: 分類結果
            history:    版本歷史

        Returns:
            XHTML 內容
        """
        jira_filter_url = self.config.get('confluence', {}).get('jira_filter_url')
        return self.page_builder.assemble(categories, history, jira_filter_url)
    
    def _update_history_only(self, current_xhtml: str) -> str:
        """
        僅更新歷史表格
        
        Args:
            current_xhtml: 當前頁面 XHTML
        
        Returns:
            更新後的 XHTML
        """
        soup = BeautifulSoup(current_xhtml, 'html.parser')
        h2_node = soup.find('h2', string=lambda s: s and '版本更新說明' in s)
        
        if h2_node:
            # 生成新的歷史表格
            new_history_table = self.page_builder._generate_history_table(
                self.state.get_history_slice(self.history_keep)
            )
            
            # 替換舊表格
            old_table = h2_node.find_next('table')
            if old_table:
                new_soup = BeautifulSoup(new_history_table, 'html.parser')
                old_table.replace_with(new_soup.table)
            
            return str(soup)
        else:
            # 找不到歷史表格，執行完整重繪
            categories = self.classify_assets(self.state.remote_state)
            return self.build_page_content(
                categories,
                self.state.get_history_slice(self.history_keep)
            )
