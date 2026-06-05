FROM python:3.11-slim AS app

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY . /app
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e ".[test]"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
