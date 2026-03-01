FROM python:3.12-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create necessary dirs
RUN mkdir -p data downloads ffmpeg

# Railway provides PORT env var
ENV WEB_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
