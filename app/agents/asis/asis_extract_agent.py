import json
from google import genai
from google.genai import types

from typing import Any, Dict

from app.core.config import GEMINI_MODEL

def extract_as_is_facts(client: genai.Client, uploaded_file: Any) -> Dict[str, Any]:
    """
    [1단계-A] As-Is 문서에서 개발자에게 필요한 구조화된 '기술 사실 데이터'를 상세하게 추출합니다.
    """
    print("\n🚀 As-Is 기술 사실 데이터 추출을 시작합니다...")

    prompt = """
    당신은 시스템의 기술적 현황을 신규 프로젝트팀에 인계하기 위해 문서를 분석하는 수석 시스템 아키텍트입니다.
    첨부된 'As-Is 시스템 현황' 문서의 모든 내용을 분석하여, 아래 4개 항목에 대한 정보를 누락 없이 상세하게 기술한 JSON 객체를 생성하십시오.
    **특히, 잠재적인 기술 부채, 운영상의 문제점, 정확한 버전 정보 등 개발자가 반드시 알아야 할 기술적 뉘앙스를 최대한 상세하게 포함해야 합니다.**
    절대로 내용을 요약하거나 생략하지 마십시오.

    [추출할 JSON 구조]
    {
      "system_overview": {
        "summary": "시스템의 공식 명칭, 최초 구축 연도, 주요 비즈니스 도메인 등 시스템을 식별할 수 있는 개요 정보를 상세히 기술",
        "main_users": "시스템을 사용하는 주요 내부/외부 사용자 그룹과 각 그룹의 핵심 사용 시나리오를 기술",
        "key_features": [
          "시스템의 기술적 또는 기능적 특징을 나타내는 문장들을 그대로 나열 (예: 'Java 기반으로 구축', '클라우드 연동 제약')"
        ]
      },
      "major_functions": [
        {
          "function_name": "주요 기능명",
          "description": "해당 기능의 기술적 구현 방식, 핵심 로직, 처리 프로세스, 관련 데이터, 현재 운영 방식 및 알려진 이슈나 한계점을 상세하게 기술"
        }
      ],
      "nfr_status": {
        "performance": "문서에 언급된 모든 성능 관련 수치(TPS, 응답 시간), 현재 성능 수준, 성능 저하 원인, 배치 작업 소요 시간 등 상세 정보",
        "security": "인증/인가 방식(SSO, OAuth, ID/PW), 2단계 인증(MFA) 적용 여부, 접근 제어 정책, 데이터 암호화 수준, 사용 중인 보안 솔루션 및 버전 정보",
        "data_handling": "총 데이터 규모, 일일 트랜잭션 양, 데이터 보관 주기, 백업/복구 정책 및 현재 수행 방식(수동/자동), 데이터 관련 리스크",
        "availability_scalability": "시스템 가용성 목표(%), 이중화(HA) 구성 현황, 스케일-업/아웃 구조, 현재 확장성의 한계점"
      },
      "architecture": {
        "server_env": "서버 환경(On-premise/Cloud), IDC 위치, 서버 스펙(CPU, Memory, Disk) 등 구체적인 물리/가상 환경 정보",
        "os_middleware": "서버 OS 및 정확한 버전, WAS, Web Server, 컨테이너 기술(Docker/K8s) 등 모든 미들웨어의 종류와 버전 정보",
        "database": "사용 중인 DBMS 종류 및 정확한 버전, DB 이중화 구성, 주요 스키마 구조나 테이블 특징",
        "frameworks_languages": "개발에 사용된 주력 언어 및 프레임워크와 정확한 버전 (예: Java 1.8, Spring 3.x), 주요 라이브러리 및 의존성 정보",
        "integration": "연동되는 모든 내부/외부 시스템 목록과 각 연동의 구체적인 방식(REST API, EAI, DB Link, SFTP 등), 프로토콜, 데이터 포맷(JSON/XML)에 대한 상세 정보"
      }
    }

    이제 분석을 시작하여, 다른 설명 없이 최종 JSON 객체만 반환하십시오.
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Part.from_bytes(
              data=uploaded_file,
              mime_type='application/pdf',
            ), 
            prompt],
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.0
            }
        )
        as_is_facts = json.loads(response.text)
        print("✅ As-Is 기술 사실 데이터 추출 완료.")
        return as_is_facts
    except Exception as e:
        print(f"🚨 As-Is 기술 사실 데이터 추출 실패: {e}")
        # 오류 발생 시 응답 텍스트를 출력하여 원인 파악에 도움
        try:
            print("--- 모델 응답 ---")
            print(response.text)
            print("--- ---")
        except:
            pass
        return {}
