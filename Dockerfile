FROM python:3.11-slim

WORKDIR /app

# 安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 創建日誌目錄
RUN mkdir -p logs

# 預設命令（可被 docker-compose 覆蓋）
CMD ["python", "main.py", "--config", "config/project_a.yaml", "--mode", "watch"]
