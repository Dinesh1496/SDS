# Prometheus & Grafana Monitoring Setup

## 11. Prometheus & Grafana Monitoring Setup

This section covers the installation and configuration of Prometheus for metrics collection and Grafana for visualization and dashboarding.

---

### 11.1 Prometheus Installation & Configuration

#### 11.1a Install Prometheus on RHEL 10

```bash
# Create prometheus user
sudo useradd \
    --system \
    --shell /sbin/nologin \
    --home-dir /var/lib/prometheus \
    --no-create-home \
    --comment "Prometheus Monitoring System" \
    prometheus

# Create directories
sudo mkdir -p /etc/prometheus
sudo mkdir -p /var/lib/prometheus
sudo mkdir -p /etc/prometheus/rules

# Download and install Prometheus
PROM_VERSION="2.48.0"
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz

tar xzf prometheus-${PROM_VERSION}.linux-amd64.tar.gz
cd prometheus-${PROM_VERSION}.linux-amd64

# Install binaries
sudo cp prometheus promtool /usr/local/bin/
sudo chmod +x /usr/local/bin/prometheus /usr/local/bin/promtool

# Install console files
sudo cp -r consoles console_libraries /etc/prometheus/

# Set ownership
sudo chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus
```

#### 11.1b Configure Prometheus

Create the Prometheus configuration file:

```bash
sudo tee /etc/prometheus/prometheus.yml << 'EOF'
# Prometheus configuration for SDS Nexus Platform

global:
  scrape_interval: 30s
  evaluation_interval: 30s
  external_labels:
    cluster: 'sds-nexus'
    environment: 'production'

# Alertmanager configuration (optional)
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - localhost:9093

# Load alerting rules
rule_files:
  - '/etc/prometheus/rules/*.yml'

# Scrape configurations
scrape_configs:
  # SDS Nexus Platform API
  - job_name: 'sds-nexus-api'
    static_configs:
      - targets:
          - 'localhost:8000'
    metrics_path: '/api/v1/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s

  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets:
          - 'localhost:9090'
EOF

sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
```

#### 11.1c Configure Alert Rules

Create alert rules for SDS Nexus monitoring:

```bash
sudo tee /etc/prometheus/rules/sds_nexus_alerts.yml << 'EOF'
# Alert rules for SDS Nexus Platform

groups:
  - name: ceph_cluster_health
    interval: 60s
    rules:
      - alert: CephClusterUnhealthy
        expr: ceph_cluster_health_status{cluster_name!=""} > 0
        for: 5m
        labels:
          severity: critical
          component: ceph
        annotations:
          summary: "Ceph cluster {{ $labels.cluster_name }} is unhealthy"
          description: "Cluster health status is {{ $value }} (0=OK, 1=WARN, 2=ERR)"

      - alert: CephClusterNearFull
        expr: ceph_cluster_utilization_percent{cluster_name!=""} > 75
        for: 10m
        labels:
          severity: warning
          component: ceph
        annotations:
          summary: "Ceph cluster {{ $labels.cluster_name }} is {{ $value }}% full"
          description: "Cluster capacity utilization has exceeded 75%"

      - alert: CephClusterCriticallyFull
        expr: ceph_cluster_utilization_percent{cluster_name!=""} > 85
        for: 5m
        labels:
          severity: critical
          component: ceph
        annotations:
          summary: "Ceph cluster {{ $labels.cluster_name }} is critically full ({{ $value }}%)"
          description: "Immediate action required to prevent data loss"

  - name: ceph_osd_health
    interval: 60s
    rules:
      - alert: CephOSDDown
        expr: ceph_osd_down{cluster_name!=""} > 0
        for: 5m
        labels:
          severity: warning
          component: osd
        annotations:
          summary: "{{ $value }} OSD(s) down in cluster {{ $labels.cluster_name }}"
          description: "Check node health and network connectivity"

      - alert: CephOSDMultipleDown
        expr: ceph_osd_down{cluster_name!=""} >= 3
        for: 5m
        labels:
          severity: critical
          component: osd
        annotations:
          summary: "Multiple OSDs down in cluster {{ $labels.cluster_name }} ({{ $value }})"
          description: "This may indicate a systemic issue"

  - name: ceph_node_health
    interval: 60s
    rules:
      - alert: CephNodeHighCPU
        expr: ceph_node_cpu_usage_percent{cluster_name!="",node_name!=""} > 90
        for: 15m
        labels:
          severity: warning
          component: node
        annotations:
          summary: "High CPU usage on node {{ $labels.node_name }} ({{ $value }}%)"

      - alert: CephNodeHighMemory
        expr: ceph_node_memory_usage_percent{cluster_name!="",node_name!=""} > 90
        for: 15m
        labels:
          severity: warning
          component: node
        annotations:
          summary: "High memory usage on node {{ $labels.node_name }} ({{ $value }}%)"

      - alert: CephNodeHighTemperature
        expr: ceph_node_temperature_celsius{cluster_name!="",node_name!=""} > 80
        for: 10m
        labels:
          severity: warning
          component: node
        annotations:
          summary: "High temperature on node {{ $labels.node_name }} ({{ $value }}°C)"
EOF

sudo chown prometheus:prometheus /etc/prometheus/rules/sds_nexus_alerts.yml
```

