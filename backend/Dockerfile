FROM python:3.12-slim

WORKDIR /app

# System deps for akshare/numpy
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "main.py"]
