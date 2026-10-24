FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data HF_HOME=/data/hf
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
