"""Redis 缓存服务"""
import json
import logging
from typing import Any, Optional, Union

import redis
from redis.exceptions import ConnectionError, TimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis 缓存类"""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False

    def _get_client(self) -> redis.Redis:
        """获取 Redis 客户端（延迟连接）"""
        if self._client is None or not self._connected:
            try:
                # 记录连接参数（不记录密码）
                logger.debug(f"尝试连接 Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
                
                self._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                    db=settings.REDIS_DB,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # 测试连接
                self._client.ping()
                self._connected = True
                logger.info(f"Redis 连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
            except (ConnectionError, TimeoutError) as e:
                self._connected = False
                logger.warning(f"Redis 连接失败，将使用内存缓存: {type(e).__name__}: {e}")
                return None
            except Exception as e:
                self._connected = False
                logger.warning(f"Redis 连接异常，将使用内存缓存: {type(e).__name__}: {e}")
                return None
        return self._client

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        client = self._get_client()
        if client is None:
            return default

        try:
            value = client.get(key)
            if value is None:
                return default

            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis 获取失败: {e}")
            self._connected = False
            return default
        except Exception as e:
            logger.error(f"Redis 获取异常: {e}")
            return default

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        client = self._get_client()
        if client is None:
            return False

        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            elif not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)

            if ttl:
                result = client.setex(key, ttl, value)
            else:
                result = client.set(key, value)

            return bool(result)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis 设置失败: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Redis 设置异常: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存"""
        client = self._get_client()
        if client is None:
            return False

        try:
            result = client.delete(key)
            return bool(result)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis 删除失败: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Redis 删除异常: {e}")
            return False

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        client = self._get_client()
        if client is None:
            return False

        try:
            return bool(client.exists(key))
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis 检查失败: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Redis 检查异常: {e}")
            return False

    def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        client = self._get_client()
        if client is None:
            return False

        try:
            return bool(client.expire(key, ttl))
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis 设置过期时间失败: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Redis 设置过期时间异常: {e}")
            return False

    def clear_pattern(self, pattern: str) -> int:
        """按模式删除缓存"""
        client = self._get_client()
        if client is None:
            return 0

        try:
            keys = client.keys(pattern)
            if keys:
                return client.delete(*keys)
            return 0
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis 批量删除失败: {e}")
            self._connected = False
            return 0
        except Exception as e:
            logger.error(f"Redis 批量删除异常: {e}")
            return 0

    def is_connected(self) -> bool:
        """检查 Redis 连接状态"""
        try:
            client = self._get_client()
            if client:
                client.ping()
                self._connected = True
                return True
        except Exception as e:
            self._connected = False
            logger.debug(f"Redis 连接检查失败: {type(e).__name__}: {e}")
        return False

    def reconnect(self) -> bool:
        """重新连接 Redis"""
        self._client = None
        self._connected = False
        return self.is_connected()


# 全局 Redis 缓存实例
redis_cache = RedisCache()

