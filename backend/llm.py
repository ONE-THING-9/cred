from google import genai
import httpx
from google.genai import types
from logger import logger
import os
gemini_api_key = os.environ.get('GEMINI_API_KEY')
client = genai.Client(api_key=gemini_api_key)

async def get_llm_response(prompt, pdf_url=None, grounding=None, model_name="gemini-2.0-flash", temp=.5, top_p=.5, max_tokens=512):
    try:
        logger.info(f"Starting LLM response generation: model={model_name}, has_pdf={bool(pdf_url)}, has_grounding={bool(grounding)}")
        
        config = None
        if grounding:
            logger.debug("Configuring grounding tools")
            config = types.GenerateContentConfig(
                tools=[types.Tool(
                    google_search=types.GoogleSearchRetrieval
                )]
            )
        if pdf_url:
            try:
                with open(pdf_url, 'rb') as f:
                    doc_data = f.read()
                logger.debug(f"Successfully read PDF file: pdf_path={pdf_url}")
            except Exception as e:
                logger.error(f"Failed to read PDF file: error={str(e)}, pdf_path={pdf_url}")
                raise
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(
                        data=doc_data,
                        mime_type='application/pdf',
                    ),
                    prompt], config=config)
        else:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt], config=config)
        output = response.candidates[0].content.parts[0].text
        return output
    except Exception as e:
        logger.error(f"Failed to generate LLM response: error={str(e)}")
        raise e