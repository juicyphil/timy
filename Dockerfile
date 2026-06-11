FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ server/
COPY static/ static/
EXPOSE 8765
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8765"]
