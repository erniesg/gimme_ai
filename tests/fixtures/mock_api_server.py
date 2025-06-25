#!/usr/bin/env python3
"""
Mock API server for testing workflow patterns.
Simulates various API endpoints with configurable behavior.
"""

import asyncio
import json
import time
import random
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
import uvicorn
import threading

@dataclass
class MockEndpoint:
    """Configuration for a mock endpoint."""
    path: str
    method: str = "GET"
    response_data: Dict[str, Any] = field(default_factory=dict)
    status_code: int = 200
    delay_seconds: float = 0
    failure_rate: float = 0  # 0.0 to 1.0
    failure_count: int = 0  # Fail N times then succeed
    current_failures: int = 0
    headers: Dict[str, str] = field(default_factory=dict)

class MockAPIServer:
    """Mock API server for testing workflow patterns."""
    
    def __init__(self, port: int = 8899):
        self.port = port
        self.app = FastAPI(title="Mock API Server", version="1.0.0")
        self.endpoints: Dict[str, MockEndpoint] = {}
        self.request_log: List[Dict[str, Any]] = []
        self.server_thread: Optional[threading.Thread] = None
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup dynamic routes for the mock server."""
        
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            """Log all requests for testing purposes."""
            start_time = time.time()
            
            # Log request
            request_data = {
                "timestamp": start_time,
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
            }
            
            # Try to read body
            try:
                body = await request.body()
                if body:
                    request_data["body"] = body.decode()
            except:
                pass
            
            self.request_log.append(request_data)
            
            response = await call_next(request)
            
            # Log response
            request_data["response_time"] = time.time() - start_time
            request_data["status_code"] = response.status_code
            
            return response
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": time.time()}
        
        @self.app.get("/admin/requests")
        async def get_request_log():
            """Get request log for testing."""
            return {"requests": self.request_log}
        
        @self.app.delete("/admin/requests")
        async def clear_request_log():
            """Clear request log."""
            self.request_log.clear()
            return {"message": "Request log cleared"}
        
        @self.app.post("/admin/endpoints")
        async def add_endpoint(endpoint: Dict[str, Any]):
            """Add a new mock endpoint."""
            path = endpoint["path"]
            self.endpoints[path] = MockEndpoint(**endpoint)
            return {"message": f"Endpoint {path} added"}
        
        @self.app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def dynamic_endpoint(path: str, request: Request):
            """Handle dynamic endpoints based on configuration."""
            full_path = f"/{path}"
            method = request.method
            
            # Check if this endpoint exists
            if full_path not in self.endpoints:
                # Log available endpoints for debugging
                available = list(self.endpoints.keys())
                raise HTTPException(
                    status_code=404, 
                    detail=f"Endpoint {method} {full_path} not configured. Available: {available}"
                )
            
            endpoint = self.endpoints[full_path]
            
            # Check method matching (optional, but good practice)
            if endpoint.method != "ANY" and endpoint.method != method:
                raise HTTPException(
                    status_code=405, 
                    detail=f"Method {method} not allowed for {full_path}. Expected: {endpoint.method}"
                )
            
            # Simulate delay
            if endpoint.delay_seconds > 0:
                await asyncio.sleep(endpoint.delay_seconds)
            
            # Simulate failures
            should_fail = False
            if endpoint.failure_count > 0 and endpoint.current_failures < endpoint.failure_count:
                endpoint.current_failures += 1
                should_fail = True
            elif endpoint.failure_rate > 0 and random.random() < endpoint.failure_rate:
                should_fail = True
            
            if should_fail:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Simulated failure for {full_path}"
                )
            
            # Return configured response
            return JSONResponse(
                content=endpoint.response_data,
                status_code=endpoint.status_code,
                headers=endpoint.headers
            )
    
    def add_endpoint(self, endpoint: MockEndpoint):
        """Add an endpoint to the mock server."""
        self.endpoints[endpoint.path] = endpoint
    
    def start(self, background: bool = True):
        """Start the mock server."""
        if background:
            def run_server():
                uvicorn.run(self.app, host="127.0.0.1", port=self.port, log_level="error")
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # Wait a bit for server to start
            time.sleep(1)
        else:
            uvicorn.run(self.app, host="127.0.0.1", port=self.port)
    
    def stop(self):
        """Stop the mock server."""
        # Note: In a real implementation, we'd need proper shutdown
        pass
    
    @property
    def base_url(self) -> str:
        """Get the base URL of the mock server."""
        return f"http://127.0.0.1:{self.port}"

# Predefined endpoint configurations for common scenarios
class MockAPIEndpoints:
    """Predefined endpoint configurations for testing."""
    
    @staticmethod
    def derivativ_question_generation() -> List[MockEndpoint]:
        """Endpoints that simulate Derivativ question generation API."""
        return [
            MockEndpoint(
                path="/api/questions/generate",
                method="POST",
                response_data={
                    "question_ids": ["q1", "q2", "q3"],
                    "topic": "algebra",
                    "status": "generated",
                    "generation_time": "2.5s"
                },
                delay_seconds=2.5  # Simulate realistic generation time
            ),
            MockEndpoint(
                path="/api/documents/generate",
                method="POST",
                response_data={
                    "document_id": "doc_123",
                    "status": "created",
                    "page_count": 5
                },
                delay_seconds=1.0
            ),
            MockEndpoint(
                path="/api/documents/store",
                method="POST",
                response_data={
                    "storage_id": "store_456",
                    "url": "https://storage.derivativ.ai/doc_123.pdf",
                    "formats": ["pdf", "docx"]
                },
                delay_seconds=0.5
            )
        ]
    
    @staticmethod
    def openai_simulation() -> List[MockEndpoint]:
        """Endpoints that simulate OpenAI API."""
        return [
            MockEndpoint(
                path="/v1/chat/completions",
                method="POST",
                response_data={
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": "gpt-3.5-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "This is a mock response from OpenAI API simulation."
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 15,
                        "total_tokens": 35
                    }
                },
                delay_seconds=1.0,
                headers={"Content-Type": "application/json"}
            )
        ]
    
    @staticmethod
    def unreliable_api() -> List[MockEndpoint]:
        """Endpoints that simulate unreliable APIs for testing retry logic."""
        return [
            MockEndpoint(
                path="/api/unreliable",
                method="POST",
                response_data={"status": "success", "attempt": 3},
                failure_count=2  # Fail twice, then succeed
            ),
            MockEndpoint(
                path="/api/flaky", 
                method="GET",
                response_data={"data": "success"},
                failure_rate=0.3  # 30% failure rate
            ),
            MockEndpoint(
                path="/api/slow",
                method="GET", 
                response_data={"message": "slow response"},
                delay_seconds=5.0  # Test timeout handling
            )
        ]

async def test_mock_server():
    """Test the mock server functionality."""
    print("🧪 Testing Mock API Server...")
    
    # Start server
    server = MockAPIServer(port=8899)
    
    # Add some test endpoints
    for endpoint in MockAPIEndpoints.derivativ_question_generation():
        server.add_endpoint(endpoint)
    
    for endpoint in MockAPIEndpoints.openai_simulation():
        server.add_endpoint(endpoint)
    
    server.start(background=True)
    
    # Test the endpoints
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        # Test health check
        async with session.get(f"{server.base_url}/health") as resp:
            data = await resp.json()
            assert data["status"] == "healthy"
            print("✅ Health check works")
        
        # Test Derivativ question generation
        async with session.post(
            f"{server.base_url}/api/questions/generate",
            json={"topic": "algebra", "count": 3}
        ) as resp:
            data = await resp.json()
            assert "question_ids" in data
            print("✅ Question generation endpoint works")
        
        # Test OpenAI simulation
        async with session.post(
            f"{server.base_url}/v1/chat/completions",
            json={"model": "gpt-3.5-turbo", "messages": []}
        ) as resp:
            data = await resp.json()
            assert "choices" in data
            print("✅ OpenAI simulation works")
        
        # Check request log
        async with session.get(f"{server.base_url}/admin/requests") as resp:
            log_data = await resp.json()
            assert len(log_data["requests"]) >= 3
            print("✅ Request logging works")
    
    print("🎉 Mock API Server tests passed!")

if __name__ == "__main__":
    asyncio.run(test_mock_server())