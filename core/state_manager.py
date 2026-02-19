"""
狀態管理器
統一管理遠端狀態快取和版本歷史記錄
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class StateManager:
    """同步狀態管理器"""

    def __init__(self, cache_file: str, history_file: str):
        """
        初始化狀態管理器

        Args:
            cache_file: 遠端狀態快取文件路徑
            history_file: 版本歷史記錄文件路徑
        """
        self.cache_file = Path(cache_file)
        self.history_file = Path(history_file)

        # { filename: { id, hash, ... } }
        self._remote_state: Dict[str, Dict[str, Any]] = {}

        # [ { date, log, user_id } ... ] 最新在前
        self._history: List[Dict[str, str]] = []

        # _load() 中產生的警告，由上層用 logger 輸出
        self._load_warnings: List[str] = []
        self._load()

    def _load(self) -> None:
        """從文件載入狀態"""
        # 載入遠端狀態快取
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._remote_state = json.load(f)
            except Exception as e:
                self._remote_state = {}
                self._load_warnings.append(f"遠端狀態快取載入失敗: {e}")

        # 載入版本歷史
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except Exception as e:
                self._history = []
                self._load_warnings.append(f"版本歷史記錄載入失敗: {e}")

    def save(self) -> None:
        """儲存狀態到文件（原子寫入，避免中斷導致 JSON 損壞）"""
        import os
        from tempfile import NamedTemporaryFile

        def _atomic_write(path: Path, obj) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=str(path.parent),
                suffix=".tmp",
            ) as tf:
                json.dump(obj, tf, ensure_ascii=False, indent=2)
                tf.flush()
                os.fsync(tf.fileno())
                tmp_name = tf.name
            os.replace(tmp_name, str(path))

        _atomic_write(self.cache_file, self._remote_state)
        _atomic_write(self.history_file, self._history)

    # ─────────────────────────────────────────────────────────────
    # remote_state
    # ─────────────────────────────────────────────────────────────
    @property
    def remote_state(self) -> Dict[str, Dict[str, Any]]:
        """取得遠端狀態快取"""
        return self._remote_state

    @remote_state.setter
    def remote_state(self, state: Dict[str, Dict[str, Any]]) -> None:
        """設定遠端狀態快取"""
        self._remote_state = state
        self.save()

    def update_remote_file(self, filename: str, attachment_id: str, file_hash: str) -> None:
        """
        更新/新增單一遠端檔案狀態（sync_engine 依賴）
        """
        self._remote_state[filename] = {"id": attachment_id, "hash": file_hash}

    def remove_remote_file(self, filename: str) -> None:
        """
        移除單一遠端檔案狀態（sync_engine 依賴）
        """
        if filename in self._remote_state:
            del self._remote_state[filename]

    # ─────────────────────────────────────────────────────────────
    # history
    # ─────────────────────────────────────────────────────────────
    @property
    def history(self) -> List[Dict[str, str]]:
        """取得版本歷史記錄"""
        return self._history

    def get_history_slice(self, keep: int = 10) -> List[Dict[str, str]]:
        """
        取得指定數量的歷史（sync_engine 依賴）
        """
        if keep <= 0:
            return []
        return self._history[:keep]

    def add_history_entry(self, log: str, user_id: str, keep: int = 10) -> None:
        """
        新增歷史記錄（sync_engine 依賴的名稱與簽名）
        """
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "log": log,
            "user_id": user_id,
        }
        self._history.insert(0, entry)
        if keep and keep > 0:
            self._history = self._history[:keep]

    # ─────────────────────────────────────────────────────────────
    # backward-compatible alias（保留你原本的方法名，避免其他地方還在用）
    # ─────────────────────────────────────────────────────────────
    def add_history(self, log: str, user_id: str) -> None:
        """舊介面：等同 add_history_entry(log, user_id, keep=10)"""
        self.add_history_entry(log, user_id, keep=10)

    def get_load_warnings(self) -> List[str]:
        """取得載入警告列表"""
        return self._load_warnings