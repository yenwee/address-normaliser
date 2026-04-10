FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/
COPY main.py .

CMD ["python", "-u", "main.py"]
