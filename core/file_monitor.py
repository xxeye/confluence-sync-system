"""
檔案監聽器
監控本地資料夾變更並觸發同步
"""

import time
import threading
from typing import Callable, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class FileMonitor:
    """檔案變更監聽器"""
    
    def __init__(
        self,
        watch_path: str,
        file_patterns: List[str],
        callback: Callable,
        delay: int = 10
    ):
        """
        初始化監聽器
        
        Args:
            watch_path: 監聽的資料夾路徑
            file_patterns: 檔案模式列表（如 ['*.png', '*.jpg']）
            callback: 檔案變更時的回調函數
            delay: 防抖延遲（秒）
        """
        self.watch_path = watch_path
        self.file_patterns = [p.lower() for p in file_patterns]
        self.callback = callback
        self.delay = delay
        self.observer = Observer()
        self.handler = _FileChangeHandler(
            file_patterns=self.file_patterns,
            callback=self.callback,
            delay=self.delay
        )
    
    def start(self) -> None:
        """啟動監聽"""
        self.observer.schedule(
            self.handler,
            self.watch_path,
            recursive=True
        )
        self.observer.start()
    
    def stop(self) -> None:
        """停止監聽"""
        self.observer.stop()
        self.observer.join()
    
    def is_alive(self) -> bool:
        """檢查監聽器是否運行中"""
        return self.observer.is_alive()


class _FileChangeHandler(FileSystemEventHandler):
    """內部檔案變更處理器"""
    
    def __init__(
        self,
        file_patterns: List[str],
        callback: Callable,
        delay: int
    ):
        super().__init__()
        self.file_patterns = file_patterns
        self.callback = callback
        self.delay = delay
        self.timer = None
        self.lock = threading.Lock()
    
    def on_any_event(self, event: FileSystemEvent) -> None:
        """處理任何檔案系統事件"""
        # 忽略目錄事件
        if event.is_directory:
            return
        
        # 檢查檔案是否符合模式
        if not self._match_patterns(event.src_path):
            return
        
        # 防抖處理：取消之前的計時器，重新設定
        with self.lock:
            if self.timer:
                self.timer.cancel()
            
            self.timer = threading.Timer(self.delay, self._trigger_callback)
            self.timer.start()
    
    def _match_patterns(self, file_path: str) -> bool:
        """檢查檔案是否符合監聽模式"""
        file_path_lower = file_path.lower()
        
        for pattern in self.file_patterns:
            if pattern.startswith('*.'):
                # 副檔名匹配
                extension = pattern[1:]  # 移除 *
                if file_path_lower.endswith(extension):
                    return True
            elif pattern in file_path_lower:
                # 包含匹配
                return True
        
        return False
    
    def _trigger_callback(self) -> None:
        """觸發回調函數"""
        try:
            self.callback()
        except Exception as e:
            print(f"回調執行錯誤: {e}")
