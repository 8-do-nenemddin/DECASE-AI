# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o") # 기본값 gpt-4o

INPUT_DIR = "app/docs"
OUTPUT_CSV_DIR = "app/output/SRS_csv"
OUTPUT_JSON_DIR = "app/output/SRS_json"
OUTPUT_ASIS_DIR = "app/output/ASIS_md"
OUTPUT_MOCKUP_DIR = "app/output/mockup_html"

SENTENCE_TRANSFORMER_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
FAISS_INDEX_DIR = "app/indexes/faiss_indexes" # FAISS 인덱스 저장 디렉토리
METADATA_STORAGE_DIR = "app/indexes/metadata" # 메타데이터 JSON 저장 디렉토리

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경 변수를 설정해주세요.")

os.makedirs(FAISS_INDEX_DIR, exist_ok=True)
os.makedirs(METADATA_STORAGE_DIR, exist_ok=True)