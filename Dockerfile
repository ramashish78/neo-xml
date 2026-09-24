FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /app/uploads
ENV UPLOAD_ROOT=/app/uploads
EXPOSE 8017
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8017"]
