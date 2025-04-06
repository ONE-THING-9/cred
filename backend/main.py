import os 
os.environ['GEMINI_API_KEY'] = "*****"

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient
from router import router as summary_router
# Create FastAPI app instance
app = FastAPI(root_path="/legal")

# Create middleware to attach session_db to request
class SessionDBMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Attach the session_db to the request object
        request.state.session_db = request.app.state.session_db
        response = await call_next(request)
        return response
class CaseDBMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Attach the session_db to the request object
        request.state.case_db = request.app.state.case_db
        response = await call_next(request)
        return response
class DBMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Attach the session_db to the request object
        request.state.db_client = request.app.state.db_client
        response = await call_next(request)
        return response
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Add session db middleware
app.add_middleware(SessionDBMiddleware)
app.add_middleware(CaseDBMiddleware)
app.add_middleware(DBMiddleware)

# MongoDB connection setup
@app.on_event("startup")
async def startup_db_client():
    app.state.db_client = AsyncIOMotorClient("mongodb://localhost:27017")
    app.state.session_db = app.state.db_client["session_db"]
    app.state.case_db = app.state.db_client["case_db"]


@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.db_client.close()

# Include routers
app.include_router(summary_router)

@app.get("/alive")
async def root():
    return {"message": "Welcome to FastAPI"}

# Dependency to get the MongoDB database
def get_db(request: Request, db_name: str):
    return getattr(request.app.state, db_name)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)