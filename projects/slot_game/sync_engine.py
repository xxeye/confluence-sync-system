"""
Slot Game 同步引擎
整合分類器、頁面建構器、說明文件載入器、檔名驗證器
"""

from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from core import BaseSyncEngine
from .classifier import SlotGameClassifier
from .page_builder import SlotGamePageBuilder
from .validator import DictLoader, FilenameValidator
from utils.note_loader import NoteLoader


class SlotGameSyncEngine(BaseSyncEngine):
    """Slot Game 同步引擎"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_builder = SlotGamePageBuilder()
        # classifier 暫時用預設 lang_codes，待 validator 初始化後更新
        self.classifier   = SlotGameClassifier()

        # ── 說明文件 ──────────────────────────────────────────
        notes_file = self.config.get('confluence', {}).get('notes_file')
        self.note_loader = NoteLoader(notes_file)

        if not self.note_loader.is_empty():
            self.logger.info("📄", f"說明文件已載入，共 {len(self.note_loader._notes)} 筆說明")
        else:
            self.logger.info("📄", "未設定說明文件或說明文件為空，說明欄位將留空")

        # ── 驗證器 ────────────────────────────────────────────
        self.validator: Optional[FilenameValidator] = None
        validator_cfg = self.config.get('validator', {})

        if validator_cfg.get('enabled', False):
            dict_file = validator_cfg.get('dict_file')
            if not dict_file:
                self.logger.warning("⚠️", "validator.enabled=true 但未設定 dict_file，驗證器停用")
            else:
                try:
                    loader         = DictLoader(dict_file)
                    self.validator = FilenameValidator(loader)
                    # 讓 classifier 使用與 validator 相同的語系集合，避免兩邊不同步
                    self.classifier = SlotGameClassifier(
                        lang_codes=loader.language,
                        bitmap_font_digits=loader.bitmap_font,
                    )
                    self.logger.info("🔍", f"檔名驗證器已啟用，字典：{dict_file}")
                except FileNotFoundError as e:
                    self.logger.warning("⚠️", f"字典檔不存在，驗證器停用：{e}")
                except Exception as e:
                    self.logger.warning("⚠️", f"驗證器初始化失敗，驗證器停用：{e}")
        else:
            self.logger.info("🔍", "檔名驗證器未啟用（validator.enabled=false）")

    def classify_assets(
        self,
        files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        return self.classifier.organize_assets(files)

    def build_page_content(
        self,
        categories: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> str:
        jira_filter_url = self.config.get('confluence', {}).get('jira_filter_url')
        notes           = dict(self.note_loader._notes)

        naming_doc_url = self.config.get('validator', {}).get('naming_doc_url')

        return self.page_builder.assemble(
            categories,
            history,
            jira_filter_url,
            notes=notes,
            validator=self.validator,   # None 時 page_builder 自動跳過驗證
            naming_doc_url=naming_doc_url,
        )

    def _update_history_only(self, current_xhtml: str) -> str:
        soup    = BeautifulSoup(current_xhtml, 'html.parser')
        h2_node = soup.find('h2', string=lambda s: s and '更新紀錄' in s)

        if h2_node:
            new_history_table = self.page_builder._generate_history_table(
                self.state.get_history_slice(self.history_keep)
            )
            old_table = h2_node.find_next('table')
            if old_table:
                new_soup = BeautifulSoup(new_history_table, 'html.parser')
                old_table.replace_with(new_soup.table)
            return str(soup)
        else:
            categories = self.classify_assets(self.state.remote_state)
            return self.build_page_content(
                categories,
                self.state.get_history_slice(self.history_keep)
            )


