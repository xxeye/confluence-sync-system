"""
重試裝飾器
提供自動重試機制，支援指數退避
"""

import time
from functools import wraps
from typing import Callable, Type, Tuple


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    重試裝飾器
    
    Args:
        max_attempts: 最大重試次數
        delay: 初始延遲時間（秒）
        backoff: 退避係數（每次重試延遲時間的倍數）
        exceptions: 需要重試的異常類型
    
    Returns:
        裝飾後的函數
    
    Example:
        @retry(max_attempts=3, delay=1, backoff=2)
        def upload_file(path):
            # 失敗時會自動重試 3 次
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            last_exception = None
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    attempt += 1
                    
                    if attempt >= max_attempts:
                        raise
                    
                    # 記錄重試資訊（如果有 logger 參數）
                    if 'logger' in kwargs:
                        logger = kwargs['logger']
                        logger.warning(
                            "⏳",
                            f"操作失敗，{current_delay:.1f}秒後重試 "
                            f"({attempt}/{max_attempts}): {str(e)}"
                        )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # 不應該到這裡，但為了安全起見
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    非同步重試裝飾器（為未來擴展保留）
    
    Args:
        max_attempts: 最大重試次數
        delay: 初始延遲時間（秒）
        backoff: 退避係數
        exceptions: 需要重試的異常類型
    
    Returns:
        裝飾後的非同步函數
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio
            attempt = 0
            current_delay = delay
            last_exception = None
            
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    attempt += 1
                    
                    if attempt >= max_attempts:
                        raise
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator
