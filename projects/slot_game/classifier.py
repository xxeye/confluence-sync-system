"""
Slot Game 資源分類器
根據檔名規則將資源分類到不同類別
"""

from typing import Dict, Any, Tuple, Optional


class SlotGameClassifier:
    """Slot Game 資源分類器"""
    
    # 多國語系白名單
    LANG_WHITELIST = [
        'cn', 'cm', 'jp', 'kr', 'th', 'id', 'vn',
        'es', 'pt', 'tr', 'mm', 'bd', 'en'
    ]
    
    def classify(self, asset: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        分類單個資源
        
        Args:
            asset: 資源字典，包含 name, size, width, height 等
        
        Returns:
            (分類名稱, 群組鍵)
            - 分類名稱: layout, main, free, loading, multi_main, multi_free, 
                       multi_loading, nu_main, nu_free, nu_loading
            - 群組鍵: 用於多國語系和位圖數字的分組，其他為 None
        """
        filename = asset['name']
        parts = self._parse_filename(filename)
        
        # 1. Layout 判斷
        if 'layout' in filename.lower():
            return 'layout', None
        
        # 2. 多國語系判斷
        lang_tag = parts[4].lower() if len(parts) >= 5 else ""
        if lang_tag in self.LANG_WHITELIST:
            group_key = "_".join(parts[:4])
            scene = parts[0].lower()
            
            if scene == 'free':
                return 'multi_free', group_key
            elif scene == 'loading':
                return 'multi_loading', group_key
            else:
                return 'multi_main', group_key
        
        # 3. 位圖數字 (NU) 判斷
        if len(parts) >= 2 and parts[1].lower() == 'nu':
            group_key = "_".join(parts[:3])
            scene = parts[0].lower()
            
            if scene == 'free':
                return 'nu_free', group_key
            elif scene == 'loading':
                return 'nu_loading', group_key
            else:
                return 'nu_main', group_key
        
        # 4. 一般資源判斷
        scene = parts[0].lower()
        if scene == 'free':
            return 'free', None
        elif scene == 'loading':
            return 'loading', None
        else:
            return 'main', None
    
    def _parse_filename(self, filename: str) -> list:
        """解析檔名為部分列表"""
        # 移除副檔名
        name_without_ext = filename
        for ext in ['.png', '.jpg', '.jpeg']:
            if filename.lower().endswith(ext):
                name_without_ext = filename[:-len(ext)]
                break
        
        # 用底線分割
        return name_without_ext.split('_')
    
    def organize_assets(
        self,
        files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        組織所有資源到分類結構
        
        Args:
            files: 檔案字典 {filename: {path, hash, width, height, size}}
        
        Returns:
            分類結果字典
        """
        categories = {
            'layout': [],
            'main': [],
            'free': [],
            'loading': [],
            'multi_main': {},
            'multi_free': {},
            'multi_loading': {},
            'nu_main': {},
            'nu_free': {},
            'nu_loading': {}
        }
        
        for filename, file_data in files.items():
            asset = {
                'name': filename,
                'size': file_data['size'],
                'orig_w': file_data['width']
            }
            
            category, group_key = self.classify(asset)
            
            if group_key:
                # 多國語系或位圖數字（需要分組）
                if group_key not in categories[category]:
                    categories[category][group_key] = []
                categories[category][group_key].append(asset)
            else:
                # 一般資源（直接列表）
                categories[category].append(asset)
        
        return categories
