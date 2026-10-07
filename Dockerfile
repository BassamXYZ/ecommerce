# ---- Image for the Django ecommerce project ----
FROM python:3.12-slim

# No .pyc files, and logs go straight to the console
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached
# until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project code
COPY . .

# Run as a non-root user (safer)
RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app \
    && chmod +x /app/docker-entrypoint.sh
USER appuser

EXPOSE 8000

# Entrypoint: migrate + collectstatic, then run the CMD below
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "ecommerce.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
