# app/services/file_processing_service.py
import json
import csv
import fitz # PyMuPDF
import re
import os
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

def create_chunks_from_documents(
    documents: List[Document],
    chunk_size: int = 2000,
    chunk_overlap: int = 200
) -> List[Document]:
    if not documents:
        return []

    print(f"Document 청킹 중 (청크 크기: {chunk_size}, 중복: {chunk_overlap})...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""],
        keep_separator=False
    )
    # split_documents는 Document 리스트를 받아 각 Document를 청킹하고,
    # 원본 Document의 metadata를 청크 Document로 복사해줌.
    chunked_documents = text_splitter.split_documents(documents)
    print(f"총 {len(chunked_documents)}개의 청크(Document) 생성 완료.")
    return chunked_documents

    # as_is_module.ipynb의 extract_text_with_page_info 함수 내용
    # 반환 타입을 (페이지 텍스트 리스트, 총 페이지 수)로 변경
def extract_text_with_page_info_from_pdf(pdf_path: str | BytesIO) -> Tuple[Optional[List[str]], int]:
    try:
        # BytesIO 객체인 경우와 파일 경로인 경우를 구분하여 처리
        if isinstance(pdf_path, BytesIO):
            document = fitz.open(stream=pdf_path.getvalue(), filetype="pdf")
        else:
            document = fitz.open(pdf_path)
            
        page_texts = []
        for page_num in range(document.page_count):
            page = document.load_page(page_num)
            text = page.get_text("text", sort=True) # 정렬된 텍스트 추출
            page_texts.append(text.strip())
        return page_texts, document.page_count
    except Exception as e:
        print(f"PDF 텍스트 추출 오류: {e}")
        return None, 0

def extract_text_for_pages_from_list(page_texts_list: List[str], start_page_num: int, end_page_num: int) -> str:
    # as_is_module.ipynb의 extract_text_for_pages 함수 내용 (입력을 리스트로 받도록 수정)
    start_idx = max(0, start_page_num - 1)
    end_idx = min(len(page_texts_list), end_page_num)
    if start_idx >= end_idx:
        return ""
    return "\\n".join(page_texts_list[start_idx:end_idx])


def get_toc_raw_text_from_page_list(page_texts_list: List[str], toc_page_numbers: List[int] = [2,3]) -> Optional[str]:
    # as_is_module.ipynb의 get_toc_raw_text_from_full_text 함수 내용 (입력을 리스트로 받도록 수정)
    toc_texts = []
    for page_num in toc_page_numbers:
        page_content = extract_text_for_pages_from_list(page_texts_list, page_num, page_num)
        if page_content:
            toc_texts.append(page_content)
        else:
            print(f"경고: 목차 페이지로 지정된 {page_num} 페이지에서 텍스트를 찾을 수 없습니다.")
    if not toc_texts:
        return None
    raw_toc = "\\n".join(toc_texts)
    raw_toc = re.sub(r'\\s+', ' ', raw_toc).strip()
    raw_toc = re.sub(r'\\.{2,}', '', raw_toc)
    raw_toc = re.sub(r'\\n{2,}', '\\n', raw_toc)
    return raw_toc

def load_requirements_from_json(filepath: str) -> List[Dict[str, Any]]:
    """지정된 경로에서 JSON 파일을 로드하여 요구사항 목록을 반환합니다."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                print(f"Error: JSON 파일 ({filepath})이 리스트 형태가 아닙니다.")
                return []
    except FileNotFoundError:
        print(f"Error: JSON 파일을 찾을 수 없습니다 - {filepath}")
        return []
    except json.JSONDecodeError:
        print(f"Error: JSON 파일 디코딩 중 오류 발생 - {filepath}")
        return []
    except Exception as e:
        print(f"Error loading JSON file {filepath}: {e}")
        return []

def save_results_to_json(results: List[Dict[str, Any]], filepath: str):
    """결과 목록을 지정된 경로에 JSON 파일로 저장합니다."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n결과가 성공적으로 {filepath} 파일에 저장되었습니다.")
    except Exception as e:
        print(f"Error saving results to JSON file {filepath}: {e}")

