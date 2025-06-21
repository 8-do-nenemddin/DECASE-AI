# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o") # 기본값 gpt-4o

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL","gemini-2.5-pro")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")


OUTPUT_UPLOADS_DIR = os.getenv("FILE_STORAGE_PATH_UPLOADS", "app/output/docs")
OUTPUT_SRS_DIR = os.getenv("FILE_STORAGE_PATH_SRS", "app/output/srs_result")
OUTPUT_ASIS_DIR = os.getenv("FILE_STORAGE_PATH_ASIS", "app/output/asis_result")
OUTPUT_MOCKUP_DIR = os.getenv("FILE_STORAGE_PATH_MOCKUP", "app/output/mockup_result")

SENTENCE_TRANSFORMER_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")

FAISS_INDEX_DIR = "app/indexes/faiss_indexes" # FAISS 인덱스 저장 디렉토리
METADATA_STORAGE_DIR = "app/indexes/metadata" # 메타데이터 JSON 저장 디렉토리

CHUNK_SIZE = 4000
CHUNK_OVERLAP = 200

if not OPENAI_API_KEY:
    print("경고: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. Gemini 모델 사용 시 오류가 발생할 수 있습니다.")
if not GOOGLE_API_KEY:
    print("경고: GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. Gemini 모델 사용 시 오류가 발생할 수 있습니다.")