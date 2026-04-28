FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 确保所有目录都是Python包
RUN touch /app/__init__.py /app/data/__init__.py /app/api/__init__.py /app/llm/__init__.py /app/strategies/__init__.py /app/models/__init__.py

EXPOSE 8000

CMD ["python", "main.py"]
