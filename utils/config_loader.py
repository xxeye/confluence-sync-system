"""
配置載入器
支援 YAML 配置文件載入和環境變數替換
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """配置載入器"""
    
    @staticmethod
    def load(config_path: str) -> Dict[str, Any]:
        """
        載入配置文件
        
        Args:
            config_path: 配置文件路徑
        
        Returns:
            配置字典
        
        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置格式錯誤
        """
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 替換環境變數
        config = ConfigLoader._replace_env_vars(config)
        
        # 驗證必要欄位
        ConfigLoader._validate_config(config)
        
        return config
    
    @staticmethod
    def _replace_env_vars(obj: Any) -> Any:
        """
        遞迴替換配置中的環境變數
        支援 ${VAR_NAME} 和 $VAR_NAME 格式
        """
        if isinstance(obj, dict):
            return {k: ConfigLoader._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [ConfigLoader._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # 匹配 ${VAR_NAME} 或 $VAR_NAME
            pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
            
            def replacer(match):
                var_name = match.group(1) or match.group(2)
                value = os.getenv(var_name)
                if value is None:
                    raise ValueError(
                        f"環境變數 '{var_name}' 未設定，"
                        f"請執行: export {var_name}='your_value'"
                    )
                return value
            
            return re.sub(pattern, replacer, obj)
        else:
            return obj
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> None:
        """
        驗證配置的必要欄位
        
        Raises:
            ValueError: 配置驗證失敗
        """
        required_fields = [
            ('project', 'name'),
            ('project', 'type'),
            ('confluence', 'url'),
            ('confluence', 'page_id'),
            ('confluence', 'email'),
            ('confluence', 'api_token'),
            ('confluence', 'user_account_id'),
            ('sync', 'target_folder'),
        ]
        
        for *path, field in required_fields:
            obj = config
            try:
                for key in path:
                    obj = obj[key]
                if field not in obj:
                    raise KeyError
            except (KeyError, TypeError):
                field_path = '.'.join(path + [field])
                raise ValueError(f"配置缺少必要欄位: {field_path}")
    
    @staticmethod
    def get_nested(config: Dict[str, Any], path: str, default: Any = None) -> Any:
        """
        取得嵌套配置值
        
        Args:
            config: 配置字典
            path: 點分隔的路徑，如 'sync.max_workers.download'
            default: 預設值
        
        Returns:
            配置值或預設值
        
        Example:
            value = ConfigLoader.get_nested(config, 'sync.max_workers.download', 15)
        """
        keys = path.split('.')
        obj = config
        
        try:
            for key in keys:
                obj = obj[key]
            return obj
        except (KeyError, TypeError):
            return default
