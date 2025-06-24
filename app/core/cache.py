"""
Redis caching utilities for the application.
"""
from typing import Optional, Dict, Any, Union, TypeVar, Generic, Type
import json
import redis.asyncio as redis
from fastapi import HTTPException
from contextlib import asynccontextmanager

from app.core.config import settings

T = TypeVar('T')

class RedisClient:
    """Redis client wrapper with connection pooling and error handling."""
    
    def __init__(self, url: str):
        """Initialize the Redis client.
        
        Args:
            url: Redis connection URL
        """
        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._url = url
    
    async def connect(self):
        """Create a Redis connection pool."""
        if not self._redis_pool:
            try:
                self._redis_pool = await aioredis.from_url(
                    self._url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20
                )
            except Exception as e:
                raise RuntimeError(f"Failed to connect to Redis: {str(e)}")
    
    async def close(self):
        """Close the Redis connection pool."""
        self._redis.close()
        self._redis.connection_pool.disconnect()
    
    async def get(self, key: str, model: Type[T] = dict) -> Optional[T]:
        """Get a value from Redis.
        
        Args:
            key: Cache key
            model: The model to deserialize the value into
            
        Returns:
            The cached value or None if not found
        """
        try:
            value = self._redis.get(key)
            if value:
                return model(**json.loads(value)) if model != dict else json.loads(value)
            return None
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Redis get operation failed: {str(e)}"
            )
    
    async def set(self, key: str, value: Union[Dict[str, Any], Any], expire: int = 3600) -> bool:
        """Set a value in Redis.
        
        Args:
            key: Cache key
            value: Value to cache (dict or Pydantic model)
            expire: Expiration time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Handle Pydantic models and dicts
            serialized = json.dumps(value.dict() if hasattr(value, 'dict') else value)
            return self._redis.set(key, serialized, ex=expire) is not None
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Redis set operation failed: {str(e)}"
            )
    
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if the key was deleted, False if it didn't exist
        """
        try:
            return self._redis.delete(key) > 0
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Redis delete operation failed: {str(e)}"
            )


# Global Redis client instance
_redis_client = None


@asynccontextmanager
async def get_redis_client() -> RedisClient:
    """Get a Redis client instance as an async context manager.
    
    Yields:
        A RedisClient instance
    """
    global _redis_client
    if _redis_client is None:
        if not settings.REDIS_URL:
            raise RuntimeError("REDIS_URL is not configured in settings")
        _redis_client = RedisClient(settings.REDIS_URL)
    
    try:
        yield _redis_client
    finally:
        # Don't close the client here as it's meant to be reused
        pass


async def init_redis():
    """Initialize the Redis connection."""
    # The connection is lazy, so just getting the client is enough
    await get_redis_client().__aenter__()


async def close_redis():
    """Close the Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
