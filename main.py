# app/main.py
from fastapi import FastAPI
from app.api import mockup as mockup_router
from app.api import update as update_router
from app.api import srs_job as srs_job_router
from app.api import srs as srs_router
from app.api import asis as asis_router
from app.api import screen_spec as screen_spec_router
from app.api import meeting_summary as meeting_summary_router

app = FastAPI(
    title="RFP Analysis Service",
    description="RFP 문서를 분석하여 요구사항을 분류, 평가하고 SRS 문서를 생성하는 API",
    version="0.1.0",
    root_path='/ai/api/v1'
)

# 라우터 등록 - root_path 제거하고 prefix만 사용
app.include_router(srs_router.router, prefix="/requirements", tags=["SRS"])
app.include_router(asis_router.router, prefix="/requirements", tags=["As-Is"]) 
app.include_router(mockup_router.router, prefix="/mockup", tags=["Mockup"]) # 추가
app.include_router(update_router.router, prefix="/requirements", tags=["Update Request"]) # 새 라우터 추가
app.include_router(srs_job_router.router, prefix="/jobs", tags=["SRS"])  # SRS 분석 작업 상태 확인 라우터
app.include_router(screen_spec_router.router, prefix="/mockup/specs", tags=["Screen Specs"])  # 화면 설계서 생성 라우터
# app.include_router(meeting_summary_router.router, prefix="/meetings", tags=["Meeting Summary"])  # 회의록 요약 라우터

@app.get("/")
async def root():
    return {"message": "RFP Analysis Service에 오신 것을 환영합니다!"}

# 애플리케이션 상태 확인용 엔드포인트 (선택 사항)
@app.get("/health")
async def health_check():
    return {"status": "ok"}
