# Build the browser editor into a local, version-pinned, self-contained
# JavaScript bundle. The deployed iframe never depends on a CDN.
FROM node:22-alpine AS solar3d-frontend
WORKDIR /solar3d
COPY dashboard/components/solar3d_drag/package.json ./
RUN npm install --no-audit --no-fund
COPY dashboard/components/solar3d_drag/editor.js ./
COPY dashboard/components/solar3d_drag/selection_logic.mjs ./
COPY dashboard/components/solar3d_drag/compass_directions.mjs ./
RUN npm run build && test -s editor.bundle.js

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=solar3d-frontend /solar3d/editor.bundle.js /app/dashboard/components/solar3d_drag/editor.bundle.js
EXPOSE 8000 8501
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
