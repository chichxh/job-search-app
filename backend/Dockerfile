FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

ARG INSTALL_ML=false

# 1) Ставим базовые зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 2) Опционально ставим ML-зависимости отдельным слоем
COPY requirements-ml.txt /app/requirements-ml.txt
RUN if [ "$INSTALL_ML" = "true" ]; then \
      pip install --no-cache-dir -r /app/requirements-ml.txt; \
    fi

# 3) Копируем код (на деле в compose он будет еще и volume-монтироваться)
COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
