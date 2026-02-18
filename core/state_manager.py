"""
狀態管理器
統一管理遠端狀態快取和版本歷史記錄
"""

import json
from pathlib import Path
from typing import Dict, List, Any
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
        self._remote_state: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, str]] = []
        self._load()
    
    def _load(self) -> None:
        """從文件載入狀態"""
        # 載入遠端狀態快取
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._remote_state = json.load(f)
            except Exception as e:
                print(f"警告：載入快取失敗，將使用空狀態: {e}")
                self._remote_state = {}
        
        # 載入版本歷史
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            except Exception as e:
                print(f"警告：載入歷史失敗，將使用空歷史: {e}")
                self._history = []
    
    def save(self) -> None:
        """儲存狀態到文件"""
        # 儲存遠端狀態快取
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self._remote_state, f, ensure_ascii=False, indent=2)
        
        # 儲存版本歷史
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)
    
    @property
    def remote_state(self) -> Dict[str, Dict[str, Any]]:
        """取得遠端狀態快取"""
        return self._remote_state
    
    @remote_state.setter
    def remote_state(self, value: Dict[str, Dict[str, Any]]) -> None:
        """設定遠端狀態快取"""
        self._remote_state = value
    
    @property
    def history(self) -> List[Dict[str, str]]:
        """取得版本歷史"""
        return self._history
    
    def update_remote_file(self, filename: str, file_id: str, file_hash: str) -> None:
        """
        更新單個檔案的遠端狀態
        
        Args:
            filename: 檔案名稱
            file_id: Confluence 附件 ID
            file_hash: 檔案哈希值
        """
        self._remote_state[filename] = {
            'id': file_id,
            'hash': file_hash
        }
    
    def remove_remote_file(self, filename: str) -> None:
        """
        移除單個檔案的遠端狀態
        
        Args:
            filename: 檔案名稱
        """
        self._remote_state.pop(filename, None)
    
    def add_history_entry(
        self,
        log_message: str,
        user_id: str,
        max_keep: int = 10
    ) -> None:
        """
        新增歷史記錄
        
        Args:
            log_message: 變更說明
            user_id: 使用者 Account ID
            max_keep: 最大保留數量
        """
        entry = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'log': log_message,
            'user_id': user_id
        }
        
        self._history.insert(0, entry)
        self._history = self._history[:max_keep]
    
    def get_history_slice(self, max_count: int) -> List[Dict[str, str]]:
        """
        取得指定數量的歷史記錄
        
        Args:
            max_count: 最大數量
        
        Returns:
            歷史記錄列表
        """
        return self._history[:max_count]
    
    def clear_cache(self) -> None:
        """清除快取（用於強制重新同步）"""
        self._remote_state = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
    
    def clear_history(self) -> None:
        """清除歷史（謹慎使用）"""
        self._history = []
        if self.history_file.exists():
            self.history_file.unlink()
