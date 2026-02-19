"""
Confluence API 客戶端
封裝所有 Confluence REST API 操作
"""

from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth

from utils import SyncLogger


class ConfluenceClient:
    """Confluence API 客戶端"""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        page_id: str,
        logger: Optional[SyncLogger] = None
    ):
        """
        初始化客戶端

        Args:
            base_url: Confluence 基礎 URL
            email: 帳號 Email
            api_token: API Token
            page_id: 目標頁面 ID
            logger: 日誌記錄器
        """
        self.base_url = base_url.rstrip('/')
        self.page_id = page_id
        self.auth = HTTPBasicAuth(email, api_token)
        self.logger = logger
        self.timeout = 30

        # ✅ 使用 Session 重用連線（Keep-Alive），並統一 auth
        self.session = requests.Session()
        self.session.auth = self.auth

    def _log(self, level: str, icon: str, message: str, exc_info=None):
        """內部日誌方法"""
        if not self.logger:
            return
        if level == 'error':
            self.logger.error(icon, message, exc_info=exc_info)
        elif level == 'warning':
            self.logger.warning(icon, message)
        else:
            self.logger.info(icon, message)

    def _normalize_content_id(self, raw_id: Optional[str]) -> Optional[str]:
        """
        Confluence 有時會回傳像 'att123456' 這種 id。
        REST v1 某些 endpoint 只接受純數字 id，所以這裡統一正規化。
        """
        if not raw_id:
            return None

        s = str(raw_id).strip()
        # 常見前綴：att
        if s.startswith("att"):
            s = s[3:]

        # 只保留數字
        digits = "".join(ch for ch in s if ch.isdigit())
        return digits or None

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files=None,
        data=None,
        stream: bool = False,
        timeout: Optional[int] = None,
        ok_status: Tuple[int, ...] = (200, 201, 204),
        max_attempts: int = 5,
    ) -> requests.Response:
        """
        統一的 HTTP 入口（含重試/退避）：
        - 429：尊重 Retry-After
        - 5xx：短暫故障重試
        - 409：Confluence 鎖定/衝突類型
        - ✅ 其他 4xx（例如 404）不重試，直接拋出
        """
        if timeout is None:
            timeout = self.timeout

        last_exc: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=timeout,
                    stream=stream,
                )

                code = resp.status_code

                # ✅ 非暫時性 4xx：直接拋出（避免 404 一直重試）
                if 400 <= code <= 499 and code not in (409, 429):
                    try:
                        err_detail = resp.json()
                    except Exception:
                        err_detail = resp.text[:2000]
                    raise requests.HTTPError(
                        f"{code} Error: {resp.reason}\nDetail: {err_detail}",
                        response=resp
                    )

                # 429/409/5xx：可重試
                if code in (429, 409) or (500 <= code <= 599):
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and str(retry_after).isdigit():
                        sleep_s = int(retry_after)
                    else:
                        sleep_s = min(30, (2 ** (attempt - 1))) + random.random()

                    self._log(
                        "warning",
                        "⏳",
                        f"HTTP {code} on {method} {resp.url}，將重試（{attempt}/{max_attempts}），等待 {sleep_s:.1f}s"
                    )
                    time.sleep(sleep_s)
                    continue

                if code not in ok_status:
                    try:
                        err_detail = resp.json()
                    except Exception:
                        err_detail = resp.text[:2000]
                    raise requests.HTTPError(
                        f"{code} Error: {resp.reason}\nDetail: {err_detail}",
                        response=resp
                    )

                return resp

            except requests.RequestException as e:
                last_exc = e
                # ✅ 若是明確的非暫時性 4xx HTTPError，直接拋出
                if isinstance(e, requests.HTTPError) and getattr(e, "response", None) is not None:
                    c = e.response.status_code
                    if 400 <= c <= 499 and c not in (409, 429):
                        raise

                if attempt == max_attempts:
                    raise

                backoff = min(10, (2 ** (attempt - 1))) + random.random()
                self._log(
                    "warning",
                    "⏳",
                    f"Request error: {e}，重試中（{attempt}/{max_attempts}），等待 {backoff:.1f}s"
                )
                time.sleep(backoff)

        raise last_exc or RuntimeError("Unknown request failure")

    def get_page_content(self) -> Tuple[str, int]:
        """取得頁面內容和版本號"""
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}"
        params = {'expand': 'body.storage,version'}

        resp = self._request("GET", url, params=params, ok_status=(200,))
        data = resp.json()
        xhtml = data['body']['storage']['value']
        version = data['version']['number']
        return xhtml, version

    def update_page_content(self, content: str, title: str, current_version: int) -> bool:
        """更新頁面內容"""
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}"
        payload = {
            'type': 'page',
            'title': title,
            'version': {'number': current_version + 1},
            'body': {'storage': {'value': content, 'representation': 'storage'}}
        }

        self._request("PUT", url, json=payload, ok_status=(200, 204))
        return True

    def get_all_attachments(self) -> List[Dict[str, Any]]:
        """取得頁面所有附件的元數據"""
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/child/attachment"
        all_attachments: List[Dict[str, Any]] = []
        start = 0
        limit = 100

        while True:
            params = {'limit': limit, 'start': start}
            resp = self._request("GET", url, params=params, ok_status=(200,))
            data = resp.json()
            results = data.get('results', []) or []

            if not results:
                break

            all_attachments.extend(results)
            start += limit

            if len(results) < limit:
                break

        return all_attachments

    def download_attachment(self, download_path: str) -> bytes:
        """下載附件內容"""
        url = f"{self.base_url}/wiki{download_path}"
        resp = self._request("GET", url, ok_status=(200,))
        return resp.content

    def delete_attachment(self, attachment_id: str) -> bool:
        """刪除附件"""
        url = f"{self.base_url}/wiki/rest/api/content/{attachment_id}"
        self._request("DELETE", url, ok_status=(200, 204))
        return True

    def upload_attachment(self, file_path: str, filename: str) -> Optional[str]:
        """
        上傳或更新附件（標準 Confluence Cloud REST v1 流程）

        - 若同名附件已存在：POST /content/{page_id}/child/attachment/{attachment_id}/data 進行更新
        - 若不存在：POST /content/{page_id}/child/attachment 進行新增
        """
        headers = {"X-Atlassian-Token": "nocheck"}
        mime = self._guess_mime_type(filename)

        existing_id = self._find_attachment_id_by_filename(filename)

        # 1) 更新
        if existing_id:
            url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/child/attachment/{existing_id}/data"
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, mime)}
                resp = self._request("POST", url, headers=headers, files=files, ok_status=(200, 201))
            # 更新成功通常會回 results[0].id（可能仍帶 att 前綴）
            try:
                rid = resp.json()["results"][0]["id"]
                return self._normalize_content_id(rid) or existing_id
            except Exception:
                return existing_id

        # 2) 新增
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/child/attachment"
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, mime)}
            resp = self._request("POST", url, headers=headers, files=files, ok_status=(200, 201))

        try:
            rid = resp.json()["results"][0]["id"]
            return self._normalize_content_id(rid)
        except Exception:
            return None

    def _guess_mime_type(self, filename: str) -> str:
        """依檔名猜測 MIME type（猜不到就用 application/octet-stream）"""
        import mimetypes

        mime, _ = mimetypes.guess_type(filename)
        return mime or "application/octet-stream"
    
    def _find_attachment_id_by_filename(self, filename: str) -> Optional[str]:
        """
        在此頁面附件中找同名檔案，找到則回傳 attachment_id，否則回傳 None

        Confluence REST v1 支援用 filename filter 查附件：
        GET /wiki/rest/api/content/{page_id}/child/attachment?filename=xxx
        """
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/child/attachment"
        params = {
            "filename": filename,
            "limit": 1,
        }

        resp = self._request("GET", url, params=params, ok_status=(200,))
        data = resp.json()
        results = data.get("results", []) or []
        if not results:
            return None

        return results[0].get("id")    

    def set_page_appearance(self, appearance: str = "full-width") -> bool:
        """
        設定頁面寬度外觀（content property API, v2）

        ✅ GET 一次 properties → 建 map → draft/published 各自 PUT 或 POST
        """
        base = f"{self.base_url}/wiki/api/v2/pages/{self.page_id}/properties"

        resp = self._request("GET", base, params={"limit": 200}, ok_status=(200,))
        results = resp.json().get("results", []) or []

        prop_map: Dict[str, Dict[str, Any]] = {}
        for p in results:
            k = p.get("key")
            if not k:
                continue
            prop_map[k] = {
                "id": p.get("id"),
                "ver": (p.get("version") or {}).get("number", 1),
            }

        for key in ("content-appearance-draft", "content-appearance-published"):
            if key in prop_map and prop_map[key].get("id"):
                pid = prop_map[key]["id"]
                ver = prop_map[key]["ver"]
                self._request(
                    "PUT",
                    f"{base}/{pid}",
                    json={"key": key, "value": appearance, "version": {"number": ver + 1}},
                    ok_status=(200, 204),
                )
            else:
                self._request(
                    "POST",
                    base,
                    json={"key": key, "value": appearance},
                    ok_status=(200, 201),
                )

        return True

    def get_page_versions(self) -> List[Dict[str, Any]]:
        """取得頁面所有版本清單（由新到舊）"""
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/version"
        all_versions: List[Dict[str, Any]] = []
        start = 0
        limit = 200

        while True:
            resp = self._request(
                "GET",
                url,
                params={'limit': limit, 'start': start},
                ok_status=(200,),
            )
            data = resp.json()
            results = data.get('results', []) or []
            if not results:
                break

            all_versions.extend(results)
            start += limit

            if len(results) < limit:
                break

        return all_versions

    def delete_page_version(self, version_number: int) -> bool:
        """刪除指定頁面版本（Confluence Cloud 不允許刪除最新版本）"""
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/version/{version_number}"
        self._request("DELETE", url, ok_status=(200, 204))
        return True

    def parse_history_from_page(self, xhtml: str, max_count: int = 10) -> List[Dict[str, str]]:
        """從頁面 XHTML 解析歷史表格"""
        history: List[Dict[str, str]] = []
        soup = BeautifulSoup(xhtml, 'html.parser')

        h2_node = soup.find('h2', string=lambda s: s and '版本更新說明' in s)

        if h2_node:
            table = h2_node.find_next('table')
            if table:
                rows = table.find_all('tr')[1:max_count + 1]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        user_tag = cols[2].find('ri:user')
                        history.append({
                            'date': cols[0].get_text(strip=True),
                            'log': cols[1].get_text(strip=True),
                            'user_id': user_tag.get('ri:account-id') if user_tag else ''
                        })

        return history