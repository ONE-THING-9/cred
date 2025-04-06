import uuid
import datetime
import os
from config import PATHS

async def create_session(request, user_id: str, police_station: str, fir_number: str):
    db = request.state.session_db
    collection = db[user_id]
    session_id = str(uuid.uuid4())
    user_data = {"session_id": session_id, "created_at": datetime.datetime.now(),
                 "title": f"{police_station}_{fir_number}"}
    result = await collection.insert_one(user_data)
    return session_id

async def save_into_session_db(request, data, session_id: str, user_id: str):
    print(data)
    db = request.state.session_db
    collection = db[user_id]
    result = await collection.update_one({"session_id": session_id}, {"$set": data})
    return result.modified_count > 0

async def get_session_history(request, user_id: str, session_id: str):
    db = request.state.session_db
    collection = db[user_id]
    result = await collection.find_one({"session_id": session_id})
    return result

async def save_conversation_into_db(request, user_id: str, session_id: str, user_message: str, response: str, field_name: str):
    db = request.state.session_db
    collection = db[user_id]
    session = await collection.find_one({"session_id": session_id})
    
    if session and field_name in session:
        if isinstance(session[field_name], list):
            session[field_name].append((user_message, response))
        else:
            session[field_name] = [(user_message, response)]
    else:
        session[field_name] = [(user_message, response)]
    
    result = await collection.update_one({"session_id": session_id}, {"$set": {field_name: session[field_name]}})
    return result.modified_count > 0

async def get_latest_sessions(request, user_id: str):
    db = request.state.session_db
    collection = db[user_id]
    cursor = collection.find().sort("created_at", -1).limit(5)
    sessions = await cursor.to_list(length=5)
    return [{"session_id": session["session_id"], "title": session.get("title", "")} for session in sessions]

async def get_existing_session(request, user_id: str, fir_number: str, police_station: str, district: str, year):
    """
    Check if a session exists for the given FIR details and user
    Returns the session data if found, None otherwise
    """
    print(user_id, fir_number, police_station, district, year)
    print("dtype", type(user_id), type(fir_number), type(police_station), type(district), type(year))
    try:
        db = request.state.session_db
        collection = db[user_id]
        existing_session = await collection.find_one({
            "fir": fir_number,
            "police_station": police_station,
            "district": district,
            "year": year
        })
        return existing_session
    except Exception as e:
        return None

async def delete_draft_field(request, user_id: str, session_id: str):
    """
    Delete the 'draft' field from the session if it exists.
    """
    db = request.state.session_db
    collection = db[user_id]
    session = await collection.find_one({"session_id": session_id})
    
    if session and "draft" in session:
        result = await collection.update_one(
            {"session_id": session_id},
            {"$unset": {"draft": None}}
        )
        return result.modified_count > 0
    raise Exception("Draft not found")

async def delete_search_field(request, user_id: str, session_id: str):
    """
    Delete the 'search' field from the session if it exists.
    """
    db = request.state.session_db
    collection = db[user_id]
    session = await collection.find_one({"session_id": session_id})
    
    if session and "search" in session:
        result = await collection.update_one(
            {"session_id": session_id},
            {"$unset": {"search": None}}
        )
        return result.modified_count > 0
    raise Exception("search not found")

# New function to get file path using the configured base paths
def get_file_path(file_type, filename):
    """
    Get the full path for a file using the configured base paths
    
    Args:
        file_type: Type of file (downloads, uploads, temp, logs)
        filename: Name of the file
        
    Returns:
        Full path to the file
    """
    if file_type not in PATHS:
        raise ValueError(f"Invalid file type: {file_type}")
    
    return os.path.join(PATHS[file_type], filename)
