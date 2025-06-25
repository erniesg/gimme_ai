"""HTTP client for workflow execution with multiple authentication types."""

import time
import json
import logging
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union, BinaryIO
from urllib.parse import urljoin, urlparse
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from ..config.workflow import AuthConfig, RetryConfig
from .r2_client import R2Client
from ..utils.security import get_secure_logger, mask_secrets

logger = get_secure_logger(__name__)


class AuthenticationError(Exception):
    """Authentication-related errors."""
    pass


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


class TimeoutError(Exception):
    """Request timeout error."""
    pass


class WorkflowHTTPClient:
    """HTTP client for workflow API calls with authentication and retry support."""
    
    def __init__(self, base_url: str, timeout: Optional[float] = 30.0):
        """
        Initialize HTTP client.
        
        Args:
            base_url: Base URL for API calls
            timeout: Default timeout for requests in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.default_timeout = timeout
        self.auth_config: Optional[AuthConfig] = None
        self.retry_config: Optional[RetryConfig] = None
        self.session = requests.Session()
        self.r2_client: Optional[R2Client] = None
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'gimme-ai-workflow/1.0',
            'Accept': 'application/json'
        })
    
    def set_auth(self, auth_config: AuthConfig) -> None:
        """Set authentication configuration."""
        if auth_config.type not in ["none", "bearer", "api_key", "basic", "custom"]:
            raise ValueError(f"Unsupported auth type: {auth_config.type}")
        
        self.auth_config = auth_config
        
        # Update session headers with auth
        auth_headers = auth_config.to_request_headers()
        self.session.headers.update(auth_headers)
    
    def set_retry_config(self, retry_config: RetryConfig) -> None:
        """Set retry configuration."""
        self.retry_config = retry_config
    
    def make_request(
        self,
        endpoint: str,
        method: str = "POST",
        payload: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        download_as_file: bool = False,
        upload_files: Optional[Dict[str, str]] = None,
        poll_for_completion: bool = False,
        poll_config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Make HTTP request with retry logic and advanced features.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            payload: Request payload
            headers: Additional headers
            timeout: Request timeout
            download_as_file: Download response as file instead of parsing
            upload_files: Files to upload (field_name: file_path)
            poll_for_completion: Poll URL until job completes
            poll_config: Polling configuration
            
        Returns:
            Response data (JSON, text, or file path if downloaded)
            
        Raises:
            RetryExhaustedError: When all retries are exhausted
            TimeoutError: When request times out
            AuthenticationError: When authentication fails
        """
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        request_timeout = timeout or self.default_timeout
        
        # Prepare headers
        request_headers = {}
        if headers:
            request_headers.update(headers)
        
        # Prepare request arguments
        request_kwargs = {
            'method': method,
            'url': url,
            'headers': request_headers,
            'timeout': request_timeout
        }
        
        # Handle file uploads
        if upload_files:
            files = self._prepare_file_uploads(upload_files)
            request_kwargs['files'] = files
            if payload:
                request_kwargs['data'] = payload  # Form data with files
        elif method.upper() != 'GET' and payload is not None:
            # Regular payload handling
            if isinstance(payload, (dict, list)):
                request_kwargs['json'] = payload
                if 'Content-Type' not in request_headers:
                    request_headers['Content-Type'] = 'application/json'
            else:
                request_kwargs['data'] = payload
        
        # Execute request with retry logic
        if self.retry_config:
            response = self._make_request_with_retry(request_kwargs)
        else:
            response = self._execute_request(request_kwargs)
        
        # Handle file download
        if download_as_file:
            return self._download_as_file(response)
        
        # Handle async job polling
        if poll_for_completion and poll_config:
            return self._poll_for_completion(response, poll_config)
        
        return response
    
    def _make_request_with_retry(self, request_kwargs: Dict[str, Any]) -> Any:
        """Execute request with retry logic."""
        retry_count = 0
        delay = self.retry_config.parse_delay_seconds()
        
        while retry_count <= self.retry_config.limit:
            try:
                return self._execute_request(request_kwargs)
            
            except Exception as e:
                # Don't retry on client errors (4xx)
                if hasattr(e, 'response') and e.response is not None:
                    if 400 <= e.response.status_code < 500:
                        raise e
                
                retry_count += 1
                
                if retry_count > self.retry_config.limit:
                    safe_error = mask_secrets(str(e))
                    logger.error(f"Request failed after {self.retry_config.limit} retries: {safe_error}")
                    raise RetryExhaustedError(f"Request failed after {self.retry_config.limit} retries: {safe_error}")
                
                # Calculate delay based on backoff strategy
                current_delay = self._calculate_backoff_delay(delay, retry_count)
                
                safe_error = mask_secrets(str(e))
                logger.warning(f"Request failed (attempt {retry_count}), retrying in {current_delay}s: {safe_error}")
                time.sleep(current_delay)
        
        # This shouldn't be reached
        raise RetryExhaustedError("Unexpected retry exhaustion")
    
    def _calculate_backoff_delay(self, base_delay: float, attempt: int) -> float:
        """Calculate delay based on backoff strategy."""
        if self.retry_config.backoff == "constant":
            return base_delay
        elif self.retry_config.backoff == "linear":
            return base_delay * attempt
        elif self.retry_config.backoff == "exponential":
            return base_delay * (2 ** (attempt - 1))
        else:
            return base_delay
    
    def _execute_request(self, request_kwargs: Dict[str, Any]) -> Any:
        """Execute a single HTTP request."""
        try:
            # Log request details with masked sensitive data
            safe_kwargs = request_kwargs.copy()
            if 'headers' in safe_kwargs:
                from ..utils.security import default_masker
                safe_kwargs['headers'] = default_masker.mask_headers(safe_kwargs['headers'])
            
            logger.debug(f"Making {safe_kwargs['method']} request to {safe_kwargs['url']}")
            
            response = self.session.request(**request_kwargs)
            
            # Check for HTTP errors
            if response.status_code >= 400:
                # Mask sensitive data in error responses
                error_text = mask_secrets(response.text) if response.text else "No response body"
                error_msg = f"HTTP {response.status_code}: {error_text}"
                if response.status_code == 401:
                    raise AuthenticationError(error_msg)
                else:
                    response.raise_for_status()
            
            # Parse response
            return self._parse_response(response)
            
        except Timeout as e:
            raise TimeoutError(f"Request timed out: {mask_secrets(str(e))}")
        
        except ConnectionError as e:
            raise Exception(f"Connection error: {mask_secrets(str(e))}")
        
        except RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                error_text = mask_secrets(e.response.text) if e.response.text else "No response body"
                error_msg = f"HTTP {e.response.status_code}: {error_text}"
                if e.response.status_code == 401:
                    raise AuthenticationError(error_msg)
            raise Exception(f"Request failed: {mask_secrets(str(e))}")
    
    def _parse_response(self, response: requests.Response) -> Any:
        """Parse HTTP response."""
        content_type = response.headers.get('Content-Type', '')
        
        try:
            # Try to parse as JSON first
            if 'application/json' in content_type or response.text.strip().startswith(('{', '[')):
                return response.json()
            else:
                return response.text
        except json.JSONDecodeError:
            # Fallback to text if JSON parsing fails
            return response.text
    
    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def _prepare_file_uploads(self, upload_files: Dict[str, str]) -> Dict[str, Any]:
        """Prepare files for upload."""
        files = {}
        for field_name, file_path in upload_files.items():
            if os.path.exists(file_path):
                files[field_name] = open(file_path, 'rb')
            else:
                logger.warning(f"File not found for upload: {file_path}")
        return files
    
    def _download_as_file(self, response_data: Any) -> str:
        """Download response content as file and return file path."""
        if isinstance(response_data, bytes):
            # Response is already binary data
            content = response_data
        elif isinstance(response_data, str) and response_data.startswith('http'):
            # Response is a URL - download the file
            file_response = self.session.get(response_data, stream=True)
            file_response.raise_for_status()
            content = file_response.content
        else:
            # Try to treat as binary
            content = str(response_data).encode()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        logger.info(f"Downloaded file to: {temp_path}")
        return temp_path
    
    def _poll_for_completion(self, initial_response: Any, poll_config: Dict[str, Any]) -> Any:
        """Poll URL until job completion."""
        poll_url = self._extract_poll_url(initial_response, poll_config)
        if not poll_url:
            logger.warning("No poll URL found in response")
            return initial_response
        
        interval = self._parse_duration(poll_config.get('poll_interval', '10s'))
        timeout = self._parse_duration(poll_config.get('poll_timeout', '30m'))
        completion_field = poll_config.get('completion_field', 'status')
        completion_values = poll_config.get('completion_values', ['completed', 'succeeded'])
        result_field = poll_config.get('result_field')
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Poll the job status
                poll_response = self.session.get(poll_url)
                poll_response.raise_for_status()
                poll_data = poll_response.json()
                
                status = poll_data.get(completion_field)
                logger.debug(f"Polling job status: {status}")
                
                if status in completion_values:
                    logger.info(f"Job completed with status: {status}")
                    if result_field and result_field in poll_data:
                        return poll_data[result_field]
                    return poll_data
                
                elif status in ['failed', 'error', 'cancelled']:
                    raise Exception(f"Job failed with status: {status}")
                
                # Wait before next poll
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error polling job: {e}")
                raise
        
        raise TimeoutError(f"Job polling timed out after {timeout}s")
    
    def _extract_poll_url(self, response: Any, poll_config: Dict[str, Any]) -> Optional[str]:
        """Extract polling URL from response."""
        if isinstance(response, dict):
            # Try common patterns
            if 'id' in response and 'urls' in response:
                # Replicate pattern
                return response['urls'].get('get')
            elif 'id' in response:
                # Generic job ID pattern - construct URL
                job_id = response['id']
                base_url = poll_config.get('poll_url_template', f"{self.base_url}/jobs/{job_id}")
                return base_url.format(job_id=job_id)
        
        return None
    
    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string to seconds."""
        if duration_str.endswith('s'):
            return float(duration_str[:-1])
        elif duration_str.endswith('m'):
            return float(duration_str[:-1]) * 60
        elif duration_str.endswith('h'):
            return float(duration_str[:-1]) * 3600
        else:
            return float(duration_str)
    
    def extract_fields(self, response: Any, field_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Extract specific fields from response data."""
        result = {}
        
        for output_key, field_path in field_mapping.items():
            value = self._get_nested_field(response, field_path)
            if value is not None:
                result[output_key] = value
        
        return result
    
    def _get_nested_field(self, data: Any, field_path: str) -> Any:
        """Get nested field from data using dot notation."""
        if not isinstance(data, dict):
            return None
        
        parts = field_path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        
        return current
    
    def setup_r2_client(self) -> None:
        """Initialize R2 client from environment variables if available."""
        try:
            self.r2_client = R2Client.from_env()
            logger.info("R2 client initialized successfully")
        except ValueError as e:
            logger.debug(f"R2 client not available: {e}")
            self.r2_client = None
    
    async def upload_to_r2(self, 
                          file_path: str, 
                          bucket: str, 
                          key: str,
                          metadata: Optional[Dict[str, str]] = None) -> str:
        """Upload file to R2 storage and return URL."""
        if not self.r2_client:
            self.setup_r2_client()
            
        if not self.r2_client:
            # Fallback to mock URL if R2 not configured
            logger.warning(f"R2 not configured, returning mock URL for {file_path}")
            return f"https://mock.r2.dev/{bucket}/{key}"
            
        return self.r2_client.upload_file(file_path, bucket, key, metadata=metadata)
    
    async def upload_data_to_r2(self,
                               data: bytes,
                               bucket: str, 
                               key: str,
                               content_type: Optional[str] = None,
                               metadata: Optional[Dict[str, str]] = None) -> str:
        """Upload data bytes to R2 storage and return URL."""
        if not self.r2_client:
            self.setup_r2_client()
            
        if not self.r2_client:
            # Fallback to mock URL if R2 not configured  
            logger.warning(f"R2 not configured, returning mock URL for data upload")
            return f"https://mock.r2.dev/{bucket}/{key}"
            
        return self.r2_client.upload_bytes(data, bucket, key, content_type, metadata)
    
    async def download_and_store_in_r2(self,
                                      url: str,
                                      bucket: str,
                                      key: str,
                                      metadata: Optional[Dict[str, str]] = None) -> str:
        """Download file from URL and store in R2."""
        if not self.r2_client:
            self.setup_r2_client()
            
        if not self.r2_client:
            # Fallback to mock URL if R2 not configured
            logger.warning(f"R2 not configured, returning mock URL for {url}")
            return f"https://mock.r2.dev/{bucket}/{key}"
            
        return self.r2_client.download_and_upload(url, bucket, key, metadata)