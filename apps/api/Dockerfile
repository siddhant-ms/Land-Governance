FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /repo/apps/api
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api /repo/apps/api
COPY data /repo/data
RUN useradd -m app && mkdir -p /repo/data/documents/_store && chown -R app /repo/data
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
