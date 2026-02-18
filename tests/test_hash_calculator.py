"""
測試哈希計算器
"""

import pytest
from io import BytesIO
from core.hash_calculator import HashCalculator


class TestHashCalculator:
    """測試 HashCalculator"""
    
    def test_calculate_from_bytes(self):
        """測試從 bytes 計算哈希"""
        data = b"Hello, World!"
        hash1 = HashCalculator.calculate(data)
        hash2 = HashCalculator.calculate(data)
        
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 為 32 位十六進位
    
    def test_calculate_from_bytesio(self):
        """測試從 BytesIO 計算哈希"""
        data = b"Test data"
        bio = BytesIO(data)
        
        hash1 = HashCalculator.calculate(bio)
        hash2 = HashCalculator.calculate(data)
        
        assert hash1 == hash2
    
    def test_compare_hashes(self):
        """測試哈希比較"""
        hash1 = "abc123def456"
        hash2 = "ABC123DEF456"  # 大小寫不同
        hash3 = "xyz789"
        
        assert HashCalculator.compare(hash1, hash2) is True
        assert HashCalculator.compare(hash1, hash3) is False
    
    def test_different_data_different_hash(self):
        """測試不同數據產生不同哈希"""
        data1 = b"Data 1"
        data2 = b"Data 2"
        
        hash1 = HashCalculator.calculate(data1)
        hash2 = HashCalculator.calculate(data2)
        
        assert hash1 != hash2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
