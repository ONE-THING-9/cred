from llm import get_llm_response
from schema import DraftRequest
from service.session import get_session_history, save_conversation_into_db
from logger import logger
from config import PATHS
import os


async def process_history(request, user_id, session_id, only_conversation = False):
    result = await get_session_history(request, user_id, session_id)
    if only_conversation:
        if 'draft' in result:
            previous_draft = result['draft']
        else:
            previous_draft = None
        return previous_draft
    summary = result['summary']
    pdf_text = result['text']
    if 'draft' in result:
        previous_draft = result['draft'][-1][1]
    else:
        previous_draft = None
    return summary, pdf_text, previous_draft

async def get_case_details(request, case_number):
    print("hhhhhhh", case_number)
    db = request.state.case_db
    collection = db[case_number]
    existing_case = await collection.find_one({"case_number": case_number})

    if existing_case:
        logger.info(f"Case {case_number} found in database, returning cached data")
        case_details = existing_case['case_details']

        table = existing_case["judgment_details"]
        response = None
        if table:
            # print("table", table)
            print("table[0]", table[0])
            file_path = table[0].get('downloaded_file_path')
            # print("file_path", file_path)

            summary_prompt = "give me all content in the file while keeping the format same as in the file"

            response = await get_llm_response(summary_prompt, pdf_url=file_path)
        
        return case_details, response
    else:
        logger.info(f"Case {case_number} not found in database, returning None")
        return None, None


async def get_draft(request, draft_request: DraftRequest):
    try:
        # logger.info(f"Processing chat draft request", draft_request)
        # if draft_request.user_message is None:
        #     previous_draft = await process_history(request, draft_request.user_id, draft_request.session_id, only_conversation = True)
        #     if previous_draft is not None:
        #         return {
        #             "status": "success",
        #             "message": previous_draft
        #         }
        
        print("draft_request", draft_request)
        if draft_request.high_court is not None:
            court_name = draft_request.high_court
        else:
            court_name = "Supreme Court of India"
        import datetime
        import pytz

        # Define the Indian time zone
        india_tz = pytz.timezone("Asia/Kolkata")

        # Get the current datetime in the Indian time zone
        current_datetime = datetime.datetime.now(india_tz)
        print("came", draft_request.draft_type)
        print("draft_request.draft_type", draft_request.user_id)
        
        if draft_request.draft_type == "Interim Relief":
            print("isnde if")
            previous_draft = None
            prompt_path = os.path.join(PATHS["prompts"], 'interm_relief.txt')
            with open(prompt_path, 'r') as file:
                chat_draft_prompt = file.read().strip()
            case_number = "CWP-10232-2022"
            print("hello")

            case_details, latest_order = await get_case_details(request, case_number)

            prompt = chat_draft_prompt.format(
            case_details=case_details, # either use summary or full text
            previous_draft=previous_draft,  
            user_message=draft_request.user_message,
            court = court_name, 
            date = current_datetime,
            court_order = latest_order
        )
        else:
            summary, pdf_text, previous_draft = await process_history(request, draft_request.user_id, draft_request.session_id)
            logger.info(f"Summary: {summary}, PDF Text: {pdf_text}, Previous Draft: {previous_draft}")
            
            # Use config for prompt file path
            prompt_path = os.path.join(PATHS["prompts"], 'chat_draft_prompt.txt')
            with open(prompt_path, 'r') as file:
                chat_draft_prompt = file.read().strip()
            prompt = chat_draft_prompt.format(
            case_details=summary, # either use summary or full text
            previous_draft=previous_draft,  
            user_message=draft_request.user_message,
            court = court_name, 
            date = current_datetime
        )
        # print(prompt)
        response = await get_llm_response(prompt)
        logger.info("Successfully generated chat draft response")

        if draft_request.draft_type != "Interim Relief":
            print("inse")
            # Save the chat draft into the database
            await save_conversation_into_db(request,draft_request.user_id, draft_request.session_id, draft_request.user_message,
                                  response,  field_name = "draft")
        # await save_conversation_into_db(request,draft_request.user_id, draft_request.session_id, draft_request.user_message,
        #                           response,  field_name = "draft")
        
        return {
            "status": "success",
            "data": {
                "chat_draft": response
            }
        }
    except Exception as e:
        logger.error(f"Failed to generate chat draft: error={str(e)}, request_data={request}")
        return {
            "status": "error",
            "message": str(e)
        }