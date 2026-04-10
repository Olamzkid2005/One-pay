#!/bin/bash
# OnePay Monitoring Stack Installer for macOS

set -e

echo "=== OnePay Monitoring Stack Installation ==="
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "Homebrew found."
fi

# Install Prometheus
echo ""
echo "Installing Prometheus..."
brew install prometheus

# Create Prometheus configuration directory
sudo mkdir -p /usr/local/etc/prometheus
sudo chown -R $(whoami) /usr/local/etc/prometheus

# Copy Prometheus configuration
cp monitoring/prometheus.yml /usr/local/etc/prometheus/prometheus.yml

# Install Grafana
echo ""
echo "Installing Grafana..."
brew install grafana

# Start services
echo ""
echo "Starting services..."

# Start Prometheus
brew services start prometheus

# Start Grafana
brew services start grafana

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Access points:"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000"
echo "  Grafana credentials: admin / admin"
echo ""
echo "Note: You'll need to configure Grafana data source manually:"
echo "  1. Open http://localhost:3000"
echo "  2. Login with admin/admin"
echo "  3. Go to Configuration → Data Sources → Add Prometheus"
echo "  4. URL: http://localhost:9090"
echo "  5. Import dashboards from grafana/dashboards/"
