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
        self._appearance_set = False  # set_page_appearance 只需執行一次

        # 輸出 StateManager 載入時產生的警告（此時 logger 已就緒）
        for warn in self.state._load_warnings:
            self.logger.warning(LogIcons.WARNING, warn)
    
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
        dry_run: bool = False,
        notes_dirty: bool = False,
    ) -> None:
        """
        執行同步（核心流程）

        Args:
            is_startup:   是否為啟動同步
            log_reason:   日誌原因
            dry_run:      是否為模擬執行（不實際修改）
            notes_dirty:  xlsx 說明文件是否在本輪事件中被更新。
                          True 時即使圖片無變更也會重新組頁。
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

            no_img_change = not diff.has_changes() and not is_startup
            if no_img_change and not notes_dirty:
                self.logger.info(LogIcons.COMPLETE, "無變更，跳過同步")
                return

            if no_img_change and notes_dirty:
                # 圖片沒動，只有說明文件更新 → 直接走輕量路徑
                self.logger.info(LogIcons.NOTE, "說明文件已更新，重新組頁中...")
                self.run_notes_only_sync(log_reason="Notes Update")
                return

            self.logger.info(LogIcons.PROGRESS, f"變更統計: {diff.summary()}")
            if notes_dirty:
                self.logger.info(LogIcons.NOTE, "（本輪同時包含說明文件更新）")

            if dry_run:
                self.logger.info(LogIcons.WARNING, "Dry-run 模式：僅預覽，不實際執行")
                self._print_diff_details(diff, local_state)
                return

            # 4. 執行物理操作
            self._execute_operations(diff, local_state, remote_state)

            # 5. 更新頁面內容（notes_dirty 時強制全量重繪，確保說明同步）
            needs_redraw = diff.has_changes() or is_startup or notes_dirty
            self._update_page(local_state, diff, log_reason, needs_redraw)

            # 6. 儲存狀態
            self.state.save()

            self.logger.success(LogIcons.COMPLETE, "同步完成")

        except Exception as e:
            self.logger.error(LogIcons.ERROR, f"同步失敗: {e}", exc_info=e)
            raise
    

    def run_notes_only_sync(self, log_reason: str = "Notes Update") -> None:
        """
        僅重新組頁並推送，不做任何圖片上傳/刪除。
        適用於只修改說明文件（xlsx）而圖片沒有變動的情況。

        用 local_state 而非 remote_state 來分類，因為只有 local 有 width/height 資料。
        """
        try:
            self.logger.info(LogIcons.NOTE, "說明文件更新，重新組頁中...")

            # 掃描本地取得含尺寸的完整 file_data
            local_state = self._scan_local_files()

            _, current_version = self.client.get_page_content()

            categories = self.classify_assets(local_state)

            self.state.add_history_entry(
                f"{log_reason} (+0 ~0 -0)",
                self.user_id,
                self.history_keep
            )

            new_content = self.build_page_content(
                categories,
                self.state.get_history_slice(self.history_keep)
            )

            page_title = f"美術資源清單_{self.project_name}"
            self.client.update_page_content(new_content, page_title, current_version)
            self.state.save()

            self.logger.success(
                LogIcons.COMPLETE,
                f"說明文件推送完成 (Ver: {current_version + 1})"
            )

        except Exception as e:
            self.logger.error(LogIcons.ERROR, f"說明文件同步失敗: {e}", exc_info=e)
            raise

    def _full_cloud_sync(self) -> Dict[str, Dict[str, Any]]:
        """完整雲端同步（並發下載與校驗）"""
        import time
        remote_state: Dict[str, Dict[str, Any]] = {}

        # 取得頁面內容和歷史
        xhtml, _ = self.client.get_page_content()
        history = self.client.parse_history_from_page(xhtml, self.history_keep)

        # 更新狀態管理器的歷史（沿用你現有做法）
        self.state._history = history

        # 取得所有附件
        all_attachments = self.client.get_all_attachments()

        # 過濾圖片附件
        image_attachments = [
            att for att in all_attachments
            if self._is_valid_file(att.get('title', ''))
        ]

        total = len(image_attachments)
        self.logger.info(
            LogIcons.LAUNCH,
            f"平行校驗中 (執行緒: {self.max_workers['download']})... 目標: {total}"
        )

        # ✅ 防呆：避免 total=0 時除以 0
        if total == 0:
            self.logger.info(LogIcons.PROGRESS, "雲端沒有符合規則的圖片附件，略過校驗。")
            return {}

        t0 = time.perf_counter()

        failed = 0
        done = 0
        step = max(1, total // 10)

        # 統計：總下載量 / 平均耗時（依你 _download_and_hash 回傳的 size/elapsed_ms）
        total_bytes = 0
        total_elapsed_ms = 0.0

        with ThreadPoolExecutor(max_workers=self.max_workers['download']) as executor:
            futures = {
                executor.submit(self._download_and_hash, att): att
                for att in image_attachments
            }

            for future in as_completed(futures):
                att = futures[future]
                title = att.get('title', '<unknown>')

                try:
                    result = future.result()
                    if result:
                        filename, file_data = result
                        remote_state[filename] = file_data

                        size = file_data.get('size')
                        elapsed_ms = file_data.get('elapsed_ms')
                        if isinstance(size, int):
                            total_bytes += size
                        if isinstance(elapsed_ms, (int, float)):
                            total_elapsed_ms += float(elapsed_ms)
                    else:
                        failed += 1
                        self.logger.warning(LogIcons.WARNING, f"附件校驗失敗（無結果）：{title}")

                except Exception as e:
                    failed += 1
                    self.logger.error(LogIcons.ERROR, f"附件校驗異常：{title}: {e}")

                done += 1

                if done % step == 0 or done == total:
                    progress = (done * 100.0) / total
                    self.logger.info(
                        LogIcons.PROGRESS,
                        f"校驗進度: {done}/{total} ({progress:.1f}%)"
                    )

        dt = time.perf_counter() - t0
        ok = len(remote_state)

        mb = total_bytes / (1024 * 1024) if total_bytes else 0.0
        mbps = (mb / dt) if (dt > 0 and mb > 0) else 0.0
        avg_ms = (total_elapsed_ms / ok) if ok > 0 else 0.0

        self.logger.info(
            LogIcons.PROGRESS,
            f"雲端校驗完成：成功 {ok}/{total}，失敗 {failed}，耗時 {dt:.2f}s，"
            f"下載量 {mb:.2f}MB，吞吐 {mbps:.2f}MB/s，平均單張 {avg_ms:.1f}ms"
        )

        return remote_state

    def _download_and_hash(
        self,
        attachment: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """下載並計算哈希（並發任務單元）"""
        from io import BytesIO
        import time

        filename = attachment.get('title', '<unknown>')

        try:
            t0 = time.perf_counter()

            download_path = attachment.get('_links', {}).get('download')
            if not download_path:
                raise KeyError("attachment missing _links.download")

            content = self.client.download_attachment(download_path)
            file_hash = HashCalculator.calculate(BytesIO(content))

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            size = len(content)

            return filename, {
                'id': attachment.get('id'),
                'hash': file_hash,
                'size': size,
                'elapsed_ms': elapsed_ms,
            }

        except Exception as e:
            self.logger.error(
                LogIcons.ERROR,
                f"下載/校驗失敗 {filename}: {e}"
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
        
        include_dirs = set(self.file_patterns.get('include_dirs', []))
        exclude_dirs = set(self.file_patterns.get('exclude_dirs', []))

        for root, dirs, files in os.walk(target_path):
            # 資料夾白名單/黑名單篩選（原地修改 dirs 讓 os.walk 跳過子資料夾）
            if include_dirs:
                dirs[:] = [d for d in dirs if d in include_dirs]
            elif exclude_dirs:
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

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
        """
        檢查檔案是否符合 file_patterns 規則。
        資料夾層級的篩選（include_dirs / exclude_dirs）由 _scan_local_files 負責。
        """
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

        # 取得當前頁面版本（只取一次）
        current_xhtml, current_version = self.client.get_page_content()

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

            # 只更新歷史表格，傳入已取得的 xhtml
            new_content = self._update_history_only(current_xhtml)

        # 推送到 Confluence
        page_title = f"美術資源清單_{self.project_name}"

        self.client.update_page_content(
            new_content,
            page_title,
            current_version
        )

        # 設定頁面為寬版（content property，與 body 分開）
        if not self._appearance_set:
            page_width = self.config.get('confluence', {}).get('page_width', 'full-width')
            self.client.set_page_appearance(page_width)
            self._appearance_set = True

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



