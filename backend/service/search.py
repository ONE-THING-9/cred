from llm import get_llm_response
from schema import SearchRequest
from service.session import get_session_history, save_conversation_into_db
from logger import logger
from config import PATHS
import os

async def process_history(request, user_id, session_id, only_conversation=False):
    result = await get_session_history(request, user_id, session_id)
    if only_conversation:
        if 'search' in result:
            previous_search = result['search']
        else:
            previous_search = None
        return previous_search
    summary = result['summary']
    pdf_text = result['text']
    if 'search' in result:
        previous_search = result['search'][-1][1]
    else:
        previous_search = None
    if 'draft' in result:
        draft = result['draft'][-1][1]
    else:
        draft = None
    return summary, pdf_text, draft, previous_search

async def get_chat_search(request, search_request: SearchRequest):
    try:
        print("hello")
        logger.info(f"Processing chat search request")
        if search_request.user_message is None:
            previous_search = await process_history(request, search_request.user_id, search_request.session_id, only_conversation = True)
            if previous_search is not None:
                return {
                    "status": "success",
                    "message": previous_search
                }
        
        summary, pdf_text, draft, previous_search = await process_history(request, search_request.user_id, search_request.session_id)
        logger.info(f"Summary: {summary}, PDF Text: {pdf_text}, Previous Search: {previous_search}")
        
        # Use config for prompt file path
        prompt_path = os.path.join(PATHS["prompts"], 'chat_search_prompt.txt')
        with open(prompt_path, 'r') as file:
            chat_draft_prompt = file.read().strip()
            
        prompt = chat_draft_prompt.format(
            user_message=search_request.user_message, 
            previous_search=previous_search, 
            case_details=summary
        )

        response = await get_llm_response(prompt, grounding=True) #, model_name="gemini-2.5-pro-preview-03-25")

        await save_conversation_into_db(request, search_request.user_id, search_request.session_id, search_request.user_message,
                                  response,  field_name = "search")
        logger.info("Successfully generated chat search response")
        return {
            "status": "success",
            "data": {
                "search_result": response
            }
        }

    except Exception as e:
        logger.error(f"Failed to generate chat search: error={str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }