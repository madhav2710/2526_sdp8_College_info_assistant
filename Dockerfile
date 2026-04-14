FROM node:20-alpine AS frontend-builder
WORKDIR /build

# User frontend
COPY frontend/User/package.json frontend/User/package-lock.json /build/user/
RUN cd /build/user && npm ci
COPY frontend/User/ /build/user/
RUN cd /build/user && VITE_API_BASE_URL=/api VITE_APP_BASE=/ npm run build

# Admin frontend
COPY frontend/Admin/package.json frontend/Admin/package-lock.json /build/admin/
RUN cd /build/admin && npm ci
COPY frontend/Admin/ /build/admin/
RUN cd /build/admin && VITE_API_BASE_URL=/api VITE_APP_BASE=/admin/ npm run build

# Super admin frontend (path includes a space)
COPY ["frontend/Super admin/package.json", "frontend/Super admin/package-lock.json", "/build/super-admin/"]
RUN cd /build/super-admin && npm ci
COPY ["frontend/Super admin/", "/build/super-admin/"]
RUN cd /build/super-admin && VITE_API_BASE_URL=/api VITE_APP_BASE=/super/ npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends caddy supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/

COPY --from=frontend-builder /build/user/dist/ /var/www/user/
COPY --from=frontend-builder /build/admin/dist/ /var/www/admin/
COPY --from=frontend-builder /build/super-admin/dist/ /var/www/super/

COPY Caddyfile /etc/caddy/Caddyfile
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
