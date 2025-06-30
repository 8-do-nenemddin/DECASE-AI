# app/services/file_processing_service.py
import json
import csv
import fitz # PyMuPDF
import re
import os
import weasyprint
from typing import List, Tuple, Optional, Dict, Any
from io import BytesIO

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

def sanitize_filename(name: str) -> str:
    """파일 이름으로 사용하기 어려운 문자를 제거하거나 대체합니다."""
    if not isinstance(name, str):
        name = str(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100] # 파일명 길이 제한

def prepare_data_for_faiss(input_json_path: str) -> List[Dict[str, Any]]:
    """
    원본 JSON 파일에서 데이터를 로드하고, 각 항목을 
    FAISS 인덱싱에 필요한 'text' (임베딩 대상)와 'metadata' (저장할 정보)로 구성된 딕셔너리 리스트로 변환합니다.
    """
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list): # 단일 객체일 경우 리스트로 감싸기
                data = [data] if isinstance(data, dict) else []
    except FileNotFoundError:
        print(f"오류: 파일을 찾을 수 없습니다 - {input_json_path}")
        return []
    except json.JSONDecodeError:
        print(f"오류: JSON 디코딩 실패 - {input_json_path}")
        return []
    except Exception as e:
        print(f"파일 로드 중 오류 발생 ({input_json_path}): {e}")
        return []

    faiss_data_items = []
    for item in data:
        # 임베딩에 사용될 텍스트 구성 (사용자 스크립트의 chunk_text 구성 방식 참조)
        embedding_text = f"""[ID] {item.get('id', '')}
[유형] {item.get('type', '')}
[설명] {item.get('description_name', '')}
[요구사항 상세] {item.get('description_content', '')}
[대상 업무] {item.get('target_task', '')}
[대분류] {item.get('category_large', '')}
[중분류] {item.get('category_medium', '')}
[소분류] {item.get('category_small', '')}
[중요도] {item.get('importance', '')}
[난이도] {item.get('difficulty', '')}
""".strip()  # 앞뒤 공백 제거

        # 메타데이터로 저장할 원본 아이템 또는 선택된 필드들
        metadata = {
            "description_name": item.get('description_name', ''),
            "type": item.get('type', ''),
            "raw_text": item.get('raw_text', ''),
            "rfp_page": item.get('rfp_page',''),
            "mod_reason": item.get('mod_reason', ''),
            "status": item.get('status', ''),
        }
        faiss_data_items.append({
            "embedding_text_source": embedding_text,
            "metadata": metadata
        })
    return faiss_data_items

def save_report(html_content: str, file_path: str):
    """
    주어진 HTML 콘텐츠를 파싱하여 깨끗한 HTML 파일과 PDF 파일로 저장합니다.
    pyhtml2pdf 라이브러리를 사용하여 PDF를 생성합니다.
    
    Args:
        html_content (str): 저장할 HTML 소스 코드 문자열 (AI가 생성한 마크다운 포함 가능).
        file_path (str): 저장할 HTML 파일의 전체 경로 (예: "reports/as_is_report.html").
                         PDF는 동일한 이름으로 확장자만 .pdf로 변경되어 저장됩니다.
    """
    # --- 1. AI 응답 파싱 (Markdown 코드 블록 제거) ---
    try:
        # 정규식을 사용해 ```html 과 ``` 사이의 내용만 정확히 추출
        match = re.search(r"```html(.*)```", html_content, re.DOTALL)
        if match:
            # 매칭된 그룹의 첫 번째(실제 코드 부분)를 가져오고, 앞뒤 공백을 제거
            clean_html = match.group(1).strip()
            print("✅ 마크다운 파싱 완료.")
        else:
            # 마크다운 블록이 없는 경우, 그냥 원본 사용
            clean_html = html_content.strip()
            print("ℹ️ 마크다운 블록이 없어 원본 HTML을 사용합니다.")
    except Exception as e:
        print(f"🚨 파싱 중 오류 발생: {e}")
        # 파싱에 실패하면 원본을 그대로 사용
        clean_html = html_content

    # --- 2. HTML 파일 저장 ---
    try:
        # 파일이 저장될 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # HTML 파일을 쓰기 모드('w')와 UTF-8 인코딩으로 저장
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(clean_html)
        print(f"✅ HTML 보고서가 성공적으로 저장되었습니다: {file_path}")
    except Exception as e:
        print(f"🚨 HTML 파일 저장 실패: {e}")
        return # HTML 저장 실패 시 함수 종료

    # --- 3. PDF 파일 저장 ---
    # 저장될 PDF 파일 경로 생성 (예: "reports/as_is_report.html" -> "reports/as_is_report.pdf")
    pdf_path = os.path.splitext(file_path)[0] + ".pdf"
    
    try:
        weasyprint.HTML(file_path).write_pdf(pdf_path)
        print(f"✅ PDF 보고서가 성공적으로 저장되었습니다: {pdf_path}")
    except Exception as e:
        print(f"🚨 PDF 변환 실패: {e}")

def create_chunks(data: List, chunk_size: int) -> List[List]:
    """리스트를 주어진 크기의 청크로 나눕니다."""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

