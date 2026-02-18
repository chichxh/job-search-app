FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Ставим зависимости
# Если переименуешь в requirements.txt — поменяй строку COPY.
COPY requirments.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 2) Копируем код (на деле в compose он будет еще и volume-монтироваться)
COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
