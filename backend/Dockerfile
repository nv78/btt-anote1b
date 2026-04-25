FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY . /app/backend

ENV PORT=5001
EXPOSE 5001

CMD ["python", "backend/app.py"]
