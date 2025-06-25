"""R2 storage client for workflow file handling."""

import os
import tempfile
import boto3
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class R2Client:
    """Cloudflare R2 storage client using S3-compatible API."""
    
    def __init__(self, 
                 account_id: str,
                 access_key_id: str, 
                 secret_access_key: str,
                 endpoint_url: Optional[str] = None):
        """Initialize R2 client.
        
        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID  
            secret_access_key: R2 secret access key
            endpoint_url: Custom endpoint URL (optional)
        """
        if not endpoint_url:
            endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
            
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name='auto'  # R2 uses 'auto' region
        )
        
        self.account_id = account_id
        
    @classmethod
    def from_env(cls) -> 'R2Client':
        """Create R2 client from environment variables."""
        required_vars = [
            'CLOUDFLARE_ACCOUNT_ID',
            'R2_ACCESS_KEY_ID', 
            'R2_SECRET_ACCESS_KEY'
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
            
        return cls(
            account_id=os.getenv('CLOUDFLARE_ACCOUNT_ID'),
            access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY')
        )
    
    def upload_bytes(self, 
                    data: bytes, 
                    bucket: str, 
                    key: str,
                    content_type: Optional[str] = None,
                    metadata: Optional[Dict[str, str]] = None) -> str:
        """Upload bytes to R2 bucket.
        
        Args:
            data: Bytes to upload
            bucket: R2 bucket name
            key: Object key/path
            content_type: MIME type
            metadata: Custom metadata
            
        Returns:
            Public URL to uploaded object
        """
        try:
            put_args = {
                'Bucket': bucket,
                'Key': key, 
                'Body': data
            }
            
            if content_type:
                put_args['ContentType'] = content_type
                
            if metadata:
                put_args['Metadata'] = metadata
                
            self.client.put_object(**put_args)
            
            # Generate public URL
            url = f"https://pub-{self.account_id}.r2.dev/{key}"
            logger.info(f"Uploaded to R2: {url}")
            return url
            
        except Exception as e:
            logger.error(f"R2 upload failed: {e}")
            raise
    
    def upload_file(self,
                   file_path: str,
                   bucket: str, 
                   key: str,
                   content_type: Optional[str] = None,
                   metadata: Optional[Dict[str, str]] = None) -> str:
        """Upload file to R2 bucket.
        
        Args:
            file_path: Local file path
            bucket: R2 bucket name  
            key: Object key/path
            content_type: MIME type
            metadata: Custom metadata
            
        Returns:
            Public URL to uploaded object
        """
        with open(file_path, 'rb') as f:
            data = f.read()
            
        if not content_type:
            # Basic content type detection
            if key.endswith('.json'):
                content_type = 'application/json'
            elif key.endswith('.txt'):
                content_type = 'text/plain'
            elif key.endswith('.mp3'):
                content_type = 'audio/mpeg'
            elif key.endswith('.png'):
                content_type = 'image/png'
            elif key.endswith('.jpg') or key.endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif key.endswith('.mp4'):
                content_type = 'video/mp4'
                
        return self.upload_bytes(data, bucket, key, content_type, metadata)
    
    def download_and_upload(self,
                                 url: str,
                                 bucket: str,
                                 key: str,
                                 metadata: Optional[Dict[str, str]] = None) -> str:
        """Download file from URL and upload to R2.
        
        Args:
            url: URL to download from
            bucket: R2 bucket name
            key: Object key/path  
            metadata: Custom metadata
            
        Returns:
            Public URL to uploaded object
        """
        import requests
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type')
            data = response.content
            
            return self.upload_bytes(data, bucket, key, content_type, metadata)
                
        except Exception as e:
            logger.error(f"Download and upload failed: {e}")
            raise
    
    def list_objects(self, bucket: str, prefix: str = "") -> list:
        """List objects in bucket with optional prefix.
        
        Args:
            bucket: R2 bucket name
            prefix: Key prefix filter
            
        Returns:
            List of object keys
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix
            )
            
            objects = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': f"https://pub-{self.account_id}.r2.dev/{obj['Key']}"
                    })
                    
            return objects
            
        except Exception as e:
            logger.error(f"List objects failed: {e}")
            raise
    
    def delete_object(self, bucket: str, key: str) -> bool:
        """Delete object from bucket.
        
        Args:
            bucket: R2 bucket name
            key: Object key/path
            
        Returns:
            True if successful
        """
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted from R2: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False