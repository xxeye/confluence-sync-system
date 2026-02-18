"""
統一日誌系統
提供格式化的日誌輸出，支援終端和檔案雙重記錄
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


class SyncLogger:
    """同步系統日誌管理器"""
    
    def __init__(self, project_name, log_dir="logs"):
        self.project_name = project_name
        self.logger = logging.getLogger(project_name)
        self.logger.setLevel(logging.INFO)
        
        # 避免重複添加 handler
        if self.logger.handlers:
            return
        
        # 創建日誌目錄
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        # Console Handler（終端輸出）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File Handler（檔案輸出）
        log_file = log_path / f"{project_name}_{datetime.now():%Y%m%d}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def info(self, icon, message):
        """資訊級別日誌"""
        self.logger.info(f"{icon} {message}")
    
    def success(self, icon, message):
        """成功日誌（使用 info 級別）"""
        self.logger.info(f"{icon} {message}")
    
    def warning(self, icon, message):
        """警告日誌"""
        self.logger.warning(f"{icon} {message}")
    
    def error(self, icon, message, exc_info=None):
        """錯誤日誌"""
        if exc_info:
            self.logger.error(f"{icon} {message}", exc_info=exc_info)
        else:
            self.logger.error(f"{icon} {message}")
    
    def debug(self, message):
        """調試日誌"""
        self.logger.debug(message)


# 日誌圖示常數
class LogIcons:
    """統一的日誌圖示"""
    START = "🏁"
    CONNECT = "📡"
    LAUNCH = "🚀"
    PROGRESS = "🔄"
    SUCCESS = "✨"
    DELETE = "🗑️"
    NEW = "🆕"
    UPDATE = "🔄"
    COMPLETE = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    WATCH = "👁️"
    CLEAN = "🧹"
    UPLOAD = "📤"
    DOWNLOAD = "📥"
    PAINT = "🎨"
    NOTE = "📝"
