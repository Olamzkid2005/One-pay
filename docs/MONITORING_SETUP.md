# OnePay Monitoring Setup Guide

## Quick Setup (Recommended)

The easiest way to set up monitoring is to install Docker Desktop:

```bash
# Install Docker Desktop for Mac
brew install --cask docker

# Start Docker Desktop from Applications

# Run monitoring stack
cd /Users/mac/Documents/One-pay
docker compose -f docker-compose.monitoring.yml up -d
```

Access:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/onepay2024)

---

## Manual Setup (Without Docker)

If you prefer not to use Docker, follow these steps:

### Step 1: Install Prometheus

```bash
# Download Prometheus
cd ~/Downloads
curl -LO https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.darwin-amd64.tar.gz
tar xvfz prometheus-2.48.0.darwin-amd64.tar.gz
cd prometheus-2.48.0.darwin-amd64

# Copy configuration
cp /Users/mac/Documents/One-pay/monitoring/prometheus.yml prometheus.yml

# Start Prometheus
./prometheus --config.file=prometheus.yml --storage.tsdb.path=./data
```

### Step 2: Install Grafana

```bash
# Download Grafana
cd ~/Downloads
curl -LO https://dl.grafana.com/oss/release/grafana-10.2.4.darwin-amd64.tar.gz
tar xvfz grafana-10.2.4.darwin-amd64.tar.gz
cd grafana-10.2.4.darwin-amd64

# Start Grafana
./bin/grafana server
```

### Step 3: Configure Grafana

1. Open http://localhost:3000
2. Login with `admin` / `admin` (change password when prompted)
3. Go to **Configuration → Data Sources → Add data source**
4. Select **Prometheus**
5. Set URL to: `http://localhost:9090`
6. Click **Save & Test**

### Step 4: Import Dashboards

1. Go to **Dashboards → Import**
2. Click **Upload JSON file**
3. Import these files from `/Users/mac/Documents/One-pay/grafana/dashboards/`:
   - `business-metrics.json`
   - `system-health.json`
   - `security-events.json`

---

## Verify Setup

### Check OnePay Metrics Endpoint

```bash
# Start OnePay application
cd /Users/mac/Documents/One-pay
python app.py

# In another terminal, check metrics
curl http://localhost:5000/metrics
```

### Check Prometheus Targets

1. Open http://localhost:9090/targets
2. Verify "onepay" job shows as **UP**

### Check Grafana Dashboards

1. Open http://localhost:3000
2. Navigate to **Dashboards → OnePay**
3. View the three dashboards

---

## Generate Test Data (Optional)

To see data in dashboards, create test transactions:

```bash
curl -X POST http://localhost:5000/api/v1/create \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000,
    "currency": "NGN",
    "customer_email": "test@example.com"
  }'
```

---

## Troubleshooting

### Prometheus not scraping OnePay

- Verify OnePay is running: `curl http://localhost:5000/health`
- Check Prometheus configuration: `http://localhost:9090/config`
- Check Prometheus targets: `http://localhost:9090/targets`

### Grafana can't connect to Prometheus

- Verify Prometheus is running: `curl http://localhost:9090`
- Check Grafana data source configuration
- Ensure both are on the same network (localhost)

### No data in dashboards

- Generate test transactions
- Wait 15-30 seconds for metrics to be scraped
- Check Prometheus query: `http://localhost:9090/graph?g0.expr=transactions_total`

---

## Stopping Services

### Docker

```bash
docker compose -f docker-compose.monitoring.yml down
```

### Manual

```bash
# Find and kill processes
pkill prometheus
pkill grafana
```
