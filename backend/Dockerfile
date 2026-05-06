FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=5001
EXPOSE 5001

CMD ["python", "app.py"]
