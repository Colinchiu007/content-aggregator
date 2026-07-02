"""
Base Publisher class.

Provides common functionality for all publishers.
"""

import httpx
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime

from content_aggregator.models.publish import PublishResult


class PublisherError(Exception):
    """Base exception for publisher errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, description: Optional[str] = None):
        """Initialize PublisherError.
        
        Args:
            message: Error message
            code: Error code (optional)
            description: Error description (optional)
        """
        super().__init__(message)
        self.code = code
        self.description = description


class BasePublisher(ABC):
    """Base class for all publishers.
    
    Provides common functionality:
    - Access token management (with caching)
    - HTTP client helpers
    - Error handling
    - Logging
    """
    
    # Default timeouts
    DEFAULT_TIMEOUT = 30.0
    TOKEN_CACHE_BUFFER = 300  # 5 minutes buffer
    
    def __init__(self, platform: str):
        """Initialize BasePublisher.
        
        Args:
            platform: Platform name (e.g., "wechat", "zhihu")
        """
        self.platform = platform
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0.0
        
    @abstractmethod
    async def get_access_token(self) -> str:
        """Get access token (with caching).
        
        Returns:
            access_token string
            
        Raises:
            PublisherError: If token fetch fails
        """
        pass
        
    @abstractmethod
    async def publish(self, article: Dict[str, Any]) -> PublishResult:
        """Publish article to platform.
        
        Args:
            article: Article dictionary with title, content, etc.
            
        Returns:
            PublishResult with status and url/message
        """
        pass
        
    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid.
        
        Returns:
            True if token is valid (with buffer), False otherwise
        """
        now = datetime.now().timestamp()
        return self.access_token is not None and now < self.token_expires_at - self.TOKEN_CACHE_BUFFER
        
    def _make_result(self, status: str, message: str, url: Optional[str] = None) -> PublishResult:
        """Create PublishResult with platform field.
        
        Args:
            status: "success" or "failed"
            message: Result message
            url: URL of published article (optional)
            
        Returns:
            PublishResult instance
        """
        return PublishResult(
            platform=self.platform,
            status=status,
            message=message,
            url=url
        )
        
    async def _http_get(self, url: str, token: Optional[str] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Make HTTP GET request.
        
        Args:
            url: Request URL
            token: Bearer token (optional)
            timeout: Request timeout (optional, uses DEFAULT_TIMEOUT)
            
        Returns:
            Response JSON as dict
            
        Raises:
            PublisherError: If request fails
        """
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=timeout or self.DEFAULT_TIMEOUT
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.RequestError as e:
            raise PublisherError(f"HTTP GET failed: {str(e)}") from e
            
    async def _http_post(self, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None, token: Optional[str] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Make HTTP POST request.
        
        Args:
            url: Request URL
            data: Form data (optional)
            json: JSON data (optional)
            token: Bearer token (optional)
            timeout: Request timeout (optional, uses DEFAULT_TIMEOUT)
            
        Returns:
            Response JSON as dict
            
        Raises:
            PublisherError: If request fails
        """
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=data,
                    json=json,
                    headers=headers,
                    timeout=timeout or self.DEFAULT_TIMEOUT
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.RequestError as e:
            raise PublisherError(f"HTTP POST failed: {str(e)}") from e
            
    def _check_api_error(self, data: Dict[str, Any], error_keys: list[str] = None) -> None:
        """Check if API response contains error.
        
        Args:
            data: API response data
            error_keys: List of error key names to check (default: ["errcode", "error"])
            
        Raises:
            PublisherError: If API error found
        """
        if error_keys is None:
            error_keys = ["errcode", "error"]
            
        for key in error_keys:
            if key in data:
                # WeChat format: {"errcode": 40001, "errmsg": "..."}
                if key == "errcode" and data[key] != 0:
                    msg = data.get("errmsg", "Unknown error")
                    raise PublisherError(
                        f"API error: {msg}",
                        code=str(data[key]),
                        description=msg
                    )
                # Zhihu format: {"error": "invalid_client", "error_description": "..."}
                elif key == "error":
                    msg = data.get("error_description", "Unknown error")
                    raise PublisherError(
                        f"API error: {msg}",
                        code=data[key],
                        description=msg
                    )