#### 11.1d Create Prometheus Systemd Service

```bash
sudo tee /etc/systemd/system/prometheus.service << 'EOF'
[Unit]
Description=Prometheus Monitoring System
Documentation=https://prometheus.io/docs/introduction/overview/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries \
    --storage.tsdb.retention.time=30d \
    --web.enable-lifecycle

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start Prometheus
sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus

# Verify status
sudo systemctl status prometheus

# Check metrics endpoint
curl http://localhost:9090/metrics

# Open firewall port (adjust source if needed)
sudo firewall-cmd --permanent --add-port=9090/tcp
sudo firewall-cmd --reload
```

#### 11.1e Verify Prometheus is Scraping SDS Nexus

```bash
# Check that SDS Nexus metrics are being scraped
curl http://localhost:9090/api/v1/targets | python3 -m json.tool

# Query a sample metric
curl 'http://localhost:9090/api/v1/query?query=ceph_cluster_health_status' | python3 -m json.tool
```

---

### 11.2 Grafana Installation & Configuration

#### 11.2a Install Grafana on RHEL 10

```bash
# Add Grafana repository
sudo tee /etc/yum.repos.d/grafana.repo << 'EOF'
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF

# Install Grafana
sudo dnf5 install -y grafana

# Start and enable Grafana
sudo systemctl daemon-reload
sudo systemctl enable grafana-server
sudo systemctl start grafana-server

# Verify status
sudo systemctl status grafana-server

# Open firewall port
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload
```

#### 11.2b Configure Grafana

```bash
# Edit Grafana configuration
sudo tee /etc/grafana/grafana.ini << 'EOF'
[server]
protocol = http
http_port = 3000
domain = sds-nexus.your-domain.com
root_url = %(protocol)s://%(domain)s:%(http_port)s/
serve_from_sub_path = false

[security]
admin_user = admin
admin_password = CHANGE_ME_SECURE_PASSWORD
secret_key = CHANGE_ME_GENERATE_RANDOM_STRING

[auth]
disable_login_form = false

[users]
allow_sign_up = false
auto_assign_org = true
auto_assign_org_role = Viewer

[log]
mode = console file
level = info

[alerting]
enabled = true

[unified_alerting]
enabled = true
EOF

# Restart Grafana
sudo systemctl restart grafana-server
```

#### 11.2c Add Prometheus Data Source via API

```bash
# Wait for Grafana to be ready
sleep 10

# Add Prometheus data source
curl -X POST http://localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://localhost:9090",
    "access": "proxy",
    "isDefault": true,
    "jsonData": {
      "timeInterval": "30s",
      "queryTimeout": "60s",
      "httpMethod": "POST"
    }
  }'
```

#### 11.2d Create Grafana Dashboards

**Option 1: Import pre-built dashboard JSON**

The platform includes pre-configured Grafana dashboards in `docker/grafana/dashboards/`. Import them via:

1. Open Grafana web UI: `http://your-server:3000`
2. Login with admin credentials
3. Navigate to Dashboards → Import
4. Upload the JSON file or paste the JSON content
5. Select the Prometheus data source
6. Click Import

