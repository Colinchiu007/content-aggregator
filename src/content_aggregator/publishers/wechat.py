"""
WeChat (Weixin) Official Account publisher.
"""

import httpx
import time
from typing import Optional, Dict, Any
from datetime import datetime

from content_aggregator.models.publish import PublishResult


class WechatAPIError(Exception):
    """Custom exception for WeChat API errors."""
    
    def __init__(self, message: str, errcode: Optional[int] = None, errmsg: Optional[str] = None):
        """Initialize WechatAPIError.
        
        Args:
            message: Error message
            errcode: WeChat API error code (optional)
            errmsg: WeChat API error message (optional)
        """
        super().__init__(message)
        self.errcode = errcode
        self.errmsg = errmsg


class WechatPublisher:
    """WeChat Official Account publisher.
    
    Implements multi-platform publishing to WeChat Official Account.
    """
    
    BASE_URL = "https://api.weixin.qq.com"
    
    def __init__(self, app_id: str, app_secret: str):
        """Initialize WechatPublisher.
        
        Args:
            app_id: WeChat Official Account APP ID
            app_secret: WeChat Official Account APP Secret
            
        Raises:
            ValueError: If app_id or app_secret is empty
        """
        if not app_id:
            raise ValueError("app_id cannot be empty")
        if not app_secret:
            raise ValueError("app_secret cannot be empty")
            
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0.0
        
    async def get_access_token(self) -> str:
        """Get WeChat access token (with caching).
        
        Returns:
            access_token string
            
        Raises:
            WechatAPIError: If API call fails
        """
        # Check if cached token is still valid (with 5min buffer)
        now = datetime.now().timestamp()
        if self.access_token and now < self.token_expires_at - 300:
            return self.access_token
        
        # Fetch new token
        url = f"{self.BASE_URL}/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                data = response.json()
                
                # Check for API error
                if "errcode" in data and data["errcode"] != 0:
                    raise WechatAPIError(
                        f"WeChat API error: {data.get('errmsg', 'Unknown error')}",
                        errcode=data["errcode"],
                        errmsg=data.get("errmsg")
                    )
                
                # Extract token
                self.access_token = data["access_token"]
                self.token_expires_at = now + data["expires_in"]
                
                return self.access_token
                
        except httpx.RequestError as e:
            raise WechatAPIError(f"Failed to get access token: {str(e)}") from e
        except Exception as e:
            if isinstance(e, WechatAPIError):
                raise
            raise WechatAPIError(f"Unexpected error: {str(e)}") from e
        
    async def upload_media(self, file_path: str) -> str:
        """Upload media file to WeChat.
        
        Args:
            file_path: Path to media file
            
        Returns:
            media_id string
            
        Raises:
            WechatAPIError: If upload fails (including file not found)
        """
        # Check if file exists
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            raise WechatAPIError(f"File not found: {file_path}")
        
        # Get access token
        token = await self.get_access_token()
        
        # Upload media
        url = f"{self.BASE_URL}/cgi-bin/material/add_material"
        params = {
            "access_token": token,
            "type": "image"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                with open(file_path, "rb") as f:
                    files = {"media": (path.name, f, "image/jpeg")}
                    response = await client.post(url, params=params, files=files, timeout=30.0)
                    data = response.json()
                    
                    # Check for API error
                    if "errcode" in data and data["errcode"] != 0:
                        raise WechatAPIError(
                            f"WeChat API error: {data.get('errmsg', 'Unknown error')}",
                            errcode=data["errcode"],
                            errmsg=data.get("errmsg")
                        )
                    
                    # Return media_id
                    return data["media_id"]
                    
        except WechatAPIError:
            raise
        except FileNotFoundError:
            raise WechatAPIError(f"File not found: {file_path}")
        except httpx.RequestError as e:
            raise WechatAPIError(f"Failed to upload media: {str(e)}") from e
        except Exception as e:
            if isinstance(e, WechatAPIError):
                raise
            raise WechatAPIError(f"Unexpected error: {str(e)}") from e
        
    async def create_draft(self, article: Dict[str, Any]) -> str:
        """Create draft in WeChat.
        
        Args:
            article: Article dictionary with title, content, etc.
            
        Returns:
            media_id string
            
        Raises:
            WechatAPIError: If API call fails
        """
        # Get access token
        token = await self.get_access_token()
        
        # Upload cover image
        cover_media_id = await self.upload_media(article["cover_image"])
        
        # Prepare draft data
        draft_data = {
            "articles": [{
                "title": article["title"],
                "author": article.get("author", ""),
                "digest": article.get("summary", ""),
                "content": article["content"],
                "content_source_url": article.get("source_url", ""),
                "thumb_media_id": cover_media_id
            }]
        }
        
        # Create draft
        url = f"{self.BASE_URL}/cgi-bin/draft/add"
        params = {"access_token": token}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=draft_data, timeout=30.0)
                data = response.json()
                
                # Check for API error
                if "errcode" in data and data["errcode"] != 0:
                    raise WechatAPIError(
                        f"WeChat API error: {data.get('errmsg', 'Unknown error')}",
                        errcode=data["errcode"],
                        errmsg=data.get("errmsg")
                    )
                
                # Return media_id
                return data["media_id"]
                
        except WechatAPIError:
            raise
        except httpx.RequestError as e:
            raise WechatAPIError(f"Failed to create draft: {str(e)}") from e
        except Exception as e:
            if isinstance(e, WechatAPIError):
                raise
            raise WechatAPIError(f"Unexpected error: {str(e)}") from e
        
    async def publish(self, article: Dict[str, Any]) -> PublishResult:
        """Publish article to WeChat Official Account.
        
        Args:
            article: Article dictionary with title, content, cover_image, etc.
            
        Returns:
            PublishResult with status and url/message
        """
        # Validate article
        if not article.get("title"):
            return PublishResult(
                platform="wechat",
                status="failed",
                message="Title is required"
            )
        
        if not article.get("cover_image"):
            return PublishResult(
                platform="wechat",
                status="failed",
                message="Cover image is required"
            )
        
        try:
            # Create draft
            draft_media_id = await self.create_draft(article)
            
            # Publish draft
            token = await self.get_access_token()
            url = f"{self.BASE_URL}/cgi-bin/freepublish/submit"
            params = {"access_token": token}
            publish_data = {"media_id": draft_media_id}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=publish_data, timeout=30.0)
                data = response.json()
                
                # Check for API error
                if "errcode" in data and data["errcode"] != 0:
                    return PublishResult(
                        platform="wechat",
                        status="failed",
                        message=f"WeChat API error: {data.get('errmsg', 'Unknown error')}"
                    )
                
                # Success
                publish_id = data.get("publish_id")
                msg_data_id = data.get("msg_data_id")
                url = f"https://mp.weixin.qq.com/s/{msg_data_id}" if msg_data_id else ""
                
                return PublishResult(
                    platform="wechat",
                    status="success",
                    url=url,
                    message=f"Published successfully (publish_id: {publish_id})"
                )
                
        except WechatAPIError as e:
            return PublishResult(
                platform="wechat",
                status="failed",
                message=str(e)
            )
        except Exception as e:
            return PublishResult(
                platform="wechat",
                status="failed",
                message=f"Unexpected error: {str(e)}"
            )
