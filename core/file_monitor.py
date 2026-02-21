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
        self.file_patterns = file_patterns
        self.callback = callback
        self.delay = delay

        self.observer = Observer()
        self.event_handler = self._create_event_handler()

        self._last_event_time = 0
        self._timer = None
        self._lock = threading.Lock()

    def _create_event_handler(self) -> FileSystemEventHandler:
        """建立事件處理器"""

        monitor = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event: FileSystemEvent):
                if event.is_directory:
                    return

                if not monitor._match_patterns(event.src_path):
                    return

                monitor._on_file_changed()

        return Handler()

    def _on_file_changed(self) -> None:
        """檔案變更事件處理（防抖）"""
        with self._lock:
            now = time.time()
            self._last_event_time = now

            if self._timer:
                self._timer.cancel()

            self._timer = threading.Timer(self.delay, self._trigger_callback_if_idle)
            self._timer.start()

    def _trigger_callback_if_idle(self) -> None:
        """如果在 delay 期間沒有新事件，觸發回調"""
        with self._lock:
            idle_time = time.time() - self._last_event_time
            if idle_time >= self.delay:
                self._trigger_callback()

    def _match_patterns(self, file_path: str) -> bool:
        """檢查檔案是否符合監聽模式（真正的 glob / 大小寫不敏感）"""
        import fnmatch
        from pathlib import Path

        p = str(file_path).lower()
        name = Path(p).name  # 先以檔名做比對（*.png 這類）

        for pattern in self.file_patterns:
            pat = str(pattern).lower()

            # 1) 先比檔名（*.png / foo_*.jpg 等）
            if fnmatch.fnmatch(name, pat):
                return True

            # 2) 若 pattern 內包含路徑片段，再比完整 path（例如 assets/**/*.png）
            if fnmatch.fnmatch(p, pat):
                return True

        return False

    def _trigger_callback(self) -> None:
        """觸發回調函數"""
        try:
            self.callback()
        except Exception as e:
            print(f"回調執行錯誤: {e}")

    def start(self) -> None:
        """開始監聽"""
        self.observer.schedule(self.event_handler, self.watch_path, recursive=True)
        self.observer.start()

    def stop(self) -> None:
        """停止監聽"""
        if self._timer:
            self._timer.cancel()

        self.observer.stop()
        self.observer.join()