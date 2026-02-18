"""
同步引擎基類
定義核心同步邏輯的抽象介面
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from PIL import Image

from .confluence_client import ConfluenceClient
from .state_manager import StateManager
from .hash_calculator import HashCalculator
from utils import SyncLogger, LogIcons


class SyncDiff:
    """同步差異"""
    
    def __init__(
        self,
        to_add: List[str],
        to_update: List[str],
        to_delete: List[str]
    ):
        self.to_add = to_add
        self.to_update = to_update
        self.to_delete = to_delete
    
    def has_changes(self) -> bool:
        """是否有變更"""
        return bool(self.to_add or self.to_update or self.to_delete)
    
    def summary(self) -> str:
        """變更摘要"""
        return f"+{len(self.to_add)} ~{len(self.to_update)} -{len(self.to_delete)}"


class BaseSyncEngine(ABC):
    """同步引擎基類"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        confluence_client: ConfluenceClient,
        state_manager: StateManager,
        logger: SyncLogger
    ):
        """
        初始化同步引擎
        
        Args:
            config: 完整配置字典
            confluence_client: Confluence 客戶端
            state_manager: 狀態管理器
            logger: 日誌記錄器
        """
        self.config = config
        self.client = confluence_client
        self.state = state_manager
        self.logger = logger
        
        # 從配置提取常用參數
        self.target_folder = config['sync']['target_folder']
        self.max_workers = config['sync']['max_workers']
        self.history_keep = config['sync']['history_keep']
        self.file_patterns = config.get('file_patterns', {})
        self.project_name = config['project']['name']
        self.user_id = config['confluence']['user_account_id']
    
    @abstractmethod
    def classify_assets(
        self,
        files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分類資源（由子類實現）
        
        Args:
            files: 檔案字典 {filename: {path, hash, width, height}}
        
        Returns:
            分類結果字典
        """
        pass
    
    @abstractmethod
    def build_page_content(
        self,
        categories: Dict[str, Any],
        history: List[Dict[str, str]]
    ) -> str:
        """
        建構頁面內容（由子類實現）
        
        Args:
            categories: 分類結果
            history: 版本歷史
        
        Returns:
            XHTML 內容
        """
        pass
    
    def run_sync(
        self,
        is_startup: bool = False,
        log_reason: str = "Sync",
        dry_run: bool = False
    ) -> None:
        """
        執行同步（核心流程）
        
        Args:
            is_startup: 是否為啟動同步
            log_reason: 日誌原因
            dry_run: 是否為模擬執行（不實際修改）
        """
        try:
            # 1. 取得遠端狀態
            if is_startup or not self.state.cache_file.exists():
                self.logger.info(LogIcons.CONNECT, "執行完整雲端同步...")
                remote_state = self._full_cloud_sync()
            else:
                remote_state = self.state.remote_state
            
            # 2. 掃描本地檔案
            self.logger.info(LogIcons.PROGRESS, "掃描本地資源...")
            local_state = self._scan_local_files()
            
            # 3. 計算差異
            diff = self._calculate_diff(local_state, remote_state)
            
            if not diff.has_changes() and not is_startup:
                self.logger.info(LogIcons.COMPLETE, "無變更，跳過同步")
                return
            
            self.logger.info(
                LogIcons.PROGRESS,
                f"變更統計: {diff.summary()}"
            )
            
            if dry_run:
                self.logger.info(LogIcons.WARNING, "Dry-run 模式：僅預覽，不實際執行")
                self._print_diff_details(diff, local_state)
                return
            
            # 4. 執行物理操作
            self._execute_operations(diff, local_state, remote_state)
            
            # 5. 更新頁面內容
            needs_redraw = (len(diff.to_add) > 0 or len(diff.to_delete) > 0 or is_startup)
            self._update_page(local_state, diff, log_reason, needs_redraw)
            
            # 6. 儲存狀態
            self.state.save()
            
            self.logger.success(LogIcons.COMPLETE, "同步完成")
            
        except Exception as e:
            self.logger.error(LogIcons.ERROR, f"同步失敗: {e}", exc_info=e)
            raise
    
    def _full_cloud_sync(self) -> Dict[str, Dict[str, Any]]:
        """完整雲端同步（並發下載與校驗）"""
        remote_state = {}
        
        # 取得頁面內容和歷史
        xhtml, _ = self.client.get_page_content()
        history = self.client.parse_history_from_page(xhtml, self.history_keep)
        
        # 更新狀態管理器的歷史
        self.state._history = history
        
        # 取得所有附件
        all_attachments = self.client.get_all_attachments()
        
        # 過濾圖片附件
        image_attachments = [
            att for att in all_attachments
            if self._is_valid_file(att['title'])
        ]
        
        total = len(image_attachments)
        self.logger.info(
            LogIcons.LAUNCH,
            f"平行校驗中 (執行緒: {self.max_workers['download']})... 目標: {total}"
        )
        
        # 並發下載與哈希計算
        with ThreadPoolExecutor(max_workers=self.max_workers['download']) as executor:
            futures = {
                executor.submit(self._download_and_hash, att): att
                for att in image_attachments
            }
            
            done = 0
            for future in as_completed(futures):
                done += 1
                result = future.result()
                
                if result:
                    filename, file_data = result
                    remote_state[filename] = file_data
                
                # 進度日誌
                if done % max(1, total // 10) == 0 or done == total:
                    progress = (done / total) * 100
                    self.logger.info(
                        LogIcons.PROGRESS,
                        f"校驗進度: {done}/{total} ({progress:.1f}%)"
                    )
        
        self.state.remote_state = remote_state
        return remote_state
    
    def _download_and_hash(
        self,
        attachment: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """下載並計算哈希（並發任務單元）"""
        filename = attachment['title']
        
        try:
            download_path = attachment['_links']['download']
            content = self.client.download_attachment(download_path)
            file_hash = HashCalculator.calculate(BytesIO(content))
            
            return filename, {
                'id': attachment['id'],
                'hash': file_hash
            }
        except Exception as e:
            self.logger.error(
                LogIcons.ERROR,
                f"下載失敗 {filename}: {e}"
            )
            return None
    
    def _scan_local_files(self) -> Dict[str, Dict[str, Any]]:
        """掃描本地檔案"""
        local_state = {}
        target_path = Path(self.target_folder)
        
        if not target_path.exists():
            self.logger.warning(
                LogIcons.WARNING,
                f"目標資料夾不存在: {self.target_folder}"
            )
            return local_state
        
        for root, _, files in os.walk(target_path):
            for filename in files:
                if not self._is_valid_file(filename):
                    continue
                
                file_path = os.path.join(root, filename)
                
                try:
                    file_hash = HashCalculator.calculate(file_path)
                    
                    # 讀取圖片尺寸
                    with Image.open(file_path) as img:
                        width, height = img.size
                    
                    local_state[filename] = {
                        'path': file_path,
                        'hash': file_hash,
                        'width': width,
                        'height': height,
                        'size': f"{width}x{height}"
                    }
                except Exception as e:
                    self.logger.error(
                        LogIcons.ERROR,
                        f"讀取檔案失敗 {filename}: {e}"
                    )
        
        return local_state
    
    def _is_valid_file(self, filename: str) -> bool:
        """檢查檔案是否有效"""
        filename_lower = filename.lower()
        
        # 檢查包含模式
        include_patterns = self.file_patterns.get('include', ['*.png', '*.jpg', '*.jpeg'])
        if include_patterns:
            matches = False
            for pattern in include_patterns:
                if pattern.startswith('*.'):
                    ext = pattern[1:]
                    if filename_lower.endswith(ext):
                        matches = True
                        break
            if not matches:
                return False
        
        # 檢查排除模式
        exclude_patterns = self.file_patterns.get('exclude', [])
        for pattern in exclude_patterns:
            if pattern.startswith('*'):
                suffix = pattern[1:]
                if suffix in filename_lower:
                    return False
        
        return True
    
    def _calculate_diff(
        self,
        local_state: Dict[str, Dict[str, Any]],
        remote_state: Dict[str, Dict[str, Any]]
    ) -> SyncDiff:
        """計算本地與遠端的差異"""
        to_add = [
            name for name in local_state
            if name not in remote_state
        ]
        
        to_delete = [
            name for name in remote_state
            if name not in local_state
        ]
        
        to_update = [
            name for name in local_state
            if name in remote_state
            and local_state[name]['hash'] != remote_state[name]['hash']
        ]
        
        return SyncDiff(to_add, to_update, to_delete)
    
    def _execute_operations(
        self,
        diff: SyncDiff,
        local_state: Dict[str, Dict[str, Any]],
        remote_state: Dict[str, Dict[str, Any]]
    ) -> None:
        """執行物理操作（刪除、上傳）"""
        # A. 刪除操作
        if diff.to_delete:
            self.logger.info(
                LogIcons.CLEAN,
                f"清理雲端資源 (執行緒: {self.max_workers['delete']})..."
            )
            
            with ThreadPoolExecutor(max_workers=self.max_workers['delete']) as executor:
                delete_futures = {
                    executor.submit(
                        self._delete_file,
                        filename,
                        remote_state[filename]['id']
                    ): filename
                    for filename in diff.to_delete
                }
                
                for future in as_completed(delete_futures):
                    filename = delete_futures[future]
                    if future.result():
                        self.state.remove_remote_file(filename)
        
        # B. 上傳操作（新增 + 更新）
        upload_targets = diff.to_add + diff.to_update
        if upload_targets:
            self.logger.info(
                LogIcons.UPLOAD,
                f"執行原子化同步 (執行緒: {self.max_workers['upload']})... "
                f"目標: {len(upload_targets)}"
            )
            
            with ThreadPoolExecutor(max_workers=self.max_workers['upload']) as executor:
                upload_futures = {
                    executor.submit(
                        self._upload_file,
                        filename,
                        local_state[filename]['path']
                    ): filename
                    for filename in upload_targets
                }
                
                for future in as_completed(upload_futures):
                    filename = upload_futures[future]
                    new_id = future.result()
                    
                    if new_id:
                        # 更新狀態
                        self.state.update_remote_file(
                            filename,
                            new_id,
                            local_state[filename]['hash']
                        )
                        
                        # 記錄日誌
                        if filename in diff.to_update:
                            self.logger.success(
                                LogIcons.UPDATE,
                                f"原子化更新完成: {filename}"
                            )
                        else:
                            self.logger.success(
                                LogIcons.NEW,
                                f"新資源上傳完成: {filename}"
                            )
    
    def _delete_file(self, filename: str, attachment_id: str) -> bool:
        """刪除檔案"""
        try:
            success = self.client.delete_attachment(attachment_id)
            if success:
                self.logger.info(LogIcons.DELETE, f"已刪除: {filename}")
            return success
        except Exception as e:
            self.logger.error(
                LogIcons.ERROR,
                f"刪除失敗 {filename}: {e}"
            )
            return False
    
    def _upload_file(self, filename: str, file_path: str) -> str:
        """上傳檔案"""
        try:
            new_id = self.client.upload_attachment(file_path, filename)
            return new_id
        except Exception as e:
            self.logger.error(
                LogIcons.ERROR,
                f"上傳失敗 {filename}: {e}"
            )
            return None
    
    def _update_page(
        self,
        local_state: Dict[str, Dict[str, Any]],
        diff: SyncDiff,
        log_reason: str,
        needs_redraw: bool
    ) -> None:
        """更新頁面內容"""
        # 新增歷史記錄
        self.state.add_history_entry(
            f"{log_reason} ({diff.summary()})",
            self.user_id,
            self.history_keep
        )
        
        if needs_redraw:
            self.logger.info(LogIcons.PAINT, "執行頁面全量重新編排...")
            
            # 分類資源
            categories = self.classify_assets(local_state)
            
            # 建構頁面內容
            new_content = self.build_page_content(
                categories,
                self.state.get_history_slice(self.history_keep)
            )
        else:
            self.logger.info(LogIcons.NOTE, "僅更新歷史表格...")
            
            # 只更新歷史表格
            current_xhtml, _ = self.client.get_page_content()
            new_content = self._update_history_only(current_xhtml)
        
        # 推送到 Confluence
        current_xhtml, current_version = self.client.get_page_content()
        page_title = f"美術資源清單_{self.project_name}"
        
        self.client.update_page_content(
            new_content,
            page_title,
            current_version
        )
        
        self.logger.success(
            LogIcons.COMPLETE,
            f"Wiki 推送完成 (Ver: {current_version + 1})"
        )
    
    def _update_history_only(self, current_xhtml: str) -> str:
        """僅更新歷史表格（需要由子類提供具體實現邏輯）"""
        # 這裡提供基本實現，子類可以覆寫
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(current_xhtml, 'html.parser')
        h2_node = soup.find('h2', string=lambda s: s and '版本更新說明' in s)
        
        if h2_node:
            # 這裡需要子類提供 generate_history_table 方法
            # 暫時返回原內容
            return current_xhtml
        
        return current_xhtml
    
    def _print_diff_details(
        self,
        diff: SyncDiff,
        local_state: Dict[str, Dict[str, Any]]
    ) -> None:
        """打印差異詳情（用於 dry-run）"""
        if diff.to_add:
            self.logger.info(LogIcons.NEW, f"待新增 ({len(diff.to_add)}):")
            for filename in diff.to_add[:10]:  # 最多顯示 10 個
                self.logger.info("  ", f"  + {filename}")
            if len(diff.to_add) > 10:
                self.logger.info("  ", f"  ... 還有 {len(diff.to_add) - 10} 個")
        
        if diff.to_update:
            self.logger.info(LogIcons.UPDATE, f"待更新 ({len(diff.to_update)}):")
            for filename in diff.to_update[:10]:
                self.logger.info("  ", f"  ~ {filename}")
            if len(diff.to_update) > 10:
                self.logger.info("  ", f"  ... 還有 {len(diff.to_update) - 10} 個")
        
        if diff.to_delete:
            self.logger.info(LogIcons.DELETE, f"待刪除 ({len(diff.to_delete)}):")
            for filename in diff.to_delete[:10]:
                self.logger.info("  ", f"  - {filename}")
            if len(diff.to_delete) > 10:
                self.logger.info("  ", f"  ... 還有 {len(diff.to_delete) - 10} 個")
