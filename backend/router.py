from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from service.fir_details import get_fir_details
from service.draft import get_draft
from service.search import get_chat_search
from service.user_detail import get_user_details, get_session_details
from service.session import delete_draft_field, delete_search_field
from service.login import authenticate_user, create_user, validate_session, end_session
from service.download_fir_pdf import download_fir_pdf
from service.case_details import get_case_details, get_case_file
router = APIRouter()
from schema import DraftRequest, SearchRequest, GetFirRequest, UserDetailsRequest, HistoryRequest, DownloadPdf
from schema import GetCasedetailsRequest, GetCaseDetailsResponse, GetCaseFileRequest
from service.display import get_court_display_data

from logger import logger

# Add new schema classes for authentication
class AuthRequest(BaseModel):
    user_id: str
    password: str

# Add authentication endpoints
@router.post("/authenticate")
async def login(request: AuthRequest):
    try:
        logger.info(f"Received login request for user user_id={request.user_id}")
        session_id = await authenticate_user(request.user_id, request.password)
        if session_id:
            logger.info(f"Login successfuluser_id={request.user_id}")
            return {
                "status": "success",
                "session_id": session_id
            }
        else:
            logger.warning(f"Login failed user_id={request.user_id}")
            return {
                "status": "error",
                "message": "Invalid credentials"
            }
    except Exception as e:
        logger.error(f"Login error error={str(e)}, user_id={request.user_id}")
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/signup")
async def signup(request: AuthRequest):
    try:
        logger.info(f"Received signup request user_id={request.user_id}")
        success = await create_user(request.user_id, request.password)
        if success:
            logger.info(f"Signup successful user_id={request.user_id}")
            return {
                "status": "success",
                "message": "User created successfully"
            }
        else:
            logger.warning(f"Signup failed - user exists user_id= {request.user_id}")
            return {
                "status": "error",
                "message": "User already exists"
            }
    except Exception as e:
        logger.error(f"Signup error error= {str(e)}, user_id={request.user_id}")
        return {
            "status": "error",
            "message": str(e)
        }

# Add session validation to existing endpoints
@router.post("/get-fir-details")
async def invoke_get_fir_details(request: Request, get_fir_request: GetFirRequest):
    try:
        logger.info("Received summary request")
        response = await get_fir_details(request, get_fir_request)
        logger.info("Successfully processed summary request")
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to process summary request error={str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/download-fir-pdf")
async def invoke_download_fir_pdf(request: Request, download_request: DownloadPdf):
    try:
        logger.info("Received download FIR PDF request")
        response = await download_fir_pdf(request, download_request)
        logger.info("Successfully processed download FIR PDF request")
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to process download FIR PDF request error={str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/get-draft")
async def invoke_draft(request:Request, draft_request: DraftRequest):
    try:
        return await get_draft(request, draft_request)
    except HTTPException as e:
        raise e
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/chat-search-api")
async def chat_search_api(request:Request, search_request: SearchRequest):
    try:
        return await get_chat_search(request, search_request)
    except HTTPException as he:
        raise he
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/logout")
async def logout(session_id: str = Header(None)):
    try:
        if not session_id:
            raise HTTPException(status_code=401, detail="No session provided")
            
        logger.info(f"Received logout request session_id={session_id}")
        success = await end_session(session_id)
        
        if success:
            logger.info(f"Logout successful session_id={session_id}")
            return {
                "status": "success",
                "message": "Logged out successfully"
            }
        else:
            logger.warning(f"Logout failed - invalid session session_id={session_id}")
            return {
                "status": "error",
                "message": "Invalid session"
            }
    except Exception as e:
        logger.error(f"Logout error error={str(e)}, session_id={session_id}")
        return {
            "status": "error",
            "message": str(e)
        }
    
@router.post("/get-user-details")
async def invoke_get_user_details(request: Request, user_detail_request: UserDetailsRequest):
    try:

        logger.info(f"Received user details request")
        response = await get_user_details(request, user_detail_request)
        logger.info(f"Successfully processed user details request")
        return response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to get user details error={str(e)}, ")
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/get-session-history")
async def get_session_history_api(request: Request, history_request: HistoryRequest):
    try:
        logger.info(f"Received session history request session_id={history_request.session_id}")
            
        history = await get_session_details(request, history_request.user_id, history_request.session_id)
        
        if history:
            logger.info(f"Successfully retrieved session history session_id={history_request.session_id}")
            return history
        else:
            logger.warning(f"Session history not found session_id={history_request.session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to get session history error={str(e)}, session_id={history_request.session_id}")
        return {
            "status": "error", 
            "message": str(e)
        }

@router.post("/delete-draft-conversation")
async def delete_draft_data(request: Request,user_id: str, session_id: str):
    try:
        logger.info(f"Received request to delete draft conversation={session_id}")
        
        await delete_draft_field(request, user_id, session_id)
        
        logger.info(f"deleted draft conversation session_id={session_id}")
        return {
            "status": "success"
        }
            
    except Exception as e:
        logger.error(f"delte draft conversation=={str(e)}, session_id={session_id}")
        return {
            "status": "error"
        }

@router.post("/delete-search-conversation")
async def delete_search_data(request: Request,user_id: str, session_id: str):
    try:
        logger.info(f"Received request to delete search conversation={session_id}")
        
        await delete_search_field(request, user_id, session_id)
        
        logger.info(f"deleted search conversation session_id={session_id}")
        return {
            "status": "success"
        }
            
    except Exception as e:
        logger.error(f"error delete search conversation=={str(e)}, session_id={session_id}")
        return {
            "status": "error"
        }
    
@router.post("/get-case-details")
async def invoke_case_detail(request: Request, background_task: BackgroundTasks ,get_case_detail_request: GetCasedetailsRequest):
    try:
        logger.info("Received case details request")
        response = await get_case_details(request, background_task,
                                          get_case_detail_request.year, get_case_detail_request.court,
                                           get_case_detail_request.case_type, get_case_detail_request.case_number)
        logger.info("Successfully processed case details request")
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to process case details request error={str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
from fastapi import FastAPI, HTTPException, BackgroundTasks # Assuming FastAPI/Starlette

@router.post("/get-case-file")
async def invoke_case_summary(request: Request,background_tasks: BackgroundTasks, get_file_request: GetCaseFileRequest):
    try:
        logger.info(f"Received case file request {get_file_request}")
        response = await get_case_file(request, get_file_request)
        logger.info("Successfully processed case file request")
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to process case file request error={str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    
@router.get("/get-display")
async def invoke_get_display(request: Request, court: Optional[str] = None):
    try:
        logger.info(f"Received display request ")
        response = await get_court_display_data(request)
        logger.info("Successfully processed display request")
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to process display request error={str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }