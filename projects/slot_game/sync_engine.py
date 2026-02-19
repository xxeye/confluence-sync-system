"""
Slot Game 同步引擎
整合分類器、頁面建構器、說明文件載入器
"""

from typing import Dict, List, Any
from bs4 import BeautifulSoup

from core import BaseSyncEngine
from .classifier import SlotGameClassifier
from .page_builder import SlotGamePageBuilder
from utils.note_loader import NoteLoader


class SlotGameSyncEngine(BaseSyncEngine):
    """Slot Game 同步引擎"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.classifier = SlotGameClassifier()
        self.page_builder = SlotGamePageBuilder()

        # 載入說明文件（路徑從 config 讀取，不存在時靜默略過）
        notes_file = self.config.get('confluence', {}).get('notes_file')
        self.note_loader = NoteLoader(notes_file)

        if not self.note_loader.is_empty():
            self.logger.info("📄", f"說明文件已載入，共 {len(self.note_loader._notes)} 筆說明")
        else:
            self.logger.info("📄", "未設定說明文件或說明文件為空，說明欄位將留空")

    def classify_assets(
        self,
        files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分類資源

        Args:
            files: 檔案字典 {filename: {path, hash, width, height, size}}

        Returns:
            分類後字典
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
            categories: 分類後資源
            history:    更新歷史

        Returns:
            XHTML 內容字串
        """
        jira_filter_url = self.config.get('confluence', {}).get('jira_filter_url')

        # 將 NoteLoader 的說明對照表傳入 page_builder
        notes = dict(self.note_loader._notes)

        return self.page_builder.assemble(
            categories,
            history,
            jira_filter_url,
            notes=notes,
        )

    def _update_history_only(self, current_xhtml: str) -> str:
        """
        僅更新歷史紀錄區塊

        Args:
            current_xhtml: 現有頁面 XHTML

        Returns:
            更新後 XHTML
        """
        soup = BeautifulSoup(current_xhtml, 'html.parser')
        h2_node = soup.find('h2', string=lambda s: s and '更新紀錄' in s)

        if h2_node:
            # 找到舊的歷史表格，替換為新的
            new_history_table = self.page_builder._generate_history_table(
                self.state.get_history_slice(self.history_keep)
            )

            old_table = h2_node.find_next('table')
            if old_table:
                new_soup = BeautifulSoup(new_history_table, 'html.parser')
                old_table.replace_with(new_soup.table)

            return str(soup)
        else:
            # 找不到歷史區塊，重新產生完整頁面
            categories = self.classify_assets(self.state.remote_state)
            return self.build_page_content(
                categories,
                self.state.get_history_slice(self.history_keep)
            )
