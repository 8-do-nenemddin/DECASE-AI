# app/services/file_processing_service.py
import json
import csv
import fitz # PyMuPDF
import re
import os
import weasyprint
import whisper
import torch
import PyPDF2
import asyncio
import tempfile
from pathlib import Path
from fastapi import UploadFile, File, Form, HTTPException, BackgroundTasks


from docx import Document
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
    # HTML을 그대로 파일로 저장 (원본 백업 또는 참고용)
    try:
        html_path = os.path.splitext(file_path)[0] + ".html"
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ 원본 HTML이 별도로 저장되었습니다: {html_path}")
    except Exception as e:
        print(f"🚨 원본 HTML 저장 실패: {e}")
        
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


def transcribe_audio_with_whisper(audio_file_path: str) -> str:
    """Whisper를 사용하여 오디오 파일에서 텍스트를 추출합니다."""
    # (제공해주신 함수와 동일, 에러 핸들링 강화)
    try:
        print(f"\nWhisper 모델 로딩 중...")
        # CPU 환경에서도 빠르게 동작하도록 작은 모델을 기본으로 설정
        model = whisper.load_model("base")
        print("Whisper 모델 로딩 완료.")
        
        print(f"음성 파일 '{audio_file_path}'에서 텍스트 추출 중...")
        result = model.transcribe(audio_file_path, language="ko", fp16=False)
        transcribed_text = result["text"]
        print("🎧 STT 변환 완료 (Whisper)")
        return transcribed_text
    except Exception as e:
        print(f"음성 파일 변환 중 오류 발생: {e}")
        if "ffmpeg" in str(e).lower():
            print("오류 메시지에 'ffmpeg'가 포함되어 있습니다. ffmpeg가 시스템에 올바르게 설치되고 PATH에 등록되어 있는지 확인해주세요.")
        raise e # 오류를 상위로 전파

def _extract_text_from_pdf(content: bytes) -> str:
    """PDF 파일의 바이트(bytes) 내용에서 텍스트를 추출합니다."""
    text = ""
    with io.BytesIO(content) as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def _extract_text_from_docx(content: bytes) -> str:
    """DOCX 파일의 바이트(bytes) 내용에서 텍스트를 추출합니다."""
    text = ""
    with io.BytesIO(content) as f:
        doc = Document(f)
        for para in doc.paragraphs:
            text += para.text + "\n"
    return text

async def extract_text_from_file(file_content: bytes, raw_filename: str) -> str:
    """
    파일 이름과 내용을 받아, 파일 종류에 따라 텍스트를 추출하는 메인 함수.
    CPU를 많이 사용하는 작업은 별도 스레드에서 실행합니다.
    """
    file_ext = Path(raw_filename).suffix.lower()
    
    if file_ext == ".txt":
        return file_content.decode('utf-8', errors='ignore')
    
    elif file_ext == ".pdf":
        return await asyncio.to_thread(_extract_text_from_pdf, file_content)
    
    elif file_ext == ".docx":
        return await asyncio.to_thread(_extract_text_from_docx, file_content)
        
    elif file_ext in [".wav", ".mp3", ".m4a"]:
        # 오디오 파일은 디스크에 임시 저장 후 처리해야 합니다.
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name
        
        try:
            # Whisper는 CPU를 많이 사용하므로 별도 스레드에서 실행합니다.
            transcribed_text = await asyncio.to_thread(
                transcribe_audio_with_whisper, tmp_file_path
            )
            return transcribed_text
        finally:
            # 임시 파일 삭제
            os.remove(tmp_file_path)
            
    else:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {file_ext}")
