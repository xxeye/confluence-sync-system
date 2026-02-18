"""
Confluence Sync System - 主入口
支援多專案管理與監聽模式
"""

import sys
import time
import argparse
import threading
from pathlib import Path

from utils import ConfigLoader, SyncLogger, LogIcons
from core import ConfluenceClient, StateManager, FileMonitor
from projects.slot_game import SlotGameSyncEngine


# 專案類型映射
PROJECT_ENGINES = {
    'slot_game': SlotGameSyncEngine,
    # 未來可以加入更多專案類型
    # 'other_project': OtherProjectSyncEngine,
}


class SyncApplication:
    """同步應用程式"""
    
    def __init__(self, config_path: str):
        """
        初始化應用程式
        
        Args:
            config_path: 配置文件路徑
        """
        # 載入配置
        self.config = ConfigLoader.load(config_path)
        
        # 初始化日誌
        self.logger = SyncLogger(self.config['project']['name'])
        
        # 初始化 Confluence 客戶端
        self.client = ConfluenceClient(
            base_url=self.config['confluence']['url'],
            email=self.config['confluence']['email'],
            api_token=self.config['confluence']['api_token'],
            page_id=self.config['confluence']['page_id'],
            logger=self.logger
        )
        
        # 初始化狀態管理器
        cache_config = self.config.get('cache', {})
        self.state_manager = StateManager(
            cache_file=cache_config.get('remote_state_file', '.sync_cache.json'),
            history_file=cache_config.get('history_file', 'version_history.json')
        )
        
        # 初始化同步引擎
        project_type = self.config['project']['type']
        engine_class = PROJECT_ENGINES.get(project_type)
        
        if not engine_class:
            raise ValueError(
                f"不支援的專案類型: {project_type}\n"
                f"可用類型: {', '.join(PROJECT_ENGINES.keys())}"
            )
        
        self.engine = engine_class(
            config=self.config,
            confluence_client=self.client,
            state_manager=self.state_manager,
            logger=self.logger
        )
        
        # 同步鎖（防止並發同步）
        self.sync_lock = threading.Lock()
    
    def run_once(self, dry_run: bool = False) -> None:
        """
        執行單次同步
        
        Args:
            dry_run: 是否為模擬執行
        """
        self.logger.info(LogIcons.START, "執行首次雲端同步...")
        
        try:
            self.engine.run_sync(
                is_startup=True,
                log_reason="Startup Consistency",
                dry_run=dry_run
            )
        except KeyboardInterrupt:
            self.logger.info(LogIcons.WARNING, "使用者中斷")
            sys.exit(0)
        except Exception as e:
            self.logger.error(LogIcons.ERROR, f"同步失敗: {e}", exc_info=e)
            sys.exit(1)
    
    def run_watch(self) -> None:
        """執行監聽模式"""
        # 先執行一次初始同步
        self.run_once()
        
        # 初始化檔案監聽器
        file_patterns = self.config.get('file_patterns', {}).get('include', ['*.png', '*.jpg', '*.jpeg'])
        watch_delay = self.config['sync']['watch_delay']
        
        monitor = FileMonitor(
            watch_path=self.config['sync']['target_folder'],
            file_patterns=file_patterns,
            callback=self._on_file_change,
            delay=watch_delay
        )
        
        # 啟動監聽
        monitor.start()
        self.logger.info(LogIcons.WATCH, "監控模式已啟動，按 Ctrl+C 停止...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info(LogIcons.WARNING, "停止監控...")
            monitor.stop()
            self.logger.info(LogIcons.COMPLETE, "已安全退出")
    
    def _on_file_change(self) -> None:
        """檔案變更回調"""
        # 使用鎖防止並發同步
        if self.sync_lock.acquire(blocking=False):
            try:
                self.logger.info(LogIcons.PROGRESS, "偵測到檔案變更，開始同步...")
                self.engine.run_sync(
                    is_startup=False,
                    log_reason="Watcher Sync"
                )
            except Exception as e:
                self.logger.error(LogIcons.ERROR, f"同步失敗: {e}", exc_info=e)
            finally:
                self.sync_lock.release()
        else:
            self.logger.warning(LogIcons.WARNING, "上一次同步尚未完成，跳過此次觸發")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='Confluence Sync System - 多專案資源自動同步系統',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 監聽模式（持續運行）
  python main.py --config config/project_a.yaml --mode watch
  
  # 單次執行模式
  python main.py --config config/project_a.yaml --mode once
  
  # Dry-run 模式（僅預覽變更）
  python main.py --config config/project_a.yaml --mode once --dry-run
        """
    )
    
    parser.add_argument(
        '--config',
        required=True,
        help='配置文件路徑 (例如: config/project_a.yaml)'
    )
    
    parser.add_argument(
        '--mode',
        choices=['once', 'watch'],
        default='watch',
        help='運行模式: once=單次執行, watch=監聽模式 (預設: watch)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry-run 模式：僅預覽變更，不實際執行（僅在 once 模式下有效）'
    )
    
    args = parser.parse_args()
    
    # 檢查配置文件是否存在
    if not Path(args.config).exists():
        print(f"❌ 錯誤：配置文件不存在: {args.config}")
        sys.exit(1)
    
    # 創建應用程式實例
    try:
        app = SyncApplication(args.config)
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        sys.exit(1)
    
    # 執行對應模式
    if args.mode == 'once':
        app.run_once(dry_run=args.dry_run)
    else:
        if args.dry_run:
            print("⚠️  警告：Dry-run 模式僅在 once 模式下有效，已忽略")
        app.run_watch()


if __name__ == '__main__':
    main()