def convert_json_to_csv(json_file_path: str, csv_file_path: str):
    """
    주어진 JSON 파일에서 데이터를 읽어 지정된 CSV 양식으로 변환하여 저장합니다.
    """
    csv_headers = [
        "요구사항 ID", "유형(기능/비기능)", "요구사항명", "요구사항 상세설명", 
        "대상 업무", "요건처리 상세", "대분류", "중분류", "소분류",
        "중요도", "난이도", "RFP", "출처문장"
    ]
    try:
        with open(json_file_path, 'r', encoding='utf-8') as json_file:
            requirements_data = json.load(json_file)
    except FileNotFoundError:
        print(f"오류: JSON 파일 '{json_file_path}'를 찾을 수 없습니다.")
        raise
    except json.JSONDecodeError as e:
        print(f"오류: JSON 파일 '{json_file_path}' 파싱 중 오류 발생: {e}")
        raise
    except Exception as e:
        print(f"오류: JSON 파일 '{json_file_path}'을 여는 중 오류 발생: {e}")
        raise

    if not isinstance(requirements_data, list):
        if isinstance(requirements_data, dict):
            requirements_data = [requirements_data]
        else:
            msg = f"오류: JSON 데이터의 최상위 구조가 리스트 또는 단일 객체가 아닙니다 (타입: {type(requirements_data)})."
            print(msg)
            raise ValueError(msg)
            
    try:
        with open(csv_file_path, 'w', newline='', encoding='utf-8-sig') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(csv_headers)
            for req in requirements_data:
                if not isinstance(req, dict):
                    print(f"경고: 요구사항 데이터 리스트 내에 딕셔너리가 아닌 항목 발견. 건너<0xEB><0x9A><0x84>니다: {req}")
                    continue
                
                row_to_write = [
                    req.get("id", ""),
                    req.get("type", ""),
                    req.get("description_name", ""),
                    req.get("description_content", ""),
                    req.get("target_task", ""),
                    req.get("processing_detail", ""),
                    req.get("category_large", ""),
                    req.get("category_medium", ""),
                    req.get("category_small", ""),
                    req.get("importance", ""),
                    req.get("difficulty", ""),
                    req.get("rfp_page", ""),
                    req.get("raw_text", "")
                ]
                writer.writerow(row_to_write)
        print(f"성공: '{json_file_path}' 파일의 내용이 '{csv_file_path}' CSV 파일로 성공적으로 변환되었습니다.")
    except IOError as e:
        print(f"오류: CSV 파일 '{csv_file_path}'을(를) 쓰거나 여는 중 I/O 오류 발생: {e}")
        raise
    except Exception as e:
        print(f"CSV 변환 중 예기치 않은 오류 발생: {e}")
        raise


def load_requirements_data_for_mockup(filepath: str) -> List[Dict[str, Any]]:
    """
    목업 생성을 위한 요구사항 파일을 로드합니다. (기존 RequirementsLoader.load_from_file 기능)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"요구사항 파일 '{filepath}' 로드 성공 (목업용).")
        if isinstance(data, list): # 일반적으로 요구사항 목록은 리스트
            return data
        elif isinstance(data, dict) and "requirements" in data and isinstance(data["requirements"], list): # 혹은 특정 키 아래 리스트
            return data["requirements"]
        else:
            print(f"경고: 파일 '{filepath}'의 내용이 예상된 리스트 또는 특정 키를 가진 딕셔너리 형식이 아닙니다.")
            return [] # 빈 리스트 반환 또는 예외 처리
    except FileNotFoundError:
        print(f"오류: 파일 '{filepath}'를 찾을 수 없습니다.")
        return []
    except json.JSONDecodeError:
        print(f"오류: 파일 '{filepath}'가 유효한 JSON 형식이 아닙니다.")
        return []
    except Exception as e:
        print(f"파일 로드 중 예기치 않은 오류 발생: {e}")
        return []

def save_html_content(html_content: str, filepath: str):
    """HTML 내용을 지정된 경로에 저장합니다."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML 파일 저장: {filepath}")
    except Exception as e:
        print(f"HTML 파일 저장 중 오류 발생 ({filepath}): {e}")
        # import traceback # 필요시 상세 에러 로깅
        # traceback.print_exc()


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

from markdown_pdf import MarkdownPdf, Section

def save_report_to_file(report_content: str, filename: str = "as_is_technical_report.md"):
    """
    생성된 보고서 내용을 파일로 저장합니다.
    """
    user_css = "body { font-family: 'NanumGothic', 'Malgun Gothic', sans-serif; } @page { margin: 1in; }"
    pdf_converter = MarkdownPdf(toc_level=2)
    pdf_converter.add_section(Section(report_content), user_css=user_css)
    try:
        pdf_converter.save(filename)
    except Exception as e:
        print(f"\n🔥 파일 저장 중 오류 발생: {e}")

def create_chunks(data: List, chunk_size: int) -> List[List]:
    """리스트를 주어진 크기의 청크로 나눕니다."""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

