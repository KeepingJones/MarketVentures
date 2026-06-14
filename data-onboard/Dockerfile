FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -c "from db.database import init_db; init_db()" 2>/dev/null || true

EXPOSE 8003

CMD ["uvicorn", "api.routes:app", "--host", "0.0.0.0", "--port", "8003"]
