"""
多專案管理器
支援同時監聽和管理多個專案的同步
"""

import sys
import time
import argparse
import threading
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import ConfigLoader, SyncLogger, LogIcons
from core import ConfluenceClient, StateManager, FileMonitor
from projects.slot_game import SlotGameSyncEngine


# 專案類型映射
PROJECT_ENGINES = {
    'slot_game': SlotGameSyncEngine,
}


class ProjectInstance:
    """單個專案實例"""
    
    def __init__(self, config_path: str, project_id: str):
        """
        初始化專案實例
        
        Args:
            config_path: 配置文件路徑
            project_id: 專案識別碼（用於日誌區分）
        """
        self.project_id = project_id
        self.config_path = config_path
        self.config = ConfigLoader.load(config_path)
        
        # 為每個專案創建專屬日誌
        log_prefix = f"{project_id}_{self.config['project']['name']}"
        self.logger = SyncLogger(log_prefix)
        
        # 初始化組件
        self.client = ConfluenceClient(
            base_url=self.config['confluence']['url'],
            email=self.config['confluence']['email'],
            api_token=self.config['confluence']['api_token'],
            page_id=self.config['confluence']['page_id'],
            logger=self.logger
        )
        
        # 為每個專案使用獨立的狀態文件
        cache_config = self.config.get('cache', {})
        cache_file = cache_config.get('remote_state_file', '.sync_cache.json')
        history_file = cache_config.get('history_file', 'version_history.json')
        
        # 添加專案前綴避免衝突
        self.state_manager = StateManager(
            cache_file=f"{project_id}_{cache_file}",
            history_file=f"{project_id}_{history_file}"
        )
        
        # 初始化同步引擎
        project_type = self.config['project']['type']
        engine_class = PROJECT_ENGINES.get(project_type)
        
        if not engine_class:
            raise ValueError(
                f"[{project_id}] 不支援的專案類型: {project_type}"
            )
        
        self.engine = engine_class(
            config=self.config,
            confluence_client=self.client,
            state_manager=self.state_manager,
            logger=self.logger
        )
        
        self.sync_lock = threading.Lock()
        self.monitor = None
    
    def run_initial_sync(self) -> bool:
        """執行初始同步"""
        try:
            self.logger.info(
                LogIcons.START,
                f"[{self.project_id}] 執行初始同步..."
            )
            self.engine.run_sync(
                is_startup=True,
                log_reason="Startup Consistency"
            )
            return True
        except Exception as e:
            self.logger.error(
                LogIcons.ERROR,
                f"[{self.project_id}] 初始同步失敗: {e}",
                exc_info=e
            )
            return False
    
    def start_monitoring(self) -> None:
        """啟動檔案監聽"""
        file_patterns = self.config.get('file_patterns', {}).get(
            'include', ['*.png', '*.jpg', '*.jpeg']
        )
        watch_delay = self.config['sync']['watch_delay']

        # 若 config 有設定 notes_file（xlsx 說明文件），一併監聽其儲存事件
        notes_file = self.config.get('confluence', {}).get('notes_file')
        extra_files = [notes_file] if notes_file else []

        self.monitor = FileMonitor(
            watch_path=self.config['sync']['target_folder'],
            file_patterns=file_patterns,
            callback=self._on_file_change,
            delay=watch_delay,
            extra_files=extra_files,
        )

        self.monitor.start()

        suffix = f"（含說明文件：{notes_file}）" if notes_file else ""
        self.logger.info(LogIcons.WATCH, f"[{self.project_id}] 監控已啟動{suffix}")
    
    def stop_monitoring(self) -> None:
        """停止檔案監聽（含 dirty timer 的安全收尾）"""
        # 1) 停止 watchdog observer
        if self.monitor:
            try:
                self.monitor.stop()
                self.logger.info(
                    LogIcons.COMPLETE,
                    f"[{self.project_id}] 監控已停止"
                )
            except Exception as e:
                self.logger.error(
                    LogIcons.ERROR,
                    f"[{self.project_id}] 停止監控失敗: {e}",
                    exc_info=e
                )

        # 2) 取消 dirty 合併 / retry timer（避免 stop 後又觸發 sync）
        if hasattr(self, "_dirty_timer") and self._dirty_timer:
            try:
                self._dirty_timer.cancel()
            except Exception:
                pass
            self._dirty_timer = None

        # 3) 清除 dirty 狀態（純保險，避免殘留）
        if hasattr(self, "_dirty"):
            self._dirty = False
    
    def _on_file_change(self, notes_dirty: bool = False) -> None:
        """
        Dirty + 合併觸發：
        - 圖片或 xlsx 事件進來只標記 dirty / notes_dirty
        - 用 Timer 合併一波事件（避免連續觸發）
        - 若同步中拿不到 lock，延後重試
        - 同步期間又有事件，結束後自動補跑下一輪
        - notes_dirty 只升不降：圖片事件不會清掉已標記的 notes_dirty
        """
        import threading
        import time

        # ---- lazy init ----
        if not hasattr(self, "_dirty"):
            self._dirty = False
        if not hasattr(self, "_notes_dirty"):
            self._notes_dirty = False
        if not hasattr(self, "_dirty_lock"):
            self._dirty_lock = threading.Lock()
        if not hasattr(self, "_dirty_timer"):
            self._dirty_timer = None

        MERGE_WINDOW_S = 1.2
        RETRY_S = 1.0

        def _arm_timer(delay_s: float) -> None:
            with self._dirty_lock:
                if self._dirty_timer:
                    try:
                        self._dirty_timer.cancel()
                    except Exception:
                        pass
                    self._dirty_timer = None
                t = threading.Timer(delay_s, _drain_dirty)
                t.daemon = True
                self._dirty_timer = t
                t.start()

        def _drain_dirty() -> None:
            with self._dirty_lock:
                if not self._dirty:
                    return

            if not self.sync_lock.acquire(blocking=False):
                self.logger.info(
                    LogIcons.NOTE,
                    f"[{self.project_id}] 正在同步中，已標記 dirty，{RETRY_S:.1f}s 後重試"
                )
                _arm_timer(RETRY_S)
                return

            try:
                # 讀走兩個 flag，同時清零
                with self._dirty_lock:
                    self._dirty = False
                    current_notes_dirty = self._notes_dirty
                    self._notes_dirty = False

                self.logger.info(
                    LogIcons.PROGRESS,
                    f"[{self.project_id}] (dirty) 合併後開始同步..."
                )
                self.engine.run_sync(
                    is_startup=False,
                    log_reason="Watcher Sync (dirty)",
                    notes_dirty=current_notes_dirty,
                )

            except Exception as e:
                self.logger.error(
                    LogIcons.ERROR,
                    f"[{self.project_id}] 同步失敗: {e}",
                    exc_info=e
                )
                with self._dirty_lock:
                    self._dirty = True
                _arm_timer(RETRY_S)

            finally:
                self.sync_lock.release()

                with self._dirty_lock:
                    needs_more = self._dirty

                if needs_more:
                    self.logger.info(
                        LogIcons.NOTE,
                        f"[{self.project_id}] 同步期間偵測到新變更，準備補跑下一輪"
                    )
                    _arm_timer(MERGE_WINDOW_S)

        # ---- 事件進來：標記 dirty，notes_dirty 只升不降 ----
        with self._dirty_lock:
            self._dirty = True
            if notes_dirty:
                self._notes_dirty = True

        _arm_timer(MERGE_WINDOW_S)


