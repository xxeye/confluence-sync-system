"""
clear_confluence.py

互動式工具：清空 Confluence 頁面內容。
讀取 configs.txt（或 --config-list 指定的清單）中的所有專案配置，
讓使用者選擇要對哪個專案執行哪些清空操作。

可清空項目：
  1. 附件（Attachments）
  2. 頁面內容（Page Body）
  3. 本地版本紀錄快取（version_history.json + .sync_cache.json）

用法：
  python clear_confluence.py
  python clear_confluence.py --config-list configs.txt
  python clear_confluence.py --configs config/project_a.yaml config/project_b.yaml
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any

from utils.config_loader import ConfigLoader
from core.confluence_client import ConfluenceClient
from utils.logger import SyncLogger, LogIcons


# ── 空白頁面 XHTML ─────────────────────────────────────────────────────────────
_EMPTY_PAGE_XHTML = '<p></p>'





def _build_client(config: Dict[str, Any], logger: SyncLogger) -> ConfluenceClient:
    conf = config['confluence']
    return ConfluenceClient(
        base_url=conf['url'],
        email=conf['email'],
        api_token=conf['api_token'],
        page_id=conf['page_id'],
        logger=logger,
    )


# ── 選擇介面 ───────────────────────────────────────────────────────────────────

def _select_project(projects: List[Dict]) -> Dict:
    """讓使用者選擇要操作的專案"""
    if len(projects) == 1:
        p = projects[0]
        print(f"\n🎯 唯一專案：{p['name']}（{p['config_path']}），自動選取")
        return p

    print("\n📋 可用專案：")
    for i, p in enumerate(projects, 1):
        print(f"  {i}. {p['name']}  [{p['config_path']}]")
    print(f"  0. 全部執行")

    while True:
        raw = input("\n請選擇專案（輸入數字）：").strip()
        if raw == '0':
            return None  # 代表全部
        if raw.isdigit() and 1 <= int(raw) <= len(projects):
            return projects[int(raw) - 1]
        print(f"  ⚠️  請輸入 0–{len(projects)} 的數字")


def _select_operations() -> List[int]:
    """讓使用者選擇要執行哪些清空操作，可複選"""
    print("\n🗑️  請選擇要清空的項目（可複選，以逗號或空格分隔）：")
    print("  1. 附件（刪除所有雲端附件）")
    print("  2. 頁面內容（清空頁面 body）")
    print("  3. 本地版本紀錄快取（version_history.json + .sync_cache.json）")
    print("  4. 雲端頁面版本歷史（保留最新版，刪除其餘舊版）")
    print("  0. 全選（1+2+3+4）")

    while True:
        raw = input("\n請輸入選項：").strip()
        # 支援 "1,2" 或 "1 2" 或 "0"
        tokens = raw.replace(',', ' ').split()
        if '0' in tokens:
            return [1, 2, 3, 4]
        ops = []
        valid = True
        for t in tokens:
            if t.isdigit() and 1 <= int(t) <= 4:
                n = int(t)
                if n not in ops:
                    ops.append(n)
            else:
                print(f"  ⚠️  無效選項：{t}")
                valid = False
                break
        if valid and ops:
            return sorted(ops)
        print("  ⚠️  請輸入 0–3 的數字（可複選）")


def _confirm(project_name: str, ops: List[int]) -> bool:
    """二次確認，避免誤操作"""
    op_names = {1: '附件', 2: '頁面內容', 3: '本地快取', 4: '雲端版本歷史'}
    op_str = '、'.join(op_names[o] for o in ops)
    print(f"\n⚠️  即將對專案「{project_name}」清空：{op_str}")
    raw = input("確認執行？（輸入 yes 繼續，其他取消）：").strip().lower()
    return raw == 'yes'


# ── 清空操作 ───────────────────────────────────────────────────────────────────

def _clear_attachments(client: ConfluenceClient, logger: SyncLogger) -> None:
    """刪除頁面所有附件"""
    logger.info(LogIcons.PROGRESS, "取得附件列表...")
    attachments = client.get_all_attachments()

    if not attachments:
        logger.info(LogIcons.COMPLETE, "無附件，略過")
        return

    total  = len(attachments)
    done   = 0
    failed = 0

    logger.info(LogIcons.LAUNCH, f"開始刪除 {total} 個附件...")
    for att in attachments:
        title = att.get('title', att['id'])
        ok = client.delete_attachment(att['id'])
        if ok:
            done += 1
            logger.info(LogIcons.DELETE, f"[{done}/{total}] 已刪除：{title}")
        else:
            failed += 1
            logger.error(LogIcons.ERROR, f"刪除失敗：{title}")

    if failed == 0:
        logger.info(LogIcons.COMPLETE, f"附件清空完成（共 {done} 個）")
    else:
        logger.warning(LogIcons.WARNING, f"附件清空完成（成功 {done}，失敗 {failed}）")


def _clear_page_content(client: ConfluenceClient, project_name: str, logger: SyncLogger) -> None:
    """將頁面 body 清空"""
    logger.info(LogIcons.PROGRESS, "取得當前頁面版本...")
    _, current_version = client.get_page_content()

    page_title = f"美術資源清單_{project_name}"
    logger.info(LogIcons.PROGRESS, f"清空頁面內容（當前版本：{current_version}）...")

    client.update_page_content(_EMPTY_PAGE_XHTML, page_title, current_version)
    logger.info(LogIcons.COMPLETE, f"頁面內容已清空（新版本：{current_version + 1}）")


def _clear_local_cache(config: Dict[str, Any], logger: SyncLogger) -> None:
    """刪除本地版本紀錄快取檔案"""
    cache_cfg    = config.get('cache', {})
    cache_file   = Path(cache_cfg.get('remote_state_file', '.sync_cache.json'))
    history_file = Path(cache_cfg.get('history_file', 'version_history.json'))

    for f in [cache_file, history_file]:
        if f.exists():
            f.unlink()
            logger.info(LogIcons.DELETE, f"已刪除：{f}")
        else:
            logger.info(LogIcons.NOTE, f"不存在（略過）：{f}")

    logger.info(LogIcons.COMPLETE, "本地快取清除完成")


def _clear_page_versions(client, logger) -> None:
    """
    刪除頁面所有舊版本，只保留最新版。

    注意：Confluence API 在刪除版本後分頁偏移會改變，
    因此不能一次取全部再刪，而是每次重新取第一頁，
    重複執行直到只剩一個版本為止。
    """
    logger.info(LogIcons.PROGRESS, "取得頁面版本清單...")
    versions = client.get_page_versions()

    if len(versions) <= 1:
        logger.info(LogIcons.COMPLETE, "只有一個版本，無需清除")
        return

    total  = len(versions) - 1  # 預計刪除數（保留最新版）
    done   = 0
    failed = 0

    logger.info(LogIcons.LAUNCH, f"開始刪除 {total} 個舊版本（保留最新版）...")

    while True:
        # 每輪重新取第一頁，避免刪除後分頁偏移導致漏刪
        versions = client.get_page_versions()
        if len(versions) <= 1:
            break

        # 取版本號最小的那個（最舊版）來刪
        oldest = min(versions, key=lambda v: v['number'])
        num    = oldest['number']
        ok     = client.delete_page_version(num)

        if ok:
            done += 1
            logger.info(LogIcons.DELETE, f"[{done}/{total}] 已刪除版本 {num}")
        else:
            failed += 1
            logger.error(LogIcons.ERROR, f"刪除版本 {num} 失敗，停止（避免無限迴圈）")
            break  # 刪除失敗時停止，避免無限迴圈

    if failed == 0:
        logger.info(LogIcons.COMPLETE, f"版本歷史清除完成（共刪除 {done} 個版本）")
    else:
        logger.warning(LogIcons.WARNING, f"版本歷史清除完成（成功 {done}，失敗 {failed}）")


# ── 對單一專案執行 ─────────────────────────────────────────────────────────────

def _run_project(project: Dict, ops: List[int]) -> None:
    name   = project['name']
    config = project['config']

    logger = SyncLogger(f"clear_{name}")
    client = _build_client(config, logger)

    print(f"\n{'─'*50}")
    logger.info(LogIcons.LAUNCH, f"開始清空：{name}")

    if 1 in ops:
        logger.info(LogIcons.PROGRESS, "── 1. 清空附件 ──")
        _clear_attachments(client, logger)

    if 2 in ops:
        logger.info(LogIcons.PROGRESS, "── 2. 清空頁面內容 ──")
        _clear_page_content(client, name, logger)

    if 3 in ops:
        logger.info(LogIcons.PROGRESS, "── 3. 清除本地快取 ──")
        _clear_local_cache(config, logger)

    if 4 in ops:
        logger.info(LogIcons.PROGRESS, "── 4. 清除雲端版本歷史 ──")
        _clear_page_versions(client, logger)

    logger.info(LogIcons.COMPLETE, f"專案「{name}」清空完成")


# ── 主程式 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='清空 Confluence 頁面附件、內容或本地快取',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python clear_confluence.py
  python clear_confluence.py --config-list configs.txt
  python clear_confluence.py --configs config/project_a.yaml
        """
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--configs', nargs='+', metavar='YAML', help='配置文件路徑列表')
    group.add_argument('--config-list', metavar='FILE', help='配置清單文件（預設：configs.txt）')
    args = parser.parse_args()

    print("=" * 50)
    print("  Confluence 頁面清空工具")
    print("=" * 50)

    # 載入所有專案配置
    config_paths = ConfigLoader.load_config_paths(
        configs=args.configs,
        config_list=args.config_list,
    )
    projects = []
    for path in config_paths:
        try:
            config = ConfigLoader.load(path)
            projects.append({
                'config_path': path,
                'config':      config,
                'name':        config['project']['name'],
            })
            print(f"✅ 已載入：{config['project']['name']}  [{path}]")
        except Exception as e:
            print(f"❌ 載入失敗：{path}  ({e})")

    if not projects:
        print("❌ 沒有可用的專案")
        sys.exit(1)

    # 選擇專案
    selected = _select_project(projects)
    targets  = projects if selected is None else [selected]

    # 選擇操作
    ops = _select_operations()

    # 逐專案確認並執行
    for project in targets:
        if not _confirm(project['name'], ops):
            print(f"  ↩️  已取消：{project['name']}")
            continue
        try:
            _run_project(project, ops)
        except Exception as e:
            print(f"❌ 執行失敗：{project['name']}  ({e})")

    print(f"\n{'='*50}")
    print("  全部完成")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()

