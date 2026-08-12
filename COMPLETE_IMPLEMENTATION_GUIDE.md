# SDS Nexus Platform - Complete Implementation Guide

## 📖 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Deployment Options](#deployment-options)
4. [Option 1: Docker Compose (Development)](#option-1-docker-compose-development)
5. [Option 2: Production VMs (RHEL 10)](#option-2-production-vms-rhel-10)
6. [Option 3: Kubernetes (Docker Desktop)](#option-3-kubernetes-docker-desktop)
7. [Option 4: Production Kubernetes](#option-4-production-kubernetes)
8. [Post-Deployment Configuration](#post-deployment-configuration)
9. [Verification & Testing](#verification--testing)
10. [Troubleshooting](#troubleshooting)
11. [Operations Guide](#operations-guide)

---

## Overview

The **SDS Nexus Platform** is an enterprise monitoring and chargeback system for Ceph object storage with:

- **Prometheus + Grafana** monitoring stack
- **Tenant usage tracking** with 30-day historical data
- **Cost calculations** in GBP/USD
- **Automated backups** and health checks
- **Multi-environment** support (dev/staging/prod)
- **High availability** options with Kubernetes

### What You'll Deploy

| Component | Purpose | Resources |
|-----------|---------|-----------|
| **API** | FastAPI REST API | 256Mi RAM, 250m CPU |
| **PostgreSQL** | Database | 256Mi RAM, 250m CPU |
| **Prometheus** | Metrics collection | 512Mi RAM, 500m CPU |
| **Grafana** | Dashboards | 256Mi RAM, 250m CPU |
| **Workers** | Background jobs | 128Mi RAM, 100m CPU |

### Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                  SDS Nexus Platform                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   API    │→│PostgreSQL │  │Prometheus│  │ Grafana  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│       │             │              │             │         │
│       │             │              │             │         │
│       └─────────────┴──────────────┴─────────────┘         │
│                          ↓                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ↓
                    ┌─────────────┐
                    │    Ceph     │
                    │   Cluster   │
                    │    (VMs)    │
                    └─────────────┘
```

---

## Prerequisites

### Common Requirements (All Deployments)

- [ ] **Git** installed
- [ ] **Python 3.12+** installed
- [ ] **Network access** to Ceph cluster
- [ ] **SSH key** for Ceph cluster (read-only)
- [ ] **RGW credentials** (access/secret keys)
- [ ] **SMTP server** details for email notifications
- [ ] **Database password** prepared

### Clone Repository

```bash
# Clone from GitHub
git clone https://github.com/Dinesh1496/SDS.git
cd SDS
```

---

## Deployment Options

Choose the deployment option that best fits your needs:

| Option | Use Case | Time | Complexity |
|--------|----------|------|------------|
| **[Option 1](#option-1-docker-compose-development)** | Development, Testing | 10 min | Easy |
| **[Option 2](#option-2-production-vms-rhel-10)** | Production VMs | 2-3 hrs | Medium |
| **[Option 3](#option-3-kubernetes-docker-desktop)** | K8s Learning, Local Dev | 20 min | Easy |
| **[Option 4](#option-4-production-kubernetes)** | Production K8s | 1-2 hrs | Medium |

---

## Option 1: Docker Compose (Development)

**Best for:** Quick testing, development, demos

**Time Required:** 10-15 minutes

### Step 1: Prerequisites

```bash
# Verify Docker and Docker Compose
docker --version
docker-compose --version
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
notepad .env  # Windows
# OR
vi .env       # Linux
```

**Minimum required configuration:**
```bash
# Application
APP_ENV=development
APP_SECRET_KEY=<generate-32-char-secret>
JWT_SECRET_KEY=<generate-32-char-secret>

# Database
DB_PASSWORD=devpassword123

# Ceph (optional for testing without real cluster)
CEPH_MONITOR_HOST=localhost
RGW_ENDPOINT=http://localhost:7480
```

**Generate secrets:**
```powershell
# PowerShell
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
```

```bash
# Linux
openssl rand -base64 32
```

### Step 3: Start Services

```bash
cd docker

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

### Step 4: Run Database Migrations

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Verify
docker-compose exec api alembic current
```

### Step 5: Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://localhost:8000 | None |
| **API Docs** | http://localhost:8000/docs | None |
| **Prometheus** | http://localhost:9090 | None |
| **Grafana** | http://localhost:3000 | admin/admin |
| **Metrics** | http://localhost:8000/api/v1/metrics | None |

### Step 6: Import Grafana Dashboards

```bash
# Wait for Grafana to be ready
timeout 30

# Import Ceph Cluster Overview
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @docker/grafana/dashboards/ceph-cluster-overview.json

# Import Tenant Usage & Chargeback
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @docker/grafana/dashboards/tenant-usage-chargeback.json
```

### Step 7: Verify

```bash
# Test API health
curl http://localhost:8000/api/v1/health/live

# Test metrics endpoint
curl http://localhost:8000/api/v1/metrics | head -20

# View logs
docker-compose logs -f api
```

### ✅ Docker Compose Complete!

**What's Running:**
- ✅ API on port 8000
- ✅ PostgreSQL on port 5432
- ✅ Prometheus on port 9090
- ✅ Grafana on port 3000

**Next Steps:**
1. Access Grafana dashboards
2. Configure Ceph connection (optional)
3. Test metrics collection

---

## Option 2: Production VMs (RHEL 10)

**Best for:** Production deployment on traditional VMs

**Time Required:** 2-3 hours

### Architecture

```
┌─────────────────────────────────────────────┐
│         RHEL 10 Server                      │
│                                             │
│  ┌─────────────┐  ┌─────────────┐         │
│  │ SDS Nexus   │  │ PostgreSQL  │         │
│  │ API Service │  │   16        │         │
│  │ (systemd)   │  │ (systemd)   │         │
│  └─────────────┘  └─────────────┘         │
│                                             │
│  ┌─────────────┐  ┌─────────────┐         │
│  │ Prometheus  │  │  Grafana    │         │
│  │ (systemd)   │  │  (systemd)  │         │
│  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────┘
```

### Step 1: System Preparation (15 minutes)

#### 1.1 Update System

```bash
# Update system
sudo dnf5 update -y

# Install prerequisites
sudo dnf5 install -y \
  git \
  python3.12 \
  python3.12-pip \
  python3.12-devel \
  postgresql-devel \
  gcc \
  openssl-devel \
  libffi-devel \
  wget \
  tar
```

#### 1.2 Create Application User

```bash
# Create user
sudo useradd -r -m -s /bin/bash sds-nexus

# Create directories
sudo mkdir -p /opt/sds-nexus
sudo mkdir -p /etc/sds-nexus
sudo mkdir -p /etc/sds-nexus/keys
sudo mkdir -p /var/log/sds-nexus
sudo mkdir -p /var/sds-nexus/backups

# Set permissions
sudo chown -R sds-nexus:sds-nexus /opt/sds-nexus
sudo chown -R sds-nexus:sds-nexus /etc/sds-nexus
sudo chown -R sds-nexus:sds-nexus /var/log/sds-nexus
sudo chown -R sds-nexus:sds-nexus /var/sds-nexus
```

#### 1.3 Configure Firewall

```bash
# Add firewall rules
sudo firewall-cmd --permanent --add-port=8000/tcp  # API
sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

### Step 2: Install PostgreSQL (10 minutes)

#### 2.1 Install PostgreSQL 16

```bash
# Install PostgreSQL
sudo dnf5 install -y postgresql16-server postgresql16-contrib

# Initialize database
sudo postgresql-setup --initdb

# Enable and start
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

#### 2.2 Create Database

```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE sds_nexus;
CREATE USER sds_nexus_user WITH PASSWORD 'YOUR_SECURE_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE sds_nexus TO sds_nexus_user;
\c sds_nexus
GRANT ALL ON SCHEMA public TO sds_nexus_user;
ALTER DATABASE sds_nexus OWNER TO sds_nexus_user;
EOF
```

#### 2.3 Configure Authentication

```bash
# Edit pg_hba.conf
sudo vi /var/lib/pgsql/16/data/pg_hba.conf

# Add this line before other rules:
# host    sds_nexus    sds_nexus_user    127.0.0.1/32    scram-sha-256

# Restart PostgreSQL
sudo systemctl restart postgresql

# Test connection
psql -h localhost -U sds_nexus_user -d sds_nexus -c "SELECT 1;"
```

### Step 3: Deploy Application (20 minutes)

#### 3.1 Clone Repository

```bash
# Clone as sds-nexus user
sudo -u sds-nexus git clone https://github.com/Dinesh1496/SDS.git /opt/sds-nexus

# Or copy files
sudo cp -r /path/to/SDS/* /opt/sds-nexus/
sudo chown -R sds-nexus:sds-nexus /opt/sds-nexus
```

#### 3.2 Create Virtual Environment

```bash
# Switch to sds-nexus user
sudo -u sds-nexus bash

# Create venv
cd /opt/sds-nexus
python3.12 -m venv venv

# Activate
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Exit sds-nexus user
exit
```

#### 3.3 Configure Environment

```bash
# Copy template
sudo cp /opt/sds-nexus/.env.production.example /etc/sds-nexus/production.env

# Set permissions
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/production.env
sudo chmod 600 /etc/sds-nexus/production.env

# Edit configuration
sudo vi /etc/sds-nexus/production.env
```

**Required Configuration:**
```bash
# Application
APP_ENV=production
APP_SECRET_KEY=<GENERATE_32_CHAR_SECRET>
JWT_SECRET_KEY=<GENERATE_32_CHAR_SECRET>

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sds_nexus
DB_USER=sds_nexus_user
DB_PASSWORD=<YOUR_DATABASE_PASSWORD>

# Ceph Configuration
CEPH_CLUSTER_NAME=<your-cluster-name>
CEPH_MONITOR_HOST=<ceph-monitor-ip>
CEPH_ADMIN_NODE=<ceph-admin-node>
CEPH_SSH_KEY_PATH=/etc/sds-nexus/keys/sds_monitor_key

# RGW Configuration
RGW_ENDPOINT=<http://rgw-endpoint:port>
RGW_ACCESS_KEY=<rgw-access-key>
RGW_SECRET_KEY=<rgw-secret-key>

# SMTP Configuration
SMTP_HOST=<smtp-server>
SMTP_PORT=587
SMTP_USER=<smtp-user>
SMTP_PASSWORD=<smtp-password>
SMTP_FROM_ADDRESS=<from-email>
```

#### 3.4 Setup SSH Keys

```bash
# Copy SSH key for Ceph access
sudo cp /path/to/your/ceph_ssh_key /etc/sds-nexus/keys/sds_monitor_key

# Set permissions
sudo chmod 600 /etc/sds-nexus/keys/sds_monitor_key
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/keys/sds_monitor_key

# Test SSH connection
sudo -u sds-nexus ssh -i /etc/sds-nexus/keys/sds_monitor_key sds-monitor@<ceph-node>
```

#### 3.5 Run Database Migrations

```bash
# Switch to sds-nexus user
sudo -u sds-nexus bash
cd /opt/sds-nexus
source venv/bin/activate

# Set environment
export APP_ENV=production

# Run migrations
alembic upgrade head

# Verify
alembic current

exit
```

### Step 4: Install Prometheus (15 minutes)

#### 4.1 Download and Install

```bash
# Download Prometheus
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz

# Extract
tar xzf prometheus-2.48.0.linux-amd64.tar.gz

# Install binaries
sudo cp prometheus-2.48.0.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-2.48.0.linux-amd64/promtool /usr/local/bin/

# Verify
prometheus --version
```

#### 4.2 Configure Prometheus

```bash
# Create directories
sudo mkdir -p /etc/prometheus/rules
sudo mkdir -p /var/lib/prometheus

# Copy configuration
sudo cp /opt/sds-nexus/docker/prometheus/prometheus.yml /etc/prometheus/
sudo cp /opt/sds-nexus/docker/prometheus/rules/*.yml /etc/prometheus/rules/

# Edit prometheus.yml - update target
sudo vi /etc/prometheus/prometheus.yml
# Change: targets: ['api:8000'] to targets: ['localhost:8000']

# Create user
sudo useradd --no-create-home --shell /bin/false prometheus

# Set permissions
sudo chown -R prometheus:prometheus /etc/prometheus
sudo chown -R prometheus:prometheus /var/lib/prometheus
```

#### 4.3 Create Systemd Service

```bash
# Create service file
sudo tee /etc/systemd/system/prometheus.service > /dev/null << 'EOF'
[Unit]
Description=Prometheus
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus \
    --web.listen-address=:9090 \
    --storage.tsdb.retention.time=30d

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

# Reload, enable, and start
sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus

# Verify
sudo systemctl status prometheus
curl http://localhost:9090/-/healthy
```

### Step 5: Install Grafana (15 minutes)

#### 5.1 Add Repository and Install

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
EOF

# Install Grafana
sudo dnf5 install -y grafana

# Enable and start
sudo systemctl enable grafana-server
sudo systemctl start grafana-server

# Verify
sudo systemctl status grafana-server
```

#### 5.2 Configure Datasource

```bash
# Wait for Grafana to start
sleep 10

# Add Prometheus datasource
curl -X POST http://localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://localhost:9090",
    "access": "proxy",
    "isDefault": true
  }'
```

#### 5.3 Import Dashboards

```bash
# Import Ceph Cluster Overview
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @/opt/sds-nexus/docker/grafana/dashboards/ceph-cluster-overview.json

# Import Tenant Usage & Chargeback
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d @/opt/sds-nexus/docker/grafana/dashboards/tenant-usage-chargeback.json
```

#### 5.4 Change Admin Password

```bash
# Access Grafana
# URL: http://YOUR_SERVER:3000
# Login: admin / admin
# You'll be prompted to change password
```

### Step 6: Configure Application Service (10 minutes)

#### 6.1 Create Systemd Service

```bash
sudo tee /etc/systemd/system/sds-nexus-api.service > /dev/null << 'EOF'
[Unit]
Description=SDS Nexus Platform API
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=sds-nexus
Group=sds-nexus
WorkingDirectory=/opt/sds-nexus
Environment="PATH=/opt/sds-nexus/venv/bin"
Environment="APP_ENV=production"
ExecStart=/opt/sds-nexus/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF
```

#### 6.2 Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable sds-nexus-api
sudo systemctl start sds-nexus-api

# Verify
sudo systemctl status sds-nexus-api
```

### Step 7: Setup Automated Tasks (10 minutes)

#### 7.1 Copy Scripts

```bash
# Copy backup script
sudo cp /opt/sds-nexus/scripts/backup_database.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/backup_database.sh

# Copy health check script
sudo cp /opt/sds-nexus/scripts/health_check.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/health_check.sh

# Copy log rotation config
sudo cp /opt/sds-nexus/scripts/log_rotation.conf /etc/logrotate.d/sds-nexus
```

#### 7.2 Configure Cron Jobs

```bash
# Edit crontab for sds-nexus user
sudo crontab -e -u sds-nexus
```

Add these lines:
```cron
# Database backup - daily at 2 AM
0 2 * * * /usr/local/bin/backup_database.sh >> /var/log/sds-nexus/backup.log 2>&1

# Health check - every 15 minutes
*/15 * * * * /usr/local/bin/health_check.sh --alert-only >> /var/log/sds-nexus/health-check.log 2>&1
```

### Step 8: Configure SELinux (Optional, 10 minutes)

```bash
# If SELinux is enabled
getenforce

# Allow API port
sudo semanage port -a -t http_port_t -p tcp 8000

# Allow database connections
sudo setsebool -P httpd_can_network_connect_db 1

# Allow network connections
sudo setsebool -P httpd_can_network_connect 1

# Verify
getsebool httpd_can_network_connect_db
getsebool httpd_can_network_connect
```

### Step 9: Verification (15 minutes)

#### 9.1 Service Status

```bash
# Check all services
sudo systemctl status sds-nexus-api
sudo systemctl status prometheus
sudo systemctl status grafana-server
sudo systemctl status postgresql
```

#### 9.2 API Health Checks

```bash
# Liveness
curl http://localhost:8000/api/v1/health/live

# Readiness
curl http://localhost:8000/api/v1/health/ready

# Metrics
curl http://localhost:8000/api/v1/metrics | grep sds_nexus_app_info

# API Documentation
curl http://localhost:8000/docs
```

#### 9.3 Prometheus Verification

```bash
# Check Prometheus is scraping
curl -s http://localhost:9090/api/v1/targets | \
  jq '.data.activeTargets[] | select(.job=="sds-nexus-api")'

# Should show: "health": "up"
```

#### 9.4 Grafana Verification

```bash
# Access Grafana
# URL: http://YOUR_SERVER:3000
# Login with your password

# Navigate to Dashboards
# Verify both dashboards are visible and showing data
```

#### 9.5 Run Health Check

```bash
# Run comprehensive health check
sudo -u sds-nexus /usr/local/bin/health_check.sh --verbose
```

### ✅ Production VM Deployment Complete!

**What's Running:**
- ✅ API Service (systemd)
- ✅ PostgreSQL 16 (systemd)
- ✅ Prometheus (systemd)
- ✅ Grafana (systemd)
- ✅ Automated backups (cron)
- ✅ Health checks (cron)

**Access URLs:**
- API: http://YOUR_SERVER:8000
- Prometheus: http://YOUR_SERVER:9090
- Grafana: http://YOUR_SERVER:3000

---

## Option 3: Kubernetes (Docker Desktop)

**Best for:** Learning Kubernetes, local development

**Time Required:** 20-30 minutes

**See:** [k8s/QUICK_START_K8S.md](k8s/QUICK_START_K8S.md) for detailed steps

### Quick Summary

```bash
# Build Docker image
docker build -t sds-nexus:latest -f docker/Dockerfile .

# Deploy to Kubernetes
kubectl apply -f k8s/base/
kubectl apply -f k8s/database/
kubectl apply -f k8s/api/

# Wait for ready
kubectl wait --for=condition=ready pod --all -n sds-nexus --timeout=300s

# Access API
kubectl port-forward -n sds-nexus svc/sds-nexus-api 8000:8000

# Test
curl http://localhost:8000/api/v1/health/live
```

### What You Get

- ✅ **2 API replicas** (high availability)
- ✅ **Auto-scaling** (2-10 pods)
- ✅ **Self-healing** (automatic restarts)
- ✅ **Load balancing**
- ✅ **Rolling updates**

**Full Guide:** [KUBERNETES_INTEGRATION.md](KUBERNETES_INTEGRATION.md)

---

## Option 4: Production Kubernetes

**Best for:** Production deployment with Kubernetes

**Time Required:** 1-2 hours

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Helm 3+ installed (optional)
- Container registry access
- StorageClass configured

### Step 1: Build and Push Image

```bash
# Build image
docker build -t your-registry/sds-nexus:v1.0.0 -f docker/Dockerfile .

# Push to registry
docker push your-registry/sds-nexus:v1.0.0
```

### Step 2: Update Manifests

```bash
# Update image in deployment
sed -i 's|image: sds-nexus:latest|image: your-registry/sds-nexus:v1.0.0|' k8s/api/api-deployment.yaml
```

### Step 3: Create Namespace

```bash
kubectl create namespace sds-nexus-prod
kubectl config set-context --current --namespace=sds-nexus-prod
```

### Step 4: Create Secrets

```bash
# Generate secrets
APP_SECRET=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 32)
DB_PASSWORD=$(openssl rand -base64 32)

# Create secret
kubectl create secret generic sds-nexus-secrets \
  --from-literal=app-secret-key=$APP_SECRET \
  --from-literal=jwt-secret-key=$JWT_SECRET \
  --from-literal=db-password=$DB_PASSWORD \
  --from-literal=ceph-ssh-key="" \
  --from-literal=rgw-access-key="YOUR_RGW_ACCESS_KEY" \
  --from-literal=rgw-secret-key="YOUR_RGW_SECRET_KEY" \
  --from-literal=smtp-password="YOUR_SMTP_PASSWORD" \
  -n sds-nexus-prod
```

### Step 5: Update ConfigMap

```bash
# Edit configmap with production values
kubectl apply -f k8s/base/configmap.yaml -n sds-nexus-prod
```

### Step 6: Deploy Database

```bash
# Update StorageClass if needed
# Edit k8s/database/postgresql-pvc.yaml

# Deploy PostgreSQL
kubectl apply -f k8s/database/ -n sds-nexus-prod

# Wait for ready
kubectl wait --for=condition=ready pod -l app=postgresql -n sds-nexus-prod --timeout=180s
```

### Step 7: Run Migrations

```bash
# Run migrations as a Job
kubectl run alembic-migrate \
  --image=your-registry/sds-nexus:v1.0.0 \
  --restart=Never \
  -n sds-nexus-prod \
  --command -- alembic upgrade head

# Check logs
kubectl logs alembic-migrate -n sds-nexus-prod
```

### Step 8: Deploy API

```bash
# Deploy API with HPA
kubectl apply -f k8s/api/ -n sds-nexus-prod

# Wait for ready
kubectl wait --for=condition=ready pod -l app=sds-nexus-api -n sds-nexus-prod --timeout=300s
```

### Step 9: Configure Ingress

```bash
# Create Ingress (example with nginx-ingress)
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sds-nexus-ingress
  namespace: sds-nexus-prod
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - sds-nexus.yourdomain.com
    secretName: sds-nexus-tls
  rules:
  - host: sds-nexus.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: sds-nexus-api
            port:
              number: 8000
EOF
```

### Step 10: Deploy Monitoring

```bash
# Deploy Prometheus and Grafana
kubectl apply -f k8s/monitoring/ -n sds-nexus-prod

# Or use Prometheus Operator
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/bundle.yaml
```

### ✅ Production Kubernetes Complete!

**What's Running:**
- ✅ API with 2+ replicas
- ✅ PostgreSQL StatefulSet
- ✅ Prometheus monitoring
- ✅ Grafana dashboards
- ✅ Auto-scaling (HPA)
- ✅ Ingress with TLS

**Access:**
- External: https://sds-nexus.yourdomain.com
- Internal: http://sds-nexus-api.sds-nexus-prod.svc.cluster.local:8000

---

## Post-Deployment Configuration

### 1. Change Default Passwords

```bash
# Grafana
# Access: http://YOUR_SERVER:3000
# Login: admin/admin
# Change password when prompted
```

### 2. Configure Ceph Connection

Edit environment file or ConfigMap with actual Ceph details:
```bash
CEPH_MONITOR_HOST=<actual-ceph-monitor>
CEPH_ADMIN_NODE=<actual-ceph-admin-node>
RGW_ENDPOINT=<actual-rgw-endpoint>
```

### 3. Configure Email Notifications

```bash
SMTP_HOST=<your-smtp-server>
SMTP_PORT=587
SMTP_USER=<your-smtp-user>
SMTP_PASSWORD=<your-smtp-password>
SMTP_FROM_ADDRESS=<from-email>
```

### 4. Set Chargeback Rates

Update rates in ConfigMap or environment:
```bash
CHARGEBACK_GBP_PER_GB_MONTH=0.05
CHARGEBACK_USD_PER_GB_MONTH=0.06
```

### 5. Create Initial Cluster Record

```python
# Access Python shell
python

from app.db.session import get_db
from app.models.cluster import Cluster

db = next(get_db())
cluster = Cluster(
    name="ue-south-1",
    display_name="UK South Production Cluster",
    location="London",
    ceph_version="17.2.6",
    is_active=True
)
db.add(cluster)
db.commit()
```

---

## Verification & Testing

### Health Checks

```bash
# API liveness
curl http://YOUR_SERVER:8000/api/v1/health/live

# API readiness
curl http://YOUR_SERVER:8000/api/v1/health/ready

# Metrics endpoint
curl http://YOUR_SERVER:8000/api/v1/metrics | head -20
```

### Prometheus Checks

```bash
# Check targets
curl http://YOUR_SERVER:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="sds-nexus-api")'

# Query metrics
curl 'http://YOUR_SERVER:9090/api/v1/query?query=up{job="sds-nexus-api"}' | jq
```

### Grafana Checks

1. Access: http://YOUR_SERVER:3000
2. Navigate to Dashboards
3. Verify both dashboards load
4. Check panels show data

### Database Checks

```bash
# Check connection
psql -h localhost -U sds_nexus_user -d sds_nexus -c "SELECT version();"

# Check tables
psql -h localhost -U sds_nexus_user -d sds_nexus -c "\dt"

# Check migration status
psql -h localhost -U sds_nexus_user -d sds_nexus -c "SELECT * FROM alembic_version;"
```

### Log Checks

```bash
# Docker Compose
docker-compose logs -f api

# Systemd
sudo journalctl -u sds-nexus-api -f

# Kubernetes
kubectl logs -f deployment/sds-nexus-api -n sds-nexus
```

---

## Troubleshooting

### API Won't Start

**Symptoms:** Service fails to start or crashes immediately

**Diagnosis:**
```bash
# Docker Compose
docker-compose logs api

# Systemd
sudo journalctl -u sds-nexus-api -n 100

# Kubernetes
kubectl logs -l app=sds-nexus-api -n sds-nexus
```

**Common Causes:**
1. Database connection failure
   - Check DB_HOST, DB_PORT, DB_PASSWORD
   - Verify PostgreSQL is running
   - Test connection manually

2. Missing environment variables
   - Check all required variables are set
   - Verify secrets are loaded

3. Port already in use
   - Check: `sudo lsof -i :8000`
   - Change port or stop conflicting service

**Solution:**
```bash
# Fix configuration
# Restart service
sudo systemctl restart sds-nexus-api

# Verify
curl http://localhost:8000/api/v1/health/live
```

### Prometheus Not Scraping

**Symptoms:** Prometheus targets show as "DOWN"

**Diagnosis:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# Check API metrics endpoint
curl http://localhost:8000/api/v1/metrics
```

**Common Causes:**
1. Wrong target address in prometheus.yml
2. Firewall blocking connection
3. API not exposing metrics

**Solution:**
```bash
# Verify prometheus.yml has correct target
cat /etc/prometheus/prometheus.yml | grep targets

# Should be: targets: ['localhost:8000']
# Not: targets: ['api:8000']

# Restart Prometheus
sudo systemctl restart prometheus
```

### Grafana Shows No Data

**Symptoms:** Dashboards show "No Data"

**Diagnosis:**
```bash
# Check datasource
curl http://localhost:3000/api/datasources -u admin:YOUR_PASSWORD | jq

# Test Prometheus connection
curl http://localhost:9090/api/v1/query?query=up
```

**Common Causes:**
1. Datasource not configured
2. Wrong Prometheus URL
3. Time range issue

**Solution:**
```bash
# Re-add datasource
curl -X POST http://localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://localhost:9090",
    "access": "proxy",
    "isDefault": true
  }'

# Test in Grafana Explore tab
```

### Database Connection Errors

**Symptoms:** "could not connect to server" errors

**Diagnosis:**
```bash
# Test connection
psql -h localhost -U sds_nexus_user -d sds_nexus

# Check PostgreSQL is running
sudo systemctl status postgresql

# Check pg_hba.conf
sudo cat /var/lib/pgsql/16/data/pg_hba.conf | grep sds_nexus
```

**Solution:**
```bash
# Verify pg_hba.conf has correct entry
# host    sds_nexus    sds_nexus_user    127.0.0.1/32    scram-sha-256

# Restart PostgreSQL
sudo systemctl restart postgresql

# Test again
psql -h localhost -U sds_nexus_user -d sds_nexus -c "SELECT 1;"
```

### Kubernetes Pods Not Starting

**Symptoms:** Pods stuck in Pending, CrashLoopBackOff, or ImagePullBackOff

**Diagnosis:**
```bash
# Check pod status
kubectl get pods -n sds-nexus

# Describe pod
kubectl describe pod <pod-name> -n sds-nexus

# Check logs
kubectl logs <pod-name> -n sds-nexus

# Check events
kubectl get events -n sds-nexus --sort-by='.lastTimestamp'
```

**Common Causes:**
1. ImagePullBackOff - Image not found
   - Build and tag image correctly
   - Push to registry if needed

2. CrashLoopBackOff - Application crashing
   - Check logs for errors
   - Verify configuration

3. Pending - Resource constraints
   - Check node resources
   - Adjust resource requests

---

## Operations Guide

### Daily Operations

#### Morning Health Check (5 minutes)

```bash
# Run health check script
/usr/local/bin/health_check.sh --verbose

# Or manually:
# 1. Check API
curl http://localhost:8000/api/v1/health/live

# 2. Check Prometheus
curl http://localhost:9090/-/healthy

# 3. Check Grafana
curl http://localhost:3000/api/health

# 4. Check for alerts
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'
```

#### View Logs

```bash
# Docker Compose
docker-compose logs --tail=100 -f api

# Systemd
sudo journalctl -u sds-nexus-api -n 100 -f

# Kubernetes
kubectl logs -f deployment/sds-nexus-api -n sds-nexus
```

#### Check Metrics

```bash
# View latest metrics
curl http://localhost:8000/api/v1/metrics | grep sds_nexus

# Check specific metric
curl http://localhost:9090/api/v1/query?query=sds_nexus_http_requests_total
```

### Backup & Recovery

#### Manual Backup

```bash
# Run backup script
/usr/local/bin/backup_database.sh

# Or manually:
# Docker Compose
docker-compose exec postgres pg_dump -U sds_nexus_user sds_nexus > backup_$(date +%Y%m%d).sql

# Systemd
sudo -u postgres pg_dump sds_nexus > /var/sds-nexus/backups/backup_$(date +%Y%m%d).sql
```

#### Restore Database

```bash
# Stop API first
sudo systemctl stop sds-nexus-api

# Restore
sudo -u postgres psql sds_nexus < /var/sds-nexus/backups/backup_20240115.sql

# Restart API
sudo systemctl start sds-nexus-api
```

### Scaling

#### Docker Compose

```bash
# Scale API workers
docker-compose up -d --scale api=3
```

#### Kubernetes

```bash
# Manual scaling
kubectl scale deployment sds-nexus-api --replicas=5 -n sds-nexus

# Auto-scaling is already configured via HPA
kubectl get hpa -n sds-nexus
```

### Updates & Rollouts

#### Docker Compose

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d

# Run migrations if needed
docker-compose exec api alembic upgrade head
```

#### Systemd

```bash
# Pull latest changes
cd /opt/sds-nexus
sudo -u sds-nexus git pull

# Install dependencies
sudo -u sds-nexus bash -c "source venv/bin/activate && pip install -r requirements.txt"

# Run migrations
sudo -u sds-nexus bash -c "cd /opt/sds-nexus && source venv/bin/activate && alembic upgrade head"

# Restart service
sudo systemctl restart sds-nexus-api
```

#### Kubernetes

```bash
# Build new image
docker build -t sds-nexus:v1.1.0 -f docker/Dockerfile .

# Update deployment (rolling update)
kubectl set image deployment/sds-nexus-api api=sds-nexus:v1.1.0 -n sds-nexus

# Watch rollout
kubectl rollout status deployment/sds-nexus-api -n sds-nexus

# Rollback if needed
kubectl rollout undo deployment/sds-nexus-api -n sds-nexus
```

### Maintenance Windows

#### Create Maintenance Window

```python
from datetime import datetime, timedelta
from app.core.maintenance import create_maintenance_window, MaintenanceType
from app.db.session import get_db

db = next(get_db())
window = create_maintenance_window(
    cluster_id=1,
    start_time=datetime.utcnow(),
    end_time=datetime.utcnow() + timedelta(hours=4),
    reason="Scheduled OSD upgrades",
    maintenance_type=MaintenanceType.SCHEDULED,
    created_by="ops-team",
    suppress_alert_sources="osd,node",
    db=db,
)
print(f"Created maintenance window ID: {window.id}")
```

---

## Documentation Reference

### Quick Guides
- **[START_HERE.md](START_HERE.md)** - Quick overview
- **[QUICK_START.md](QUICK_START.md)** - Fast deployment
- **[k8s/QUICK_START_K8S.md](k8s/QUICK_START_K8S.md)** - Kubernetes deployment

### Detailed Guides
- **[PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)** - Production VMs (detailed)
- **[KUBERNETES_INTEGRATION.md](KUBERNETES_INTEGRATION.md)** - Kubernetes (comprehensive)
- **[docs/IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** - Legacy guide

### Operational Documentation
- **[docs/OPERATIONAL_RUNBOOK.md](docs/OPERATIONAL_RUNBOOK.md)** - Daily operations
- **[docs/MONITORING_INTEGRATION.md](docs/MONITORING_INTEGRATION.md)** - External integrations
- **[docs/TENANT_CHARGEBACK_DASHBOARD.md](docs/TENANT_CHARGEBACK_DASHBOARD.md)** - Dashboard guide

### Reference
- **[README.md](README.md)** - Project overview
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Verification checklist
- **[OPERATIONAL_COMPLETENESS_CHECKLIST.md](OPERATIONAL_COMPLETENESS_CHECKLIST.md)** - Readiness assessment

---

## Support & Resources

### Quick Commands

```bash
# Health check
curl http://localhost:8000/api/v1/health/live

# View logs
sudo journalctl -u sds-nexus-api -f

# Check status
sudo systemctl status sds-nexus-api

# Restart service
sudo systemctl restart sds-nexus-api

# Run backup
/usr/local/bin/backup_database.sh

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq
```

### Getting Help

1. Check troubleshooting section (above)
2. Review logs for errors
3. Check GitHub issues: https://github.com/Dinesh1496/SDS/issues
4. Consult operational runbook: `docs/OPERATIONAL_RUNBOOK.md`

---

## Deployment Comparison

| Feature | Docker Compose | Production VMs | K8s (Docker Desktop) | K8s (Production) |
|---------|----------------|----------------|----------------------|------------------|
| **Setup Time** | 10 min | 2-3 hrs | 20 min | 1-2 hrs |
| **Complexity** | Easy | Medium | Easy | Medium |
| **HA** | No | No | Yes (2+ pods) | Yes (2+ pods) |
| **Auto-Scale** | No | No | Yes (2-10) | Yes (configurable) |
| **Auto-Heal** | Restart only | Systemd restart | Yes | Yes |
| **Load Balance** | No | No | Yes | Yes |
| **Rolling Updates** | No | Manual | Yes | Yes |
| **Best For** | Dev/Test | Production VMs | Learning/Dev | Production K8s |

---

**Version:** 1.0.0  
**Last Updated:** January 2024  
**Platform:** SDS Nexus  
**Status:** Production Ready ✅

