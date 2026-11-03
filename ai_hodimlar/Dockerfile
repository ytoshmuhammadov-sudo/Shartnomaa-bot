FROM python:3.12-slim
WORKDIR /app
COPY ai_hodimlar/requirements.txt ai_hodimlar/requirements.txt
RUN pip install --no-cache-dir -r ai_hodimlar/requirements.txt
COPY ai_hodimlar ai_hodimlar
ENV AI_HODIMLAR_DB=/data/ai_hodimlar.db
RUN mkdir -p /data
# Bitta worker: Telegram long-polling va bilim yangilovchi server ichida ishlaydi
CMD ["sh", "-c", "uvicorn ai_hodimlar.server:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
