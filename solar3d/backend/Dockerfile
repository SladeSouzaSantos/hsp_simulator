FROM python:3.12-slim
WORKDIR /app
COPY solar3d/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY solar3d /app/solar3d
EXPOSE 8001
CMD ["uvicorn", "solar3d.backend.api:app", "--host", "0.0.0.0", "--port", "8001"]
