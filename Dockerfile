FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ ./engine/
COPY prompts/ ./prompts/
COPY main.py llm.py ./
COPY static/ ./static/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8420
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/sante')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8420"]
