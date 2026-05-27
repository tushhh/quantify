web: PYTHONPATH=src:. gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 1 --max-requests 50 --max-requests-jitter 10 --bind 0.0.0.0:${PORT:-8000}
