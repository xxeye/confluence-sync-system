"""
檔案監聽器
監控本地資料夾變更並觸發同步
"""

import fnmatch
import time
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class FileMonitor:
    """檔案變更監聽器"""

    def __init__(
        self,
        watch_path: str,
        file_patterns: List[str],
        callback: Callable,
        delay: int = 10,
        extra_files: Optional[List[str]] = None,
    ):
        """
        初始化監聽器

        Args:
            watch_path:    主監聽的資料夾路徑（圖片資料夾，recursive）
            file_patterns: 主路徑的檔案模式列表（如 ['*.png', '*.jpg']）
            callback:      變更時的回調函數，簽名為 callback(notes_dirty: bool)
                           notes_dirty=True  表示本次事件由 xlsx 觸發
                           notes_dirty=False 表示本次事件由圖片觸發
            delay:         防抖延遲（秒）
            extra_files:   額外要監聽的具體檔案路徑列表（如 xlsx 說明文件）
        """
        self.watch_path    = watch_path
        self.file_patterns = file_patterns
        self.callback      = callback
        self.delay         = delay

        # {目錄絕對路徑: {小寫檔名, ...}}
        self._extra_file_map: Dict[str, Set[str]] = {}
        for f in (extra_files or []):
            ep = Path(f).resolve()
            dir_key = str(ep.parent)
            self._extra_file_map.setdefault(dir_key, set()).add(ep.name.lower())

        self.observer = Observer()

        # 單一防抖 timer，但帶 notes_dirty flag
        self._last_event_time: float = 0
        self._notes_dirty: bool = False
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    # ── 事件處理器工廠 ────────────────────────────────────────────────────────

    def _make_main_handler(self) -> FileSystemEventHandler:
        """主目錄 handler：圖片變更，notes_dirty 維持不變"""
        monitor = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event: FileSystemEvent):
                if event.is_directory:
                    return
                if monitor._matches_main(event.src_path):
                    monitor._schedule(notes_dirty=False)

        return Handler()

    def _make_extra_handler(self, allowed_names: Set[str]) -> FileSystemEventHandler:
        """額外目錄 handler：xlsx 變更，標記 notes_dirty=True"""
        monitor = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event: FileSystemEvent):
                if event.is_directory:
                    return
                name = Path(event.src_path).name.lower()
                # 過濾 Excel（~$xxx）/ macOS（._xxx）暫存檔
                if name.startswith('~$') or name.startswith('._'):
                    return
                if name in allowed_names:
                    monitor._schedule(notes_dirty=True)

        return Handler()

    def _matches_main(self, file_path: str) -> bool:
        p    = str(file_path).lower()
        name = Path(p).name
        for pattern in self.file_patterns:
            pat = str(pattern).lower()
            if fnmatch.fnmatch(name, pat):
                return True
            if fnmatch.fnmatch(p, pat):
                return True
        return False

    # ── 防抖排程（單一 timer，notes_dirty 只增不減）──────────────────────────

    def _schedule(self, notes_dirty: bool) -> None:
        """
        重設防抖 timer。
        notes_dirty 一旦被設為 True，在 timer 觸發前不會被圖片事件清掉，
        確保「圖片 + xlsx 同時改動」時，callback 拿到的是 notes_dirty=True。
        """
        with self._lock:
            self._last_event_time = time.time()
            if notes_dirty:
                self._notes_dirty = True   # 只升不降
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay, self._fire_if_idle)
            self._timer.start()

    def _fire_if_idle(self) -> None:
        with self._lock:
            if time.time() - self._last_event_time < self.delay:
                return  # 還有新事件進來，不觸發
            notes_dirty = self._notes_dirty
            self._notes_dirty = False     # 清旗，準備下一輪

        try:
            self.callback(notes_dirty)
        except Exception as e:
            print(f"[FileMonitor] 回調執行錯誤: {e}")

    # ── 生命週期 ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        self.observer.schedule(self._make_main_handler(), self.watch_path, recursive=True)

        for dir_str, names in self._extra_file_map.items():
            if not Path(dir_str).exists():
                print(f"[FileMonitor] 額外監聽目錄不存在，略過：{dir_str}")
                continue
            self.observer.schedule(
                self._make_extra_handler(names),
                dir_str,
                recursive=False,
            )
            print(f"[FileMonitor] 額外監聽：{dir_str}  檔案：{names}")

        self.observer.start()

    def stop(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
        self.observer.stop()
        self.observer.join()
