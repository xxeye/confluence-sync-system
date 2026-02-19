"""
Confluence API 客戶端
封裝所有 Confluence REST API 操作
"""

import requests
from typing import Dict, List, Optional, Tuple, Any
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup

from utils import retry, SyncLogger


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
    
    def _log(self, level: str, icon: str, message: str, exc_info=None):
        """內部日誌方法"""
        if self.logger:
            if level == 'error':
                self.logger.error(icon, message, exc_info=exc_info)
            elif level == 'warning':
                self.logger.warning(icon, message)
            else:
                self.logger.info(icon, message)
    
    @retry(max_attempts=3, delay=1, exceptions=(requests.RequestException,))
    def get_page_content(self) -> Tuple[str, int]:
        """
        取得頁面內容和版本號
        
        Returns:
            (XHTML 內容, 版本號)
        
        Raises:
            requests.RequestException: API 請求失敗
        """
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}"
        params = {'expand': 'body.storage,version'}
        
        response = requests.get(
            url,
            auth=self.auth,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        xhtml = data['body']['storage']['value']
        version = data['version']['number']
        
        return xhtml, version
    
    @retry(max_attempts=3, delay=1, exceptions=(requests.RequestException,))
    def update_page_content(
        self,
        content: str,
        title: str,
        current_version: int
    ) -> bool:
        """
        更新頁面內容
        
        Args:
            content: 新的 XHTML 內容
            title: 頁面標題
            current_version: 當前版本號
        
        Returns:
            是否成功
        
        Raises:
            requests.RequestException: API 請求失敗
        """
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}"
        
        payload = {
            'type': 'page',
            'title': title,
            'version': {'number': current_version + 1},
            'body': {
                'storage': {
                    'value': content,
                    'representation': 'storage'
                }
            }
        }
        
        response = requests.put(
            url,
            json=payload,
            auth=self.auth,
            timeout=self.timeout
        )

        if not response.ok:
            # 印出 Confluence 回傳的詳細錯誤訊息，方便診斷 XHTML 問題
            try:
                err_detail = response.json()
            except Exception:
                err_detail = response.text[:2000]
            raise requests.HTTPError(
                f"{response.status_code} Error: {response.reason}\n"
                f"Detail: {err_detail}",
                response=response
            )

        return True
    
    @retry(max_attempts=3, delay=1, exceptions=(requests.RequestException,))
    def get_all_attachments(self) -> List[Dict[str, Any]]:
        """
        取得頁面所有附件的元數據
        
        Returns:
            附件列表
        
        Raises:
            requests.RequestException: API 請求失敗
        """
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/child/attachment"
        all_attachments = []
        start = 0
        limit = 100
        
        while True:
            params = {'limit': limit, 'start': start}
            response = requests.get(
                url,
                auth=self.auth,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                break
            
            all_attachments.extend(results)
            start += limit
            
            if len(results) < limit:
                break
        
        return all_attachments
    
    @retry(max_attempts=3, delay=1, exceptions=(requests.RequestException,))
    def download_attachment(self, download_path: str) -> bytes:
        """
        下載附件內容
        
        Args:
            download_path: 附件下載路徑（來自附件元數據）
        
        Returns:
            附件二進位內容
        
        Raises:
            requests.RequestException: 下載失敗
        """
        url = f"{self.base_url}/wiki{download_path}"
        response = requests.get(
            url,
            auth=self.auth,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        return response.content
    
    @retry(max_attempts=3, delay=1, exceptions=(requests.RequestException,))
    def delete_attachment(self, attachment_id: str) -> bool:
        """
        刪除附件
        
        Args:
            attachment_id: 附件 ID
        
        Returns:
            是否成功
        
        Raises:
            requests.RequestException: 刪除失敗
        """
        url = f"{self.base_url}/wiki/rest/api/content/{attachment_id}"
        response = requests.delete(
            url,
            auth=self.auth,
            timeout=self.timeout
        )
        
        return response.status_code in [200, 204]
    
    @retry(max_attempts=3, delay=2, exceptions=(requests.RequestException,))
    def upload_attachment(
        self,
        file_path: str,
        filename: str
    ) -> Optional[str]:
        """
        上傳或更新附件（使用 PUT 原子操作）
        
        Args:
            file_path: 本地檔案路徑
            filename: 檔案名稱
        
        Returns:
            新的附件 ID，失敗返回 None
        
        Raises:
            requests.RequestException: 上傳失敗
        """
        url = f"{self.base_url}/wiki/rest/api/content/{self.page_id}/child/attachment"
        headers = {'X-Atlassian-Token': 'nocheck'}
        
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'image/png')}
            response = requests.put(
                url,
                auth=self.auth,
                headers=headers,
                files=files,
                timeout=self.timeout
            )
        
        if response.status_code == 200:
            data = response.json()
            return data['results'][0]['id']
        elif response.status_code == 409:
            # 頁面鎖定衝突，由重試機制處理
            raise requests.RequestException("Page locked conflict (409)")
        else:
            response.raise_for_status()
            return None
    
    def set_page_appearance(self, appearance: str = "full-width") -> bool:
        """
        設定頁面寬度外觀（透過 content property API）

        Confluence Cloud 的頁面寬度不在 body storage 裡，
        必須透過獨立的 content property 端點設定。

        appearance 可選值:
            "full-width"  → UI 顯示為「寬版」/「全版」
            "fixed-width" → UI 顯示為「窄版」（預設）

        此方法會自動處理「首次建立」與「已存在時更新」兩種情況。
        """
        base = f"{self.base_url}/wiki/api/v2/pages/{self.page_id}/properties"

        for key in ("content-appearance-draft", "content-appearance-published"):
            # ① 先嘗試取得現有 property（確認是否已設定過）
            get_resp = requests.get(
                base,
                auth=self.auth,
                timeout=self.timeout
            )
            existing_id   = None
            existing_ver  = None

            if get_resp.status_code == 200:
                for prop in get_resp.json().get("results", []):
                    if prop.get("key") == key:
                        existing_id  = prop.get("id")
                        existing_ver = prop.get("version", {}).get("number", 1)
                        break

            if existing_id:
                # ② 已存在 → PUT 更新
                put_resp = requests.put(
                    f"{base}/{existing_id}",
                    json={
                        "key": key,
                        "value": appearance,
                        "version": {"number": existing_ver + 1}
                    },
                    auth=self.auth,
                    timeout=self.timeout
                )
                if put_resp.status_code not in (200, 204):
                    self._log("warning", "⚠️",
                              f"更新 {key} 失敗: {put_resp.status_code}")
            else:
                # ③ 不存在 → POST 建立
                post_resp = requests.post(
                    base,
                    json={"key": key, "value": appearance},
                    auth=self.auth,
                    timeout=self.timeout
                )
                if post_resp.status_code not in (200, 201):
                    self._log("warning", "⚠️",
                              f"建立 {key} 失敗: {post_resp.status_code}")

        return True

    def parse_history_from_page(
        self,
        xhtml: str,
        max_count: int = 10
    ) -> List[Dict[str, str]]:
        """
        從頁面 XHTML 解析歷史表格
        
        Args:
            xhtml: 頁面 XHTML 內容
            max_count: 最大解析數量
        
        Returns:
            歷史記錄列表
        """
        history = []
        soup = BeautifulSoup(xhtml, 'html.parser')
        
        # 尋找「版本更新說明」標題
        h2_node = soup.find('h2', string=lambda s: s and '版本更新說明' in s)
        
        if h2_node:
            table = h2_node.find_next('table')
            if table:
                rows = table.find_all('tr')[1:max_count + 1]  # 跳過標題行
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