**Option 2: Create dashboard manually**

Create a dashboard for Ceph Cluster Health:

```bash
# Example: Create dashboard via API
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @- << 'EOF'
{
  "dashboard": {
    "title": "SDS Nexus - Ceph Cluster Health",
    "tags": ["sds-nexus", "ceph"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Cluster Health Status",
        "type": "stat",
        "targets": [
          {
            "expr": "ceph_cluster_health_status",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              {"value": "0", "text": "HEALTHY"},
              {"value": "1", "text": "WARNING"},
              {"value": "2", "text": "ERROR"}
            ],
            "thresholds": {
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 1, "color": "yellow"},
                {"value": 2, "color": "red"}
              ]
            }
          }
        }
      }
    ]
  },
  "overwrite": false
}
EOF
```

---

### 11.3 Alert Manager Configuration (Optional)

For email/Slack/PagerDuty alerts from Prometheus:

#### 11.3a Install Alertmanager

```bash
# Download Alertmanager
AM_VERSION="0.26.0"
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v${AM_VERSION}/alertmanager-${AM_VERSION}.linux-amd64.tar.gz

tar xzf alertmanager-${AM_VERSION}.linux-amd64.tar.gz
cd alertmanager-${AM_VERSION}.linux-amd64

# Install binary
sudo cp alertmanager amtool /usr/local/bin/
sudo chmod +x /usr/local/bin/alertmanager /usr/local/bin/amtool

# Create directories
sudo mkdir -p /etc/alertmanager
sudo mkdir -p /var/lib/alertmanager

# Create alertmanager user
sudo useradd \
    --system \
    --shell /sbin/nologin \
    --home-dir /var/lib/alertmanager \
    --no-create-home \
    --comment "Alertmanager" \
    alertmanager

sudo chown -R alertmanager:alertmanager /etc/alertmanager /var/lib/alertmanager
```

#### 11.3b Configure Alertmanager

```bash
sudo tee /etc/alertmanager/alertmanager.yml << 'EOF'
global:
  resolve_timeout: 5m
  smtp_smarthost: 'your-smtp-relay.internal:587'
  smtp_from: 'sds-nexus-alerts@your-domain.com'
  smtp_auth_username: 'sds-nexus@your-domain.com'
  smtp_auth_password: 'YOUR_SMTP_PASSWORD'
  smtp_require_tls: true

route:
  group_by: ['alertname', 'cluster', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'email-ops'

  routes:
    - match:
        severity: critical
      receiver: 'email-critical'
      continue: true

    - match:
        severity: warning
      receiver: 'email-ops'

receivers:
  - name: 'email-ops'
    email_configs:
      - to: 'storage-ops@your-domain.com'
        headers:
          Subject: '[SDS Nexus] {{ .GroupLabels.severity | toUpper }}: {{ .GroupLabels.alertname }}'

  - name: 'email-critical'
    email_configs:
      - to: 'storage-alerts@your-domain.com,oncall@your-domain.com'
        headers:
          Subject: '[SDS Nexus CRITICAL] {{ .GroupLabels.alertname }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'cluster']
EOF

sudo chown alertmanager:alertmanager /etc/alertmanager/alertmanager.yml
```

#### 11.3c Create Alertmanager Systemd Service

```bash
sudo tee /etc/systemd/system/alertmanager.service << 'EOF'
[Unit]
Description=Alertmanager
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=alertmanager
Group=alertmanager
ExecStart=/usr/local/bin/alertmanager \
    --config.file=/etc/alertmanager/alertmanager.yml \
    --storage.path=/var/lib/alertmanager \
    --web.listen-address=:9093

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable alertmanager
sudo systemctl start alertmanager
sudo systemctl status alertmanager

# Open firewall port
sudo firewall-cmd --permanent --add-port=9093/tcp
sudo firewall-cmd --reload
```

---

### 11.4 Dashboard Import & Configuration

Pre-configured dashboards are included in the project under `docker/grafana/dashboards/`:

1. **Ceph Cluster Overview** - Overall cluster health, capacity, OSDs, MONs
2. **Node Metrics** - CPU, memory, load, temperature per node
3. **Object Storage (RGW)** - Bucket usage, user operations, API metrics
4. **Platform Health** - API performance, worker jobs, database connections
5. **Alerts Dashboard** - Active alerts, alert history, suppression status

