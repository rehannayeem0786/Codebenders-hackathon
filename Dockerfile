FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
# run.py reads HOST and PORT from the environment (backend/app/config.py).
# 127.0.0.1 is unreachable from outside a container, so bind all interfaces.
ENV HOST=0.0.0.0
ENV PORT=8000

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "run.py"]
