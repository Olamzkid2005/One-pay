#!/bin/bash
# OnePay Monitoring Stack Installer for macOS (Direct Binary Download)

set -e

echo "=== OnePay Monitoring Stack Installation ==="
echo ""

# Create directories
INSTALL_DIR="$HOME/onepay-monitoring"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "Installing Prometheus..."
# Download Prometheus
PROMETHEUS_VERSION="2.48.0"
curl -LO "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.darwin-amd64.tar.gz"
tar xvfz "prometheus-${PROMETHEUS_VERSION}.darwin-amd64.tar.gz"
cd "prometheus-${PROMETHEUS_VERSION}.darwin-amd64"

# Copy configuration from project
cp /Users/mac/Documents/One-pay/monitoring/prometheus.yml prometheus.yml

# Start Prometheus in background
echo "Starting Prometheus..."
./prometheus --config.file=prometheus.yml --storage.tsdb.path=./data > prometheus.log 2>&1 &
PROMETHEUS_PID=$!
echo "Prometheus PID: $PROMETHEUS_PID"
echo $PROMETHEUS_PID > prometheus.pid

cd "$INSTALL_DIR"

echo "Installing Grafana..."
# Download Grafana
GRAFANA_VERSION="10.2.4"
curl -LO "https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.darwin-amd64.tar.gz"
tar xvfz "grafana-${GRAFANA_VERSION}.darwin-amd64.tar.gz"
cd "grafana-${GRAFANA_VERSION}"

# Start Grafana in background
echo "Starting Grafana..."
./bin/grafana server > grafana.log 2>&1 &
GRAFANA_PID=$!
echo "Grafana PID: $GRAFANA_PID"
echo $GRAFANA_PID > grafana.pid

cd "$INSTALL_DIR"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Access points:"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000"
echo "  Grafana credentials: admin / admin"
echo ""
echo "To stop services:"
echo "  kill $PROMETHEUS_PID"
echo "  kill $GRAFANA_PID"
echo ""
echo "To restart services:"
echo "  cd $INSTALL_DIR/prometheus-${PROMETHEUS_VERSION}.darwin-amd64"
echo "  ./prometheus --config.file=prometheus.yml --storage.tsdb.path=./data > prometheus.log 2>&1 &"
echo "  cd $INSTALL_DIR/grafana-${GRAFANA_VERSION}"
echo "  ./bin/grafana server > grafana.log 2>&1 &"
echo ""
echo "Note: You'll need to configure Grafana data source manually:"
echo "  1. Open http://localhost:3000"
echo "  2. Login with admin/admin"
echo "  3. Go to Configuration → Data Sources → Add Prometheus"
echo "  4. URL: http://localhost:9090"
echo "  5. Import dashboards from /Users/mac/Documents/One-pay/grafana/dashboards/"