To import all dashboards:

```bash
cd /opt/sds-nexus
for dashboard in docker/grafana/dashboards/*.json; do
  echo "Importing $(basename $dashboard)..."
  curl -X POST http://localhost:3000/api/dashboards/db \
    -H "Content-Type: application/json" \
    -u admin:CHANGE_ME_SECURE_PASSWORD \
    -d @"$dashboard"
done
```

---

## 12. Multi-Environment Configuration Management

The platform supports multiple deployment environments (development, staging, production) with environment-specific configuration files.

---

### 12.1 Environment-Specific Configuration Files

The platform loads configuration from environment-specific `.env` files:

| Environment | Configuration File | Location |
|---|---|---|
| Development | `.env.development` | Project root (for local dev) |
| Staging | `.env.staging` | `/etc/sds-nexus/staging.env` (production deploy) |
| Production | `.env.production` | `/etc/sds-nexus/production.env` (production deploy) |

#### 12.1a Configuration File Structure

Example production configuration (`/etc/sds-nexus/production.env`):

```bash
# Environment
APP_ENV=production

# Database
DB_HOST=postgres-prod.internal
DB_NAME=sds_nexus_prod
DB_USER=sds_nexus_user
DB_PASSWORD=SECURE_PASSWORD_HERE

# Ceph
CEPH_CLUSTER_NAME=ue-south-1
CEPH_MONITOR_HOST=dbr-gbch-sds01
# ... etc
```

See `.env.production.example` for full configuration template.

---

### 12.2 Environment Variable Management

#### 12.2a Set Active Environment

The platform detects the environment via the `APP_ENV` variable:

```bash
# Set environment for current session
export APP_ENV=production

# Or set in the environment file
echo "APP_ENV=production" >> /etc/sds-nexus/production.env
```

#### 12.2b Configuration Precedence

Configuration values are loaded in the following order (highest to lowest priority):

1. **Environment variables** (set in shell/systemd)
2. **Environment-specific file** (e.g., `/etc/sds-nexus/production.env`)
3. **Base `.env` file** (fallback)
4. **Default values** (in `config.py`)

#### 12.2c Validation

The platform validates required configuration on startup:

```bash
# Test configuration loading
cd /opt/sds-nexus
sudo -u sds-nexus APP_ENV=production /opt/sds-nexus/venv/bin/python3 << 'EOF'
from app.core.environment import validate_environment_config, get_environment_info

# Validate configuration
if validate_environment_config():
    print("✓ Configuration is valid")
    info = get_environment_info()
    print(f"  Environment: {info['environment']}")
    print(f"  Config file: {info['config_file']}")
else:
    print("✗ Configuration validation failed")
    exit(1)
EOF
```

---

### 12.3 Switching Between Environments

#### 12.3a Update Systemd Service for Environment

```bash
# Edit the systemd service file
sudo systemctl edit sds-nexus-api.service

# Add environment override:
[Service]
Environment="APP_ENV=production"
EnvironmentFile=/etc/sds-nexus/production.env

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart sds-nexus-api
```

#### 12.3b Docker Compose Environment Selection

```bash
# Development
docker-compose up -d

# Staging (with custom env file)
docker-compose --env-file .env.staging up -d

# Production
docker-compose --env-file /etc/sds-nexus/production.env up -d
```

---

## 13. Maintenance Windows & Alert Suppression

The platform supports scheduled maintenance windows to suppress alerts during planned system changes.

---

### 13.1 Creating Maintenance Windows

#### 13.1a Via Python API

```python
from datetime import datetime, timedelta
from app.core.maintenance import create_maintenance_window, MaintenanceType
from app.db.session import get_db

# Create a 4-hour maintenance window starting now
start_time = datetime.utcnow()
end_time = start_time + timedelta(hours=4)

window = create_maintenance_window(
    cluster_id=1,
    start_time=start_time,
    end_time=end_time,
    reason="Upgrade Ceph OSDs on nodes sds08-sds12",
    maintenance_type=MaintenanceType.SCHEDULED,
    created_by="ops-team",
    suppress_alert_sources="osd,node",  # Only suppress OSD and node alerts
    db=next(get_db()),
)

print(f"Created maintenance window {window.id}")
```

