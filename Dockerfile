FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    TZ=Asia/Makassar

WORKDIR /app
RUN useradd --create-home --uid 10001 appuser && \
    mkdir -p /app/data/runs && chown -R appuser:appuser /app/data
COPY requirements.txt .
RUN python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser .streamlit/config.toml ./.streamlit/config.toml
COPY --chown=appuser:appuser helper/ ./helper/
COPY --chown=appuser:appuser scrap/ ./scrap/
COPY --chown=appuser:appuser styles/ ./styles/
COPY --chown=appuser:appuser asset/ ./asset/
COPY --chown=appuser:appuser scripts/smoke_test.py ./scripts/smoke_test.py
USER appuser
EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5).read()" || exit 1
CMD ["streamlit", "run", "main.py"]
