import os
import json
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response
from app.core.config import OUTPUT_SRS_DIR

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
    responses={404: {"description": "Job not found"}},
)

# In-memory job store (in production, use Redis or a database)
job_store: Dict[str, Dict[str, Any]] = {}

def create_job() -> str:
    """Create a new job and return its ID"""
    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "PROCESSING",
        "message": "작업이 시작되었습니다.",
        "result": None,
        "error": None,
        "attempts": 0
    }
    return job_id

def update_job_status(job_id: str, status: str, result: Any = None, error: str = None, message: str = None):
    """Update job status and result"""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    current_job = job_store[job_id]
    current_job.update({
        "status": status,
        "result": result,
        "error": error,
        "attempts": current_job.get("attempts", 0) + 1
    })
    
    if message:
        current_job["message"] = message
    
    # 상태 업데이트 로깅
    print(f"Job {job_id} status updated: {status}, message: {message}, attempts: {current_job['attempts']}")
    
    return current_job

@router.get("/{job_id}/status", 
    summary="Get job status",
    description="Get the current status of a job by its ID. Returns the job status which can be 'PROCESSING', 'COMPLETED', or 'FAILED'.",
    response_description="Returns the job ID and its current status")
async def get_job_status(
    job_id: str = Path(..., description="The ID of the job to check status")
):
    """Get the status of a job"""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_store[job_id]
    print(f"Job {job_id} status check: {job['status']}, attempts: {job.get('attempts', 0)}")
    
    return {
        "job_id": job_id,
        "status": job["status"],
        "message": job.get("message", ""),
        "attempts": job.get("attempts", 0)
    }

@router.get("/{job_id}/result",
    summary="Get job result",
    description="Get the result of a completed job by its ID. If the job is still processing, returns a message indicating the job is not yet complete.",
    response_description="Returns the job result if completed, or a message indicating the job is still processing")
async def get_job_result(
    job_id: str = Path(..., description="The ID of the job to get results")
):
    """Get the result of a completed job"""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_store[job_id]
    
    if job["status"] == "PROCESSING":
        return {
            "status": "PROCESSING",
            "message": "The job is still being processed. Please check back later.",
            "attempts": job.get("attempts", 0)
        }
    
    if job["status"] == "FAILED":
        raise HTTPException(status_code=500, detail=job["error"])
    
    if job["error"]:
        raise HTTPException(status_code=500, detail=job["error"])
    
    # If result is bytes (PDF), return as PDF response
    if isinstance(job["result"], bytes):
        return Response(
            content=job["result"],
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=as_is_analysis_report.pdf"
            }
        )
    
    # Otherwise return as JSON
    return job["result"] 