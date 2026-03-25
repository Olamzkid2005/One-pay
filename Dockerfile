FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Non-root user for security
RUN adduser --disabled-password --gecos "" onepay && chown -R onepay /app
USER onepay

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["./entrypoint.sh"]
