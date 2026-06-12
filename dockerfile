FROM python:3.11-slim
WORKDIR /app
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=src:.
CMD exec gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 1 --bind 0.0.0.0:$PORT
