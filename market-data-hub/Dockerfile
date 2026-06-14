FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["sh", "-c", "python -c 'from db.database import init_db, seed_vendors, seed_datasets; init_db(); seed_vendors(); seed_datasets()' && uvicorn api.routes:app --host 0.0.0.0 --port 8001"]
