from fastapi import APIRouter, Form, File, UploadFile, HTTPException
from typing import Optional
import base64
import uuid

from app.models import AnalysisResponse, DetailedAnalysis
from app.services import analysis_engine
from app.database import storage

router = APIRouter()

@router.post("/verify", response_model=AnalysisResponse)
async def verify_content(
    content_type: str = Form(..., description="Type of content: text, url, or image"),
    content: str = Form(..., description="Content to analyze"),
    language: Optional[str] = Form("en", description="Language preference: hi or en"),
    user_id: Optional[str] = Form(None, description="Optional user identifier"),
    file: UploadFile = File(None, description="Optional file upload for images")
):
    """
    Core content verification endpoint
    
    Supports three types of analysis:
    - text: Direct text analysis
    - url: Website/link credibility check  
    - image: Image manipulation detection
    """
    
    try:
        # Handle file upload for images
        if file and content_type == "image":
            # Read file content
            file_content = await file.read()
            # Convert to base64 for processing (mock)
            content = base64.b64encode(file_content).decode('utf-8')
        
        # Validate content type
        if content_type not in ["text", "url", "image"]:
            raise HTTPException(status_code=400, detail="Invalid content_type. Must be 'text', 'url', or 'image'")
        
        # Process content through analysis engine
        analysis_result = analysis_engine.process_content(content_type, content, language)
        
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Create response object
        response = AnalysisResponse(
            analysis_id=analysis_id,
            verdict=analysis_result["verdict"],
            confidence_score=analysis_result["confidence_score"],
            summary=analysis_result["summary"],
            processing_time=analysis_result["processing_time"],
            detailed_analysis=analysis_result["detailed_analysis"]
        )
        
        # Save to storage
        storage_data = {
            "analysis_id": analysis_id,
            "content_type": content_type,
            "content": content if content_type != "image" else "[IMAGE_DATA]",  # Don't store full base64
            "language": language,
            "user_id": user_id,
            "verdict": response.verdict,
            "confidence_score": response.confidence_score,
            "summary": response.summary,
            "processing_time": response.processing_time,
            "detailed_analysis": response.detailed_analysis.dict()
        }
        
        success = storage.save_analysis(analysis_id, storage_data)
        if not success:
            print(f"Warning: Failed to save analysis {analysis_id} to storage")
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/results/{analysis_id}")
async def get_analysis_results(analysis_id: str):
    """
    Retrieve detailed analysis results by ID
    """
    try:
        result = storage.get_analysis(analysis_id)
        if not result:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return result
        
    except Exception as e:
        if "Analysis not found" in str(e):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analysis: {str(e)}")


@router.get("/archive")
async def get_archive(limit: int = 20, user_id: Optional[str] = None):
    """
    Get analysis archive/history
    """
    try:
        analyses = storage.get_all_analyses(limit)
        
        # Filter by user_id if provided
        if user_id:
            analyses = [a for a in analyses if a.get("user_id") == user_id]
        
        return {
            "analyses": analyses,
            "total": len(analyses)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve archive: {str(e)}")