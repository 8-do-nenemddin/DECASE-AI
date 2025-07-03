FROM amdp-registry.skala-ai.com/skala25a/decase-ai-base:1.0.0

# 애플리케이션 코드 복사
COPY . /app

# Playwright 브라우저 및 의존성 설치
RUN playwright install

EXPOSE 8000 8081 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081", "--workers", "4"]
