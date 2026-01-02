from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import shutil
from app.services.html_export_service import html_export_service

router = APIRouter()

class ExportRequest(BaseModel):
    result_data: Dict[str, Any]

@router.post("/html", response_class=FileResponse)
async def export_html(request: ExportRequest, background_tasks: BackgroundTasks):
    """
    Export analysis result to HTML.
    Returns the HTML file as a download.
    """
    try:
        # Generate and save HTML file
        file_path = html_export_service.save_html(request.result_data)
        
        # Clean up file after sending (optional, depending on requirements)
        # For now, we keep it or let a separate cleanup process handle it.
        # If we wanted to delete it:
        # background_tasks.add_task(os.remove, file_path)
        
        filename = os.path.basename(file_path)
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="text/html"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
