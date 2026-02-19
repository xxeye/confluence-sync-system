"""
哈希計算器
提供檔案內容的 MD5 哈希計算，用於精確比對
"""

import hashlib
from typing import Union
from io import BytesIO


class HashCalculator:
    """檔案哈希計算器"""
    
    @staticmethod
    def calculate(file_source: Union[str, bytes, BytesIO]) -> str:
        """
        計算檔案的 MD5 哈希值
        
        Args:
            file_source: 可以是：
                - 檔案路徑（str）
                - 二進位數據（bytes）
                - BytesIO 物件
        
        Returns:
            32 位十六進位 MD5 哈希字串
        
        Raises:
            Exception: 計算失敗
        
        Example:
            # 從檔案路徑計算
            hash1 = HashCalculator.calculate('/path/to/file.png')
            
            # 從二進位數據計算
            hash2 = HashCalculator.calculate(b'binary data')
            
            # 從 BytesIO 計算
            hash3 = HashCalculator.calculate(BytesIO(b'data'))
        """
        try:
            if isinstance(file_source, str):
                # 讀取本地檔案
                with open(file_source, 'rb') as f:
                    data = f.read()
            elif isinstance(file_source, bytes):
                # 直接使用二進位數據
                data = file_source
            elif isinstance(file_source, BytesIO):
                # 從 BytesIO 讀取
                data = file_source.getvalue()
            else:
                raise TypeError(
                    f"不支援的類型: {type(file_source)}，"
                    f"僅支援 str, bytes, BytesIO"
                )
            
            # 計算 MD5
            return hashlib.md5(data).hexdigest()
            
        except Exception as e:
            raise RuntimeError(f"哈希計算失敗: {e}") from e
    
    @staticmethod
    def compare(hash1: str, hash2: str) -> bool:
        """
        比較兩個哈希值是否相同
        
        Args:
            hash1: 哈希值 1
            hash2: 哈希值 2
        
        Returns:
            是否相同
        """
        return hash1.lower() == hash2.lower()

