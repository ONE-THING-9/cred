from service.session import get_latest_sessions, get_session_history
from schema import UserDetailsRequest
from logger import logger

async def get_user_details(request, user_details_request: UserDetailsRequest):
    try:
        logger.info(f"Received user details request user_id={user_details_request.user_id}")
        user_details = await get_latest_sessions(request, user_details_request.user_id)
        logger.info(f"Fetched user details: {user_details}")
        if user_details:
            logger.info(f"User details fetched user_id={user_details_request.user_id}")
            return {
                "status": "success",
                "user_details": user_details
            }
        else:
            logger.warning(f"User details not found user_id={user_details_request.user_id}")
            return {
                "status": "error",
                "user_details": []
            }
    except Exception as e:
        logger.error(f"User details error error={str(e)}, user_id={user_details_request.user_id}")
        return {
            "status": "error",
            "message": []
        }
    
async def get_session_details(request, user_id, session_id):
    try:
        logger.info(f"Received session history request session_id={session_id}")
        history = await get_session_history(request, user_id, session_id)
        if history:
            logger.info(f"Successfully retrieved session history session_id={session_id}")

            return {
                "status": "success",
                "data": {"fir": history.get("fir", ""), "police_station": history.get("police_station", ""),
                         "year": history.get("year", ""), "district": history.get("district", ""),
                         "summary": history.get("summary", ""), "pdf_link": history.get("pdf_link", "")}
            }
        else:
            logger.warning(f"Session history not found session_id={session_id}")
            return {
                "status": "error",
                "message": "Session not found"
            }
    except Exception as e:
        logger.error(f"Failed to get session history error={str(e)}, session_id={session_id}")
        return {
            "status": "error",
            "message": str(e)
        }
