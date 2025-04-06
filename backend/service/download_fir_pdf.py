from fastapi.responses import FileResponse
from fastapi import HTTPException
from schema import DownloadPdf
from logger import logger
import os


async def download_fir_pdf(request, download_request: DownloadPdf):
    try:
        logger.info(f"Processing download FIR PDF request: session_id={download_request.session_id}, user_id={download_request.user_id}")
        
        # Get session collection for the user
        db = request.state.session_db
        collection = db[download_request.user_id]
        
        # Find the session by ID
        session = await collection.find_one({"session_id": download_request.session_id})
        
        if not session:
            logger.error(f"Session not found: session_id={download_request.session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get PDF path from the session
        pdf_path = session.get("pdf_link")
        
        if not pdf_path:
            logger.error(f"PDF link not found in session: session_id={download_request.session_id}")
            raise HTTPException(status_code=404, detail="PDF link not found in session")
        
        # Check if PDF file exists
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found at path: {pdf_path}")
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        logger.info(f"Successfully found PDF at path: {pdf_path}")
        
        # Return PDF file
        return FileResponse(
            path=pdf_path,
            filename=os.path.basename(pdf_path),
            media_type='application/pdf'
        )
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to download FIR PDF: error={str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download FIR PDF: {str(e)}") 