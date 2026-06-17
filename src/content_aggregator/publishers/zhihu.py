"""
Zhihu (知乎) Publisher.

Implements multi-platform publishing to Zhihu.
Inherits from BasePublisher.
"""

import httpx
from datetime import datetime
from typing import Optional, Dict, Any

from .base import BasePublisher, PublisherError
from content_aggregator.models.publish import PublishResult


class ZhihuAPIError(PublisherError):
    """Custom exception for Zhihu API errors.
    
    Kept for backward compatibility.
    Inherits from PublisherError.
    """
    
    def __init__(self, message: str, error: Optional[str] = None, error_description: Optional[str] = None):
        """Initialize ZhihuAPIError.
        
        Args:
            message: Error message
            error: Zhihu API error code (optional)
            error_description: Zhihu API error description (optional)
        """
        # Map error -> code, error_description -> description
        super().__init__(message, code=error, description=error_description)
        self.error = error
        self.error_description = error_description


class ZhihuPublisher(BasePublisher):
    """Zhihu Publisher.
    
    Implements multi-platform publishing to Zhihu.
    Inherits from BasePublisher.
    """
    
    BASE_URL = "https://www.zhihu.com/api/v4"
    
    def __init__(self, client_id: str, client_secret: str, username: str, password: str):
        """Initialize ZhihuPublisher.
        
        Args:
            client_id: Zhihu OAuth client ID
            client_secret: Zhihu OAuth client secret
            username: Zhihu username
            password: Zhihu password
            
        Raises:
            ValueError: If any credential is empty
        """
        super().__init__("zhihu")
        
        if not client_id:
            raise ValueError("client_id cannot be empty")
        if not client_secret:
            raise ValueError("client_secret cannot be empty")
        if not username:
            raise ValueError("username cannot be empty")
        if not password:
            raise ValueError("password cannot be empty")
            
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        
    async def get_access_token(self) -> str:
        """Get Zhihu access token (with caching).
        
        Returns:
            access_token string
            
        Raises:
            ZhihuAPIError: If API call fails
        """
        # Check if cached token is still valid (with 5min buffer)
        if self._is_token_valid():
            return self.access_token
        
        # Fetch new token (OAuth 2.0 password grant)
        url = f"{self.BASE_URL}/oauth/token"
        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, timeout=10.0)
                data = response.json()
                
                # Check for API error (Zhihu format)
                if "error" in data:
                    raise ZhihuAPIError(
                        f"Zhihu API error: {data.get('error_description', 'Unknown error')}",
                        error=data.get("error"),
                        error_description=data.get("error_description")
                    )
                
                # Extract token
                self.access_token = data["access_token"]
                self.token_expires_at = datetime.now().timestamp() + data["expires_in"]
                
                return self.access_token
                
        except ZhihuAPIError:
            raise
        except httpx.RequestError as e:
            raise ZhihuAPIError(f"Failed to get access token: {str(e)}") from e
        except Exception as e:
            if isinstance(e, ZhihuAPIError):
                raise
            raise ZhihuAPIError(f"Unexpected error: {str(e)}") from e
        
    async def publish(self, article: Dict[str, Any]) -> PublishResult:
        """Publish article to Zhihu.
        
        Args:
            article: Article dictionary with title, content, tags, etc.
            
        Returns:
            PublishResult with status and url/message
        """
        # Validate article
        if not article.get("title"):
            return self._make_result(
                status="failed",
                message="Title is required"
            )
        
        if not article.get("content"):
            return self._make_result(
                status="failed",
                message="Content is required"
            )
        
        try:
            # Get access token
            token = await self.get_access_token()
            
            # Prepare article data
            article_data = {
                "title": article["title"],
                "content": article["content"],
                "summary": article.get("summary", ""),
                "tags": article.get("tags", [])
            }
            
            # Create article
            url = f"{self.BASE_URL}/articles"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=article_data, timeout=30.0)
                data = response.json()
                
                # Check for API error (Zhihu format)
                if "error" in data:
                    return self._make_result(
                        status="failed",
                        message=f"Zhihu API error: {data.get('error_description', 'Unknown error')}"
                    )
                
                # Success
                article_id = data.get("article_id")
                url = f"https://zhuanlan.zhihu.com/p/{article_id}" if article_id else ""
                
                return self._make_result(
                    status="success",
                    url=url,
                    message=f"Published successfully (article_id: {article_id})"
                )
                
        except ZhihuAPIError as e:
            return self._make_result(
                status="failed",
                message=str(e)
            )
        except Exception as e:
            return self._make_result(
                status="failed",
                message=f"Unexpected error: {str(e)}"
            )