#### 13.1b Via Database Insert

```sql
-- Create maintenance window via SQL
INSERT INTO maintenance_windows (
    cluster_id,
    start_time,
    end_time,
    reason,
    maintenance_type,
    created_by,
    suppress_alert_sources,
    is_active
) VALUES (
    1,
    '2024-03-15 02:00:00',
    '2024-03-15 06:00:00',
    'Scheduled firmware update on storage nodes',
    'scheduled',
    'ops-team',
    '*',  -- Suppress all alert sources
    1
);
```

---

### 13.2 Alert Suppression Rules

#### 13.2a Suppression Behavior

When a maintenance window is active:

1. Platform checks `is_maintenance_active(cluster_id)` before creating alerts
2. If maintenance window exists with `*` in `suppress_alert_sources`, ALL alerts are suppressed
3. If specific sources are listed (e.g., `"osd,node"`), only those alert sources are suppressed
4. Alerts are still logged to database with `status='suppressed'` for audit trail
5. Prometheus metrics continue to be updated (only alert creation is suppressed)

#### 13.2b Alert Source Types

Valid alert sources for suppression:

- `cluster_health` - Cluster-wide health alerts
- `osd` - OSD up/down alerts
- `node` - Node CPU/memory/temperature alerts
- `capacity` - Storage capacity warnings
- `placement_group` - PG degraded/undersized alerts
- `bucket` - RGW bucket alerts
- `tenant` - Tenant usage alerts
- `*` - All alert types

#### 13.2c Example Maintenance Window Configurations

**Full cluster maintenance (suppress all alerts):**
```python
suppress_alert_sources="*"
```

**OSD replacement (suppress only OSD alerts):**
```python
suppress_alert_sources="osd"
```

**Network maintenance (suppress node connectivity alerts):**
```python
suppress_alert_sources="node,osd"
```

---

### 13.3 Maintenance Window API

#### 13.3a List Active Maintenance Windows

```bash
# Via SQL
SELECT 
    id,
    cluster_id,
    start_time,
    end_time,
    reason,
    maintenance_type,
    is_active
FROM maintenance_windows
WHERE is_active = 1
  AND start_time <= NOW()
  AND end_time >= NOW();
```

#### 13.3b End Maintenance Window Early

```python
from app.core.maintenance import end_maintenance_window
from app.db.session import get_db

# End maintenance window before scheduled end time
success = end_maintenance_window(
    window_id=123,
    db=next(get_db()),
)

if success:
    print("Maintenance window ended")
else:
    print("Maintenance window not found")
```

#### 13.3c Cleanup Expired Windows

The platform automatically cleans up expired maintenance windows via a scheduled job. To manually trigger cleanup:

```python
from app.core.maintenance import cleanup_expired_windows
from app.db.session import get_db

# Mark expired windows as inactive
count = cleanup_expired_windows(db=next(get_db()))
print(f"Cleaned up {count} expired maintenance windows")
```

#### 13.3d Check if Maintenance is Active

```python
from app.core.maintenance import is_maintenance_active
from app.db.session import get_db

# Check if maintenance window is currently active for cluster
if is_maintenance_active(cluster_id=1, db=next(get_db())):
    print("Maintenance window is active - alerts will be suppressed")
else:
    print("No active maintenance window")
```

---

## Summary

The SDS Nexus platform now includes:

✅ **Prometheus Integration** - Metrics collection with 30-day retention
✅ **Grafana Dashboards** - Pre-built dashboards for cluster, node, and platform health
✅ **Alert Rules** - Comprehensive alerting for Ceph and platform issues
✅ **Multi-Environment Support** - Development, staging, and production configurations
✅ **Maintenance Windows** - Scheduled alert suppression during planned changes
✅ **Alert Manager** (Optional) - Email/Slack/PagerDuty notifications

All metrics are automatically exposed at `/api/v1/metrics` and scraped by Prometheus every 15 seconds.

Access the monitoring stack:
- **Prometheus**: `http://your-server:9090`
- **Grafana**: `http://your-server:3000` (default login: admin/admin)
- **Alertmanager**: `http://your-server:9093` (if configured)
