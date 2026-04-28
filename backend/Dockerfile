FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 创建存储目录（Railway volume会挂载到这里）
RUN mkdir -p /app/storage

EXPOSE 8000

CMD ["python", "main.py"]