class MultiProjectManager:
    """多專案管理器"""
    
    def __init__(self, config_paths: List[str]):
        """
        初始化多專案管理器
        
        Args:
            config_paths: 配置文件路徑列表
        """
        self.projects: Dict[str, ProjectInstance] = {}
        
        # 載入所有專案
        for i, config_path in enumerate(config_paths):
            project_id = f"P{i+1}"
            try:
                project = ProjectInstance(config_path, project_id)
                self.projects[project_id] = project
                print(f"✅ [{project_id}] 已載入: {project.config['project']['name']}")
            except Exception as e:
                print(f"❌ [{project_id}] 載入失敗: {config_path}")
                print(f"   錯誤: {e}")
    
    def run_all_once(self, parallel: bool = False) -> None:
        """
        執行所有專案的單次同步
        
        Args:
            parallel: 是否並行執行（預設為 False，循序執行）
        """
        if parallel:
            self._run_parallel_sync()
        else:
            self._run_sequential_sync()
    
    def _run_sequential_sync(self) -> None:
        """循序執行同步（一個接一個）"""
        print(f"\n🚀 開始循序同步 {len(self.projects)} 個專案...")
        print("=" * 60)
        
        success_count = 0
        for project_id, project in self.projects.items():
            if project.run_initial_sync():
                success_count += 1
            print("-" * 60)
        
        print(f"\n✅ 完成！成功: {success_count}/{len(self.projects)}")
    
    def _run_parallel_sync(self) -> None:
        """並行執行同步（同時進行）"""
        print(f"\n🚀 開始並行同步 {len(self.projects)} 個專案...")
        print("=" * 60)
        
        with ThreadPoolExecutor(max_workers=len(self.projects)) as executor:
            futures = {
                executor.submit(project.run_initial_sync): project_id
                for project_id, project in self.projects.items()
            }
            
            success_count = 0
            for future in as_completed(futures):
                project_id = futures[future]
                try:
                    if future.result():
                        success_count += 1
                except Exception as e:
                    print(f"❌ [{project_id}] 同步異常: {e}")
        
        print(f"\n✅ 完成！成功: {success_count}/{len(self.projects)}")
    
    def run_all_watch(self) -> None:
        """啟動所有專案的監聽模式"""
        print(f"\n🚀 啟動 {len(self.projects)} 個專案的監聽模式...")
        print("=" * 60)
        
        # 先執行初始同步
        for project_id, project in self.projects.items():
            if not project.run_initial_sync():
                print(f"⚠️  [{project_id}] 初始同步失敗，跳過監聽")
                continue
            print("-" * 60)
        
        # 啟動所有監聽器
        print("\n📡 啟動監聽器...")
        for project_id, project in self.projects.items():
            try:
                project.start_monitoring()
            except Exception as e:
                print(f"❌ [{project_id}] 監聽啟動失敗: {e}")
        
        print("\n✅ 所有專案監聽已啟動")
        print("📝 日誌位置: logs/")
        print("⌨️  按 Ctrl+C 停止所有監聽\n")
        
        # 保持運行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⏹️  收到停止信號...")
            self.stop_all()
    
    def stop_all(self) -> None:
        """停止所有專案的監聽"""
        print("🛑 停止所有監聽器...")
        for project_id, project in self.projects.items():
            try:
                project.stop_monitoring()
            except Exception as e:
                print(f"❌ [{project_id}] 停止失敗: {e}")
        
        print("✅ 已安全退出")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='多專案管理器 - 同時監聽多個 Confluence 專案',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 同時監聽 3 個專案
  python multi_project_manager.py \\
    --configs config/project_a.yaml config/project_b.yaml config/project_c.yaml \\
    --mode watch

  # 單次同步所有專案（循序執行）
  python multi_project_manager.py \\
    --configs config/*.yaml \\
    --mode once

  # 單次同步所有專案（並行執行，更快）
  python multi_project_manager.py \\
    --configs config/*.yaml \\
    --mode once \\
    --parallel

  # 使用配置清單文件
  python multi_project_manager.py \\
    --config-list configs.txt \\
    --mode watch
        """
    )
    
    # 配置輸入方式
    config_group = parser.add_mutually_exclusive_group(required=True)
    config_group.add_argument(
        '--configs',
        nargs='+',
        help='配置文件路徑列表（支援萬用字元，如 config/*.yaml）'
    )
    config_group.add_argument(
        '--config-list',
        help='配置清單文件（每行一個配置路徑）'
    )
    
    # 執行模式
    parser.add_argument(
        '--mode',
        choices=['once', 'watch'],
        default='watch',
        help='運行模式: once=單次同步, watch=監聽模式 (預設: watch)'
    )
    
    # 並行選項
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='並行執行同步（僅在 once 模式下有效，可大幅提升速度）'
    )
    
    args = parser.parse_args()
    
    # 收集並驗證配置文件路徑（使用統一的 ConfigLoader.load_config_paths）
    valid_configs = ConfigLoader.load_config_paths(
        configs=args.configs,
        config_list=args.config_list,
    )
    print(f"📋 找到 {len(valid_configs)} 個配置文件")
    
    # 創建多專案管理器
    try:
        manager = MultiProjectManager(valid_configs)
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        sys.exit(1)
    
    if not manager.projects:
        print("❌ 錯誤：沒有成功載入任何專案")
        sys.exit(1)
    
    # 執行對應模式
    try:
        if args.mode == 'once':
            manager.run_all_once(parallel=args.parallel)
        else:
            if args.parallel:
                print("⚠️  警告：--parallel 僅在 once 模式下有效，已忽略")
            manager.run_all_watch()
    except KeyboardInterrupt:
        print("\n⏹️  使用者中斷")
        manager.stop_all()
    except Exception as e:
        print(f"\n❌ 執行錯誤: {e}")
        manager.stop_all()
        sys.exit(1)


if __name__ == '__main__':
    main()

