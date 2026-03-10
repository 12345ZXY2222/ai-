from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.api.endpoints import router as api_router
from app.api.llm_experiment import router as llm_experiment_router
from app.api.simulation_repair import router as simulation_repair_router
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import os

load_dotenv()


# ---------- WebSocket for Real-time Updates ----------
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, world_id: str):
        await websocket.accept()
        if world_id not in self.active_connections:
            self.active_connections[world_id] = []
        self.active_connections[world_id].append(websocket)
        print(f"WebSocket connected for world {world_id}, total connections: {len(self.active_connections[world_id])}")
    
    def disconnect(self, websocket: WebSocket, world_id: str):
        if world_id in self.active_connections:
            self.active_connections[world_id].remove(websocket)
            if not self.active_connections[world_id]:
                del self.active_connections[world_id]
        print(f"WebSocket disconnected for world {world_id}")
    
    async def broadcast_to_world(self, world_id: str, message: dict):
        if world_id not in self.active_connections:
            return
        dead_connections = []
        for connection in self.active_connections[world_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to WebSocket: {e}")
                dead_connections.append(connection)
        for conn in dead_connections:
            self.disconnect(conn, world_id)

manager = ConnectionManager()
# ---------- End WebSocket ----------

app = FastAPI(title="AI Simulation Platform")

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

# Mount uploads directory
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Standardized Error Handling ----------
class ErrorResponse:
    """Standard error response format."""
    def __init__(self, code: str, message: str, detail: Optional[Any] = None):
        self.error = {
            "code": code,
            "message": message,
            "detail": detail
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return self.error

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with standardized format."""
    from fastapi.responses import JSONResponse
    error = ErrorResponse(
        code="http_error",
        message=exc.detail,
        detail={"status_code": exc.status_code}
    )
    return JSONResponse(status_code=exc.status_code, content=error.to_dict())

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle request validation errors."""
    from fastapi.responses import JSONResponse
    error = ErrorResponse(
        code="validation_error",
        message="Invalid request parameters",
        detail=exc.errors()
    )
    return JSONResponse(status_code=422, content=error.to_dict())

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle any unhandled exceptions."""
    import traceback
    from fastapi.responses import JSONResponse
    # Log the full exception for debugging
    print(f"Unhandled exception: {exc}")
    traceback.print_exc()
    error = ErrorResponse(
        code="internal_server_error",
        message="An internal server error occurred",
        detail=str(exc) if app.debug else None
    )
    return JSONResponse(status_code=500, content=error.to_dict())

# ---------- End Error Handling ----------

app.include_router(api_router, prefix="/api")
app.include_router(llm_experiment_router, prefix="/api")
app.include_router(simulation_repair_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "AI Simulation Platform Backend is running"}


@app.websocket("/ws/{world_id}")
async def websocket_endpoint(websocket: WebSocket, world_id: str):
    await manager.connect(websocket, world_id)
    try:
        while True:
            # Keep connection alive, client can send ping
            data = await websocket.receive_text()
            # Optional: handle client messages (e.g., ping/pong)
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, world_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
