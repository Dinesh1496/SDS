# SDS Nexus Platform — Production Implementation Guide

**Version:** 1.0.0  
**Environment:** SDS Nexus Ceph Object Storage  
**Target OS:** Red Hat Enterprise Linux 10 (RHEL 10)  
**Auth Model:** Read-Only Local Account (locally created in SDS Nexus)  
**Monitoring:** Prometheus + Grafana  
**Classification:** Internal — Storage Operations Team

---

## Table of Contents

1. [Pre-Implementation Checklist & RHEL 10 Server Requirements](#1-pre-implementation-checklist)
   - 1.1 RHEL 10 Server Requirements
   - 1.2 Network Connectivity Requirements
   - 1.3 RHEL 10 Firewall Configuration
   - 1.4 RHEL 10 SELinux Configuration
   - 1.5 Subscription and Repository Setup
   - 1.6 Software Installation on RHEL 10
   - 1.7 lm_sensors Configuration
   - 1.8 NTP / Chrony Configuration
   - 1.9 Python Virtual Environment Setup
   - 1.10 Directory Structure
   - 1.11 Pre-Implementation Checklist Summary
2. [Read-Only Account Setup (SDS Nexus)](#2-read-only-account-setup-sds-nexus)
3. [Module 1 — Cluster Health Monitoring](#3-module-1--cluster-health-monitoring)
4. [Module 2 — Node Monitoring](#4-module-2--node-monitoring)
5. [Module 3 — Object Storage Monitoring](#5-module-3--object-storage-monitoring)
6. [Module 4 — Reporting](#6-module-4--reporting)
7. [Module 5 — Chargeback](#7-module-5--chargeback)
8. [Module 6 — Dashboard](#8-module-6--dashboard)
9. [Database Setup & Migrations](#9-database-setup--migrations)
10. [Scheduler & Worker Setup](#10-scheduler--worker-setup)
11. [Prometheus & Grafana Monitoring Setup](#11-prometheus--grafana-monitoring-setup)
    - 11.1 Prometheus Installation & Configuration
    - 11.2 Grafana Installation & Configuration
    - 11.3 Alert Manager Configuration
    - 11.4 Dashboard Import & Configuration
12. [Multi-Environment Configuration Management](#12-multi-environment-configuration-management)
    - 12.1 Environment-Specific Configuration Files
    - 12.2 Environment Variable Management
    - 12.3 Switching Between Environments
13. [Maintenance Windows & Alert Suppression](#13-maintenance-windows--alert-suppression)
    - 13.1 Creating Maintenance Windows
    - 13.2 Alert Suppression Rules
    - 13.3 Maintenance Window API
14. [Docker Production Deployment](#14-docker-production-deployment)
15. [Systemd Timer Setup](#15-systemd-timer-setup)
16. [Environment Variable Reference](#16-environment-variable-reference)
17. [Security Hardening Checklist](#17-security-hardening-checklist)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. Pre-Implementation Checklist

Complete every item before starting module implementation.

---

### 1.1 RHEL 10 Server Requirements

#### Platform Server (runs the Python application)

This is the dedicated server that hosts the SDS Nexus platform application,
FastAPI API, APScheduler workers, and connects outbound to Ceph and PostgreSQL.

**Hardware — Minimum (small cluster, < 50 OSDs)**

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 4 vCPU / physical cores | 8 vCPU |
| RAM | 8 GB | 16 GB |
| OS Disk | 50 GB SSD | 100 GB SSD |
| Data Disk | 100 GB (reports + logs) | 500 GB |
| NIC | 1 × 1 GbE | 1 × 10 GbE |

**Hardware — Production (large cluster, 50–500+ OSDs)**

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 8 vCPU | 16 vCPU |
| RAM | 16 GB | 32 GB |
| OS Disk | 100 GB SSD | 200 GB SSD |
| Data Disk | 500 GB SSD | 1 TB SSD (RAID 1) |
| NIC | 1 × 10 GbE | 2 × 10 GbE (bonded) |

> **Note:** The platform server does not store Ceph data. Disk sizing is driven
> by accumulated report files, log rotation, and the PostgreSQL database if
> co-located. For large deployments put PostgreSQL on a separate server.

---

#### PostgreSQL Server (dedicated — recommended for production)

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 4 vCPU | 8 vCPU |
| RAM | 8 GB | 16 GB |
| OS Disk | 50 GB SSD | 100 GB SSD |
| DB Disk | 100 GB SSD | 500 GB SSD (separate mount) |
| NIC | 1 × 1 GbE | 1 × 10 GbE |

> For small / lab deployments PostgreSQL can be co-located on the platform server.
> In that case add the PostgreSQL RAM and disk figures to the platform server spec.

---

#### Operating System

| Item | Requirement |
|---|---|
| Distribution | Red Hat Enterprise Linux 10 (RHEL 10) |
| Architecture | x86_64 or aarch64 |
| Subscription | Active RHEL subscription OR Red Hat Developer account |
| Installation type | Minimal Install + Standard (no GUI required) |
| SELinux | Enforcing (do not disable — configure correctly) |
| Firewalld | Enabled (configure rules below) |
| FIPS mode | Optional — compatible if FIPS is required by your security policy |

---

#### RHEL 10 Specific Notes

RHEL 10 ships with Python 3.12 in AppStream and uses `dnf5` as the
default package manager (replaces `dnf` from RHEL 9). The commands below
account for both `dnf5` and legacy `dnf` syntax.

RHEL 10 also enforces stricter default crypto policies. The `sds-monitor`
SSH key must use ED25519 or RSA-4096 — RSA-2048 is deprecated in RHEL 10's
`DEFAULT` crypto policy.

---

### 1.2 OSNexus QuantaStor Cluster Architecture

This platform is managed via **OSNexus QuantaStor Manager**. The cluster
`ue-south-1` is confirmed visible in the GUI with the following live state.

#### 1.2a Confirmed Cluster Inventory (from GUI screenshot)

| Component | Count | Status | GUI Tab |
|---|---|---|---|
| **Cluster name** | `ue-south-1` | -- | Scale-out Storage Clusters |
| **Storage nodes** | 12 | Active | Left panel: `dbr-gbch-sds01` to `dbr-gbch-sds12` |
| **OSDs** | 287 / 287 up | HEALTH_OK | Cluster Dashboard |
| **MONs in quorum** | 7 / 7 | All healthy | Cluster Dashboard > Cluster Monitors tab |
| **Object Gateways** | 9 / 12 active | Normal | Cluster Dashboard > Object Gateways tab |
| **Load Balancers** | 12 / 12 | All up | Cluster Dashboard > Load Balancer tab |
| **Metadata Servers** | 0 / 0 | N/A (CephFS not used) | Cluster Dashboard |
| **Storage pools** | 7 / 7 | Online | Cluster Dashboard |
| **Capacity used** | 179.88 TB (3.41%) | -- | Cluster Storage Capacity donut |
| **Capacity free** | 509 TB (96.59%) | -- | Cluster Storage Capacity donut |

> **Note on Object Gateways:** 9 out of 12 active is normal in QuantaStor.
> RGW daemons are co-located on storage nodes and not all nodes run one.
> The Load Balancer only routes to the 9 active gateways automatically.

---

#### 1.2b Corrected Traffic Flow Architecture

You are correct that the **Load Balancer sits in front of the Object Gateways**.
In QuantaStor, the Load Balancer is a **reverse proxy / VIP** that receives all
incoming S3 client traffic and distributes it across the active RGW daemons.

The correct traffic path is:

```
S3 Client (or this platform) --> Load Balancer VIP --> Object Gateway (RGW) --> Storage Nodes
```

NOT the other way around. The Load Balancer is the entry point, not the Gateway.

```
+------------------------------------------------------------------+
|        OSNexus QuantaStor -- Cluster: ue-south-1                 |
|                                                                   |
|  +------------------------------------------------------------+  |
|  | LOAD BALANCERS (12/12) -- S3 CLIENT ENTRY POINT            |  |
|  |                                                             |  |
|  | QuantaStor built-in reverse proxy / VIP                    |  |
|  | Receives ALL S3 and Admin API traffic first                 |  |
|  | <-- Set RGW_ENDPOINT and RGW_ADMIN_ENDPOINT to this VIP --> |  |
|  +-----------------------------+------------------------------+  |
|                                | distributes to active gateways  |
|  +-----------------------------v------------------------------+  |
|  | OBJECT GATEWAYS (9/12 active)                              |  |
|  |                                                             |  |
|  | Ceph RGW daemons co-located on storage nodes               |  |
|  | Serve S3/Swift API, talk to RADOS for data                 |  |
|  | <-- Never configure individual gateway IPs in .env -->     |  |
|  +-----------------------------+------------------------------+  |
|                                | Ceph RADOS internal protocol    |
|  +-----------------------------v------------------------------+  |
|  | STORAGE NODES (12 nodes: dbr-gbch-sds01 to dbr-gbch-sds12)|  |
|  |                                                             |  |
|  |  dbr-gbch-sds01  -- MON + admin node (verify below)       |  |
|  |  dbr-gbch-sds02  -- MON                                   |  |
|  |  dbr-gbch-sds03  -- MON   (7 MONs across 12 nodes)        |  |
|  |  dbr-gbch-sds04  -- MON                                   |  |
|  |  dbr-gbch-sds05  -- MON                                   |  |
|  |  dbr-gbch-sds06  -- MON                                   |  |
|  |  dbr-gbch-sds07  -- MON                                   |  |
|  |  dbr-gbch-sds08  -- OSD  (287 OSDs / 12 nodes = ~24/node) |  |
|  |  dbr-gbch-sds09  -- OSD                                   |  |
|  |  dbr-gbch-sds10  -- OSD                                   |  |
|  |  dbr-gbch-sds11  -- OSD                                   |  |
|  |  dbr-gbch-sds12  -- OSD                                   |  |
|  +----------------------------^--------------------------------+  |
|                               | SSH port 22 (direct)             |
+-------------------------------|---------------------------------+
                                |
+-------------------------------+---------------------------------+
|         SDS NEXUS MONITORING PLATFORM (RHEL 10)                 |
|                                                                   |
|  Modules 1+2 -- SSH ---------> Nodes dbr-gbch-sds01..sds12      |
|  Module 3    -- HTTP/S3 -----> Load Balancer VIP (entry point)   |
|  All modules -- SQL ---------> PostgreSQL                        |
+-----------------------------------------------------------------+
```

**Step-by-step for each traffic type:**

| Step | Traffic | Path | Who handles |
|---|---|---|---|
| 1 | S3/API request | Platform --> **Load Balancer VIP** | LB receives |
| 2 | LB forwards | LB --> **active Object Gateway (RGW)** | LB picks 1 of 9 |
| 3 | Gateway reads/writes data | Gateway --> **Storage Nodes** (RADOS) | Internal Ceph |
| 4 | SSH monitoring | Platform --> **Storage Nodes directly** | Bypasses LB + Gateway |

---

#### 1.2c Connection Rules -- Critical

| Traffic Type | Connect To | Do NOT Use | Module |
|---|---|---|---|
| S3 API (ListBuckets, GetObject etc.) | **Load Balancer VIP** | Individual Gateway IPs or Node IPs | 3 |
| RGW Admin API (/admin/user, /admin/bucket) | **Load Balancer VIP** | Individual Gateway IPs or Node IPs | 3 |
| SSH Ceph CLI (ceph status, ceph df etc.) | **Node IPs directly** (dbr-gbch-sds01...) | Load Balancer, Object Gateways | 1, 2 |
| Node metrics (/proc, SMART, sensors) | **Each node IP directly** | Load Balancer, Object Gateways | 2 |
| radosgw-admin CLI (user/bucket mgmt) | **Admin node SSH** (e.g. dbr-gbch-sds01) | Load Balancer, Object Gateways | Setup |

---

#### 1.2d Network Port Requirements

**Object storage -- via Load Balancer (client entry point, in front of Gateways)**

| Source | Destination | Port | Protocol | Purpose |
|---|---|---|---|---|
| Platform server | **Load Balancer VIP** | 7480 | TCP | RGW S3 API + Admin API (HTTP) |
| Platform server | **Load Balancer VIP** | 443 | TCP | RGW HTTPS (if TLS configured in QuantaStor) |

> LB forwards these to one of the 9 active Object Gateways automatically.

**SSH -- direct to storage nodes (bypasses LB and Gateway entirely)**

| Source | Destination | Port | Protocol | Purpose |
|---|---|---|---|---|
| Platform server | `dbr-gbch-sds01` (MON / admin) | 22 | TCP | SSH -- ceph CLI, cluster health |
| Platform server | `dbr-gbch-sds02` to `sds07` (MONs) | 22 | TCP | SSH -- MON quorum status |
| Platform server | `dbr-gbch-sds01` to `sds12` (all nodes) | 22 | TCP | SSH -- OSD status, node metrics, SMART |

**Other connections**

| Source | Destination | Port | Protocol | Purpose |
|---|---|---|---|---|
| Platform server | PostgreSQL server | 5432 | TCP | Platform database |
| Platform server | SMTP relay | 587 | TCP | Email reports (STARTTLS) |
| Platform server | NTP server | 123 | UDP | Time sync |
| Admin workstation | Platform server | 443 | TCP | Nginx HTTPS |

---

#### 1.2e Find Your Exact Endpoints in QuantaStor GUI

**Get the Load Balancer VIP (for RGW_ENDPOINT)**

In QuantaStor Manager:
1. Select cluster `ue-south-1`
2. Click the **Load Balancer** tab in the bottom panel
3. Note the **VIP address** and **port** -- this is the S3 client entry point
4. Set this as both `RGW_ENDPOINT` and `RGW_ADMIN_ENDPOINT` in your `.env`

```bash
# Verify from the platform server -- LB should forward to an active gateway
LB_VIP="<VIP from Load Balancer tab>"
curl -si http://${LB_VIP}:7480/ | grep -i "Server:"
# Expected: Server: Ceph Object Gateway
# (This confirms LB --> Gateway --> Node path is working end to end)
```

**Get node hostnames and IPs (for SSH config)**

In QuantaStor Manager:
1. Select cluster `ue-south-1`
2. Click **Cluster Members** tab in the bottom panel
3. Note the **hostname** and **management IP** for each of the 12 nodes
4. Node naming pattern: `dbr-gbch-sds01` through `dbr-gbch-sds12`

```bash
# Test SSH access to all 12 nodes (after Section 2 account setup)
for N in $(seq -w 1 12); do
    HOST="dbr-gbch-sds${N}"
    echo -n "  ${HOST}: "
    ssh -i /etc/sds-nexus/keys/sds_monitor_ed25519 \
        -o ConnectTimeout=5 \
        -o BatchMode=yes \
        sds-monitor@${HOST} "hostname" 2>/dev/null && echo "OK" || echo "FAILED"
done
```

**Identify the admin node (for ceph CLI)**

In QuantaStor Manager:
1. Click **Cluster Monitors** tab
2. The first listed MON (typically `dbr-gbch-sds01`) is the admin node
3. Confirm by checking for the admin keyring on that node

```bash
for N in 01 02 03; do
    HOST="dbr-gbch-sds${N}"
    echo -n "  ${HOST} admin keyring: "
    ssh -i /etc/sds-nexus/keys/sds_monitor_ed25519 \
        sds-monitor@${HOST} \
        "test -f /etc/ceph/ceph.client.admin.keyring && echo FOUND || echo absent" \
        2>/dev/null
done
```

**Record your confirmed .env values**

```bash
# Set these in /etc/sds-nexus/production.env after completing the steps above:

CEPH_CLUSTER_NAME=ue-south-1
CEPH_CLUSTER_DISPLAY_NAME="QuantaStor Cluster ue-south-1"
CEPH_ADMIN_NODE=dbr-gbch-sds01          # Update if keyring found on different node
CEPH_MONITOR_HOST=dbr-gbch-sds01        # First MON node
CEPH_SSH_USER=sds-monitor

# Load Balancer VIP -- entry point in front of Object Gateways
RGW_ENDPOINT=http://<LB-VIP>:7480
RGW_ADMIN_ENDPOINT=http://<LB-VIP>:7480/admin
# LB routes automatically to 9 active Object Gateways -- no gateway IPs needed
```

---

### 1.3 RHEL 10 Firewall Configuration

```bash
# On the PLATFORM SERVER — allow inbound API access
# (Nginx proxies 443 → 8000; 8000 should only be locally accessible)

sudo firewall-cmd --permanent --add-service=https          # 443 — Nginx
sudo firewall-cmd --permanent --add-service=http           # 80 — redirect to 443
sudo firewall-cmd --permanent --add-port=8000/tcp          # API (restrict to mgmt net)
sudo firewall-cmd --permanent --add-service=postgresql     # 5432 — if DB co-located
sudo firewall-cmd --reload

# Restrict API port to management network only (replace with your CIDR)
sudo firewall-cmd --permanent --zone=public \
    --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" \
    port port="8000" protocol="tcp" accept'

# Verify
sudo firewall-cmd --list-all
```

---

### 1.4 RHEL 10 SELinux Configuration

Do not disable SELinux. Configure it correctly for the application.

```bash
# Verify SELinux is enforcing
getenforce
# Expected: Enforcing

# Allow the application to bind to port 8000
sudo semanage port -a -t http_port_t -p tcp 8000

# Allow outbound SSH connections from the app (for Paramiko)
sudo setsebool -P nis_enabled 1

# Allow the sds-nexus user to write to /var/sds-nexus
sudo semanage fcontext -a -t var_t "/var/sds-nexus(/.*)?"
sudo restorecon -Rv /var/sds-nexus

# Allow writing to /var/log/sds-nexus
sudo semanage fcontext -a -t var_log_t "/var/log/sds-nexus(/.*)?"
sudo restorecon -Rv /var/log/sds-nexus

# Allow Nginx to proxy to port 8000
sudo setsebool -P httpd_can_network_connect 1

# Verify no AVC denials after first run
sudo ausearch -c 'python3' --raw | audit2allow -M sds-nexus-policy
# Review output — apply only if the denials are expected
```

---

### 1.5 RHEL 10 Subscription and Repository Setup

```bash
# Register with Red Hat (if not already registered)
sudo subscription-manager register \
    --username=your-redhat-username \
    --password=your-redhat-password \
    --auto-attach

# Verify subscription is attached
sudo subscription-manager status

# Enable required repositories
sudo subscription-manager repos \
    --enable=rhel-10-for-x86_64-baseos-rpms \
    --enable=rhel-10-for-x86_64-appstream-rpms

# Update all packages to latest
sudo dnf5 update -y

# Verify RHEL 10 version
cat /etc/redhat-release
# Expected: Red Hat Enterprise Linux release 10.x
```

---

### 1.6 Software Installation on RHEL 10

```bash
# Install Python 3.12 and build dependencies
# Note: RHEL 10 AppStream ships Python 3.12 as the default stream
sudo dnf5 install -y \
    python3.12 \
    python3.12-pip \
    python3.12-devel \
    python3-setuptools \
    python3-wheel

# Install PostgreSQL client libraries (for psycopg2 compilation)
sudo dnf5 install -y \
    postgresql \
    postgresql-devel \
    libpq-devel

# Install build tools and SSL libraries
sudo dnf5 install -y \
    gcc \
    gcc-c++ \
    make \
    openssl \
    openssl-devel \
    libffi-devel \
    zlib-devel \
    bzip2-devel \
    readline-devel \
    sqlite-devel

# Install system utilities
sudo dnf5 install -y \
    git \
    curl \
    wget \
    vim \
    tmux \
    net-tools \
    bind-utils \
    lsof \
    htop \
    smartmontools \
    lm_sensors \
    policycoreutils-python-utils  # For semanage

# Install Nginx (for reverse proxy)
sudo dnf5 install -y nginx
sudo systemctl enable nginx

# Install PostgreSQL 16 server (if co-locating DB on platform server)
# Skip this block if using a dedicated PostgreSQL server
sudo dnf5 module enable postgresql:16 -y
sudo dnf5 install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql

# Verify Python version
python3.12 --version
# Expected: Python 3.12.x

# Verify pip
python3.12 -m pip --version
```

---

### 1.7 Configure lm_sensors (for node temperature monitoring)

This runs on each **Ceph node** that the `sds-monitor` user will connect to,
not on the platform server.

```bash
# On each Ceph node — detect and configure sensors
sudo sensors-detect --auto
sudo systemctl enable --now lm_sensors

# Test sensors output (should show CPU temperatures)
sensors -j

# If sensors returns empty — check kernel modules loaded
lsmod | grep -i thermal
lsmod | grep -i coretemp
# Load manually if missing:
sudo modprobe coretemp
# Add to /etc/modules-load.d/ for persistence:
echo "coretemp" | sudo tee /etc/modules-load.d/coretemp.conf
```

---

### 1.8 NTP / Chrony Configuration

Time synchronisation is critical — Ceph requires all nodes to be within 0.5s
of each other. The platform server must also be time-synchronised for accurate
report timestamps and chargeback calculations.

```bash
# RHEL 10 uses chrony by default
sudo systemctl status chronyd

# Verify time sync status
chronyc tracking
chronyc sources -v

# If not synced — configure NTP servers (replace with your internal NTP)
sudo tee /etc/chrony.conf << 'EOF'
# Use your internal NTP servers
server ntp1.internal.company.com iburst prefer
server ntp2.internal.company.com iburst
server ntp3.internal.company.com iburst

# Allow NTP client access from local network
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
logdir /var/log/chrony
EOF

sudo systemctl restart chronyd
chronyc tracking
# Verify "System time" offset is < 10ms
```

---

### 1.9 Python Virtual Environment Setup

```bash
# Create virtual environment for the application
sudo -u sds-nexus python3.12 -m venv /opt/sds-nexus/venv

# Verify
/opt/sds-nexus/venv/bin/python --version
# Expected: Python 3.12.x

# Upgrade pip inside venv
sudo -u sds-nexus /opt/sds-nexus/venv/bin/pip install --upgrade pip setuptools wheel

# Install application dependencies
cd /opt/sds-nexus
sudo -u sds-nexus /opt/sds-nexus/venv/bin/pip install -r requirements.txt

# Verify key packages installed
sudo -u sds-nexus /opt/sds-nexus/venv/bin/pip list | grep -E \
    "fastapi|sqlalchemy|paramiko|boto3|loguru|openpyxl|pandas"
```

---

### 1.10 Directory Structure

```bash
# Application directories
sudo mkdir -p /opt/sds-nexus                  # Application root
sudo mkdir -p /opt/sds-nexus/venv             # Python virtual environment
sudo mkdir -p /opt/sds-nexus/logs             # Symlink to /var/log/sds-nexus

# Data directories
sudo mkdir -p /var/sds-nexus/reports          # Generated Excel/PDF reports
sudo mkdir -p /var/sds-nexus/reports/monthly  # Monthly report archive
sudo mkdir -p /var/sds-nexus/reports/daily    # Daily report archive
sudo mkdir -p /var/sds-nexus/data             # Persistent application data
sudo mkdir -p /var/sds-nexus/backups          # Database backups
sudo mkdir -p /var/sds-nexus/charts           # Temporary chart PNG files

# Log directory
sudo mkdir -p /var/log/sds-nexus

# Configuration and secrets
sudo mkdir -p /etc/sds-nexus                  # Configuration root
sudo mkdir -p /etc/sds-nexus/keys             # SSH private keys (mode 700)

# Temp files
sudo mkdir -p /tmp/sds-nexus

# Create dedicated system user (no login shell)
sudo useradd \
    --system \
    --shell /sbin/nologin \
    --home-dir /opt/sds-nexus \
    --no-create-home \
    --comment "SDS Nexus Platform Service Account" \
    sds-nexus

# Assign ownership
sudo chown -R sds-nexus:sds-nexus /opt/sds-nexus
sudo chown -R sds-nexus:sds-nexus /var/sds-nexus
sudo chown -R sds-nexus:sds-nexus /var/log/sds-nexus
sudo chown -R root:sds-nexus /etc/sds-nexus
sudo chmod 750 /etc/sds-nexus
sudo chmod 700 /etc/sds-nexus/keys

# Verify
ls -la /opt/sds-nexus
ls -la /var/sds-nexus
ls -la /etc/sds-nexus
```

---

### 1.11 Pre-Implementation Checklist Summary

Tick every item before starting Module 1 implementation.

**Server**
- [ ] RHEL 10 installed, registered, and fully updated (`dnf5 update`)
- [ ] Active Red Hat subscription confirmed (`subscription-manager status`)
- [ ] Hardware meets minimum spec for your cluster size (Section 1.1)
- [ ] Chrony is synchronised — offset < 10ms (`chronyc tracking`)
- [ ] SELinux in Enforcing mode (`getenforce`)
- [ ] Firewall rules applied (`firewall-cmd --list-all`)

**Software**
- [ ] Python 3.12.x installed (`python3.12 --version`)
- [ ] Virtual environment created at `/opt/sds-nexus/venv`
- [ ] All `requirements.txt` packages installed without errors
- [ ] `smartmontools` installed on all Ceph nodes
- [ ] `lm_sensors` configured and returning temperature data on Ceph nodes

**Database**
- [ ] PostgreSQL 16 installed and running
- [ ] `sds_nexus` database created
- [ ] `sds_nexus_user` created with correct permissions
- [ ] Connection from platform server to PostgreSQL verified

**Networking**
- [ ] Platform server can SSH to all Ceph nodes on port 22
- [ ] Platform server can reach RGW on port 7480
- [ ] Platform server can reach SMTP server on port 587
- [ ] All firewall and SELinux rules applied

**Secrets**
- [ ] `/etc/sds-nexus/production.env` created with mode `600`
- [ ] SSH private key at `/etc/sds-nexus/keys/sds_monitor_ed25519` with mode `600`
- [ ] Both files owned by `sds-nexus:sds-nexus`

---

## 2. Read-Only Account Setup (SDS Nexus)

This platform uses a **locally created read-only account** in SDS Nexus for all
Ceph CLI and RGW API access. This is a security best practice — the platform
never requires write access to the storage cluster.

### 2.1 Create Read-Only SSH User on Ceph Nodes

Run these commands on **each Ceph node** (MON, OSD, RGW, MGR nodes):

```bash
# Create the local read-only account
sudo useradd --system --shell /bin/bash \
    --comment "SDS Nexus Monitoring - Read Only" \
    --create-home sds-monitor

# Lock the password (SSH key only — no password login)
sudo passwd -l sds-monitor

# Create .ssh directory
sudo mkdir -p /home/sds-monitor/.ssh
sudo chmod 700 /home/sds-monitor/.ssh
sudo chown sds-monitor:sds-monitor /home/sds-monitor/.ssh
```

### 2.2 Grant Ceph Read-Only Permissions

```bash
# On the Ceph admin node — grant read-only caps to the monitor user
# This creates a Ceph auth key for the monitoring account
sudo ceph auth get-or-create client.sds-monitor \
    mon 'allow r' \
    osd 'allow r' \
    mds 'allow r' \
    mgr 'allow r' \
    > /tmp/ceph.client.sds-monitor.keyring

# Verify the keyring was created
sudo ceph auth get client.sds-monitor

# Deploy keyring to all nodes that will run ceph CLI
sudo cp /tmp/ceph.client.sds-monitor.keyring \
    /etc/ceph/ceph.client.sds-monitor.keyring
sudo chmod 640 /etc/ceph/ceph.client.sds-monitor.keyring
sudo chown root:sds-monitor /etc/ceph/ceph.client.sds-monitor.keyring
```

### 2.3 Configure sudo for Read-Only Ceph Commands

Create a sudoers file that allows `sds-monitor` to run ONLY read-only
Ceph commands without a password:

```bash
sudo tee /etc/sudoers.d/sds-nexus-monitor << 'EOF'
# SDS Nexus Platform - Read-Only Monitoring Account
# IMPORTANT: Only allows read-only Ceph CLI commands

# Ceph cluster status commands (read-only)
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph status
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph health *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph df *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph osd df *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph osd tree *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph osd stat *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph osd dump *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph mon stat *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph mon dump *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph mgr stat *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph mgr dump *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph pg stat *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/ceph pg dump *

# Node metrics (read-only system commands)
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/smartctl -a *
sds-monitor ALL=(ALL) NOPASSWD: /usr/bin/sensors *
sds-monitor ALL=(ALL) NOPASSWD: /bin/cat /proc/meminfo
sds-monitor ALL=(ALL) NOPASSWD: /bin/cat /proc/cpuinfo
sds-monitor ALL=(ALL) NOPASSWD: /bin/cat /proc/loadavg
sds-monitor ALL=(ALL) NOPASSWD: /bin/df -h

# Explicitly DENY all write/modify commands
sds-monitor ALL=(ALL) !SETENV: /usr/bin/ceph osd set *
sds-monitor ALL=(ALL) !SETENV: /usr/bin/ceph osd unset *
sds-monitor ALL=(ALL) !SETENV: /usr/bin/ceph osd rm *
sds-monitor ALL=(ALL) !SETENV: /usr/bin/ceph auth del *
EOF

# Validate sudoers syntax
sudo visudo -c -f /etc/sudoers.d/sds-nexus-monitor
```

### 2.4 Generate SSH Key for Platform Server

Run on the **platform server** (not Ceph nodes):

```bash
# Generate ED25519 key (more secure than RSA for new deployments)
sudo -u sds-nexus ssh-keygen \
    -t ed25519 \
    -f /etc/sds-nexus/keys/sds_monitor_ed25519 \
    -C "sds-nexus-platform@$(hostname)-$(date +%Y%m%d)" \
    -N ""   # No passphrase for automated use

# Set strict permissions
sudo chmod 600 /etc/sds-nexus/keys/sds_monitor_ed25519
sudo chmod 644 /etc/sds-nexus/keys/sds_monitor_ed25519.pub
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/keys/sds_monitor_ed25519*

# Display public key to copy to Ceph nodes
cat /etc/sds-nexus/keys/sds_monitor_ed25519.pub
```

### 2.5 Distribute SSH Public Key to All Ceph Nodes

> **Topology note:** SSH keys go to the **12 storage nodes** only
> (`dbr-gbch-sds01` through `dbr-gbch-sds12`). Do **not** add the key
> to Object Gateway nodes or Load Balancers — those are not accessed
> via SSH by this platform.

```bash
# All 12 nodes confirmed from the QuantaStor GUI (ue-south-1)
# Adjust if your DNS uses IPs instead of hostnames
CEPH_NODES=(
    "dbr-gbch-sds01"   # MON / Admin node (check Cluster Monitors tab)
    "dbr-gbch-sds02"   # MON
    "dbr-gbch-sds03"   # MON
    "dbr-gbch-sds04"   # MON
    "dbr-gbch-sds05"   # MON
    "dbr-gbch-sds06"   # MON
    "dbr-gbch-sds07"   # MON  (7 MONs — from Cluster Monitors tab)
    "dbr-gbch-sds08"   # OSD node
    "dbr-gbch-sds09"   # OSD node
    "dbr-gbch-sds10"   # OSD node
    "dbr-gbch-sds11"   # OSD node
    "dbr-gbch-sds12"   # OSD node
)

echo "Deploying SSH key to all 12 QuantaStor nodes (ue-south-1)..."
for CEPH_NODE in "${CEPH_NODES[@]}"; do
    echo -n "  ${CEPH_NODE}: "
    ssh-copy-id \
        -i /etc/sds-nexus/keys/sds_monitor_ed25519.pub \
        -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=10 \
        sds-monitor@${CEPH_NODE} \
        && echo "OK" || echo "FAILED — check sds-monitor user exists on this node"
done

echo ""
echo "Verifying Ceph CLI access via admin node (dbr-gbch-sds01)..."
ssh -i /etc/sds-nexus/keys/sds_monitor_ed25519 \
    sds-monitor@dbr-gbch-sds01 \
    "sudo /usr/bin/ceph status --format json" \
    | python3 -m json.tool | grep -E '"status"|"num_osds"|"num_mons"'
# Expected output (matching QuantaStor GUI dashboard):
#   "status": "HEALTH_OK"
#   "num_osds": 287
#   "num_mons": 7
```

### 2.6 Create Read-Only RGW Admin API User in SDS Nexus

The `radosgw-admin` command manages RGW users. It must run on the **Ceph
admin node** (one of the Nodes you see in the GUI) — not on the Gateway
node and not on the Load Balancer. The user account it creates is stored
in the Ceph cluster's RADOS backend and is then accessible through all
Gateway nodes via the Load Balancer.

```
Architecture reminder for this step:
  Run command on: Node (Ceph admin node) — via SSH
  User is stored in: Ceph RADOS (replicated across all Nodes)
  User is accessible via: Gateway → Load Balancer VIP (HTTP API)
```

```bash
# SSH to the Ceph ADMIN NODE (a Node in the GUI — not the Gateway/LB)
ssh -i /etc/sds-nexus/keys/sds_monitor_ed25519 \
    sds-monitor@<admin-node-ip>

# Create the read-only RGW user
# This is a LOCAL account within SDS Nexus RGW, not a Linux system user
sudo radosgw-admin user create \
    --uid="sds-nexus-monitor" \
    --display-name="SDS Nexus Monitor (Read-Only)" \
    --email="sds-monitor@internal" \
    --max-buckets=0 \
    --suspended=false

# Get the generated access key and secret
sudo radosgw-admin user info --uid="sds-nexus-monitor"
# Note: copy the access_key and secret_key values — they go into .env

# Grant read-only admin caps (info/list only — no write caps)
sudo radosgw-admin caps add \
    --uid="sds-nexus-monitor" \
    --caps="users=read;buckets=read;metadata=read;usage=read;zone=read"

# Verify caps were applied correctly
sudo radosgw-admin user info --uid="sds-nexus-monitor" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['caps'])"
# Expected: [{'type': 'buckets', 'perm': 'read'}, {'type': 'users', 'perm': 'read'}, ...]

# Now verify the user is reachable THROUGH THE LOAD BALANCER
# (This confirms gateway → LB → Ceph data path works end-to-end)
curl -s "http://<Load-Balancer-VIP>:7480/admin/user?uid=sds-nexus-monitor" \
    --header "Authorization: AWS <access_key>:<computed_sig>" \
    | python3 -m json.tool | head -10
# If this returns user data — your Gateway → LB → Node chain is working
```

### 2.7 Update .env with Read-Only Credentials

```bash
# Copy example env file
cp .env.example /etc/sds-nexus/production.env
chmod 600 /etc/sds-nexus/production.env

# Edit and fill in — use the values identified in Section 1.2b:
# CEPH_ADMIN_NODE=<IP of admin node from Nodes section in GUI>
# CEPH_MONITOR_HOST=<IP of MON node from Nodes section in GUI>
# CEPH_SSH_USER=sds-monitor
# CEPH_SSH_KEY_PATH=/etc/sds-nexus/keys/sds_monitor_ed25519
#
# ── RGW: point at the LOAD BALANCER, not individual Gateway nodes ──
# RGW_ENDPOINT=http://<Load-Balancer-VIP>:7480
# RGW_ADMIN_ENDPOINT=http://<Load-Balancer-VIP>:7480/admin
# RGW_ACCESS_KEY=<access_key from radosgw-admin user info>
# RGW_SECRET_KEY=<secret_key from radosgw-admin user info>
# RGW_ADMIN_ACCESS_KEY=<same as RGW_ACCESS_KEY>
# RGW_ADMIN_SECRET_KEY=<same as RGW_SECRET_KEY>
```

### 2.8 Verify Complete Read-Only Access

```bash
# Run the connectivity test script
python scripts/test_connectivity.py

# Expected output:
# [OK] SSH to ceph-admin.internal as sds-monitor
# [OK] ceph status (read-only)
# [OK] ceph df (read-only)
# [OK] RGW admin API /admin/user?list (read-only)
# [OK] PostgreSQL database connection
```

---

## 3. Module 1 — Cluster Health Monitoring

### What It Collects

| Data Point | Ceph Command | Interval |
|---|---|---|
| Cluster health status | `ceph status` | 5 min |
| MON quorum state | `ceph mon stat` | 5 min |
| MGR active/standby | `ceph mgr stat` | 5 min |
| OSD up/in/out/down | `ceph osd tree` | 5 min |
| OSD disk usage | `ceph osd df` | 5 min |
| PG states | `ceph pg stat` | 5 min |
| Capacity (bytes) | `ceph df` | 1 hour |
| Recovery progress | `ceph status` | 5 min |

### Files to Implement

```
app/services/cluster_health/
├── __init__.py
├── collector.py        ← SSH → Ceph CLI → parse → return typed objects
├── health_service.py   ← Orchestrates collection, persists to DB, raises alerts
├── alert_service.py    ← Alert dedup, threshold checks, status transitions
└── schemas.py          ← Internal data transfer objects

app/workers/
└── cluster_monitor.py  ← APScheduler job that calls health_service every 5min

app/api/v1/endpoints/
└── cluster_health.py   ← GET /clusters/{id}/health, GET /clusters/{id}/osds etc.

app/repositories/
└── monitoring.py       ← Alert CRUD, PG snapshot inserts
```

### Implementation Steps

**Step 1 — Implement `collector.py`**

The collector is a pure data-fetching class. It uses the `CephClient` from
`app/utils/ceph_client.py` (already built). It must **never write** to the
cluster — all commands are read-only (`ceph status`, `ceph df`, etc.).

Key methods to implement:
```python
class ClusterHealthCollector:
    def collect_full_status(self, cluster: Cluster) -> ClusterSnapshot
    def collect_capacity(self, cluster: Cluster) -> CapacitySnapshot
    def collect_osd_status(self, cluster: Cluster) -> list[OSDSnapshot]
    def collect_pg_stats(self, cluster: Cluster) -> PGSnapshot
```

The `CephClient.from_cluster()` factory already handles SSH with retry.
Pass `ssh_user=sds-monitor` and `ssh_key_path` from cluster config.

**Step 2 — Implement `health_service.py`**

Orchestrates collection and persistence:
```python
class ClusterHealthService:
    def __init__(self, db: Session, cluster_repo: ClusterRepository,
                 alert_service: AlertService)
    def run_health_check(self, cluster: Cluster) -> HealthCheckResult
    def persist_capacity_snapshot(self, cluster_id: int, snapshot: CapacitySnapshot)
    def persist_osd_states(self, cluster_id: int, osds: list[OSDSnapshot])
    def persist_pg_snapshot(self, cluster_id: int, pg: PGSnapshot)
```

**Step 3 — Implement `alert_service.py`**

Alert logic with deduplication:
```python
class AlertService:
    def check_cluster_health(self, cluster, status) -> list[Alert]
    def check_osd_down(self, cluster, osds) -> list[Alert]
    def check_capacity_thresholds(self, cluster, capacity) -> list[Alert]
    def check_pg_degraded(self, cluster, pgs) -> list[Alert]
    def resolve_cleared_alerts(self, cluster_id, source)
    def deduplicate(self, dedup_key) -> bool   # True = new alert needed
```

**Step 4 — Register APScheduler job in `cluster_monitor.py`**

```python
scheduler.add_job(
    func=run_cluster_health_check,
    trigger="interval",
    seconds=settings.get_monitoring_settings().cluster_health_interval,
    id="cluster_health",
    replace_existing=True,
    misfire_grace_time=60,
)
```

**Step 5 — Add API endpoints**

```
GET  /api/v1/clusters/{id}/health          # Latest health snapshot
GET  /api/v1/clusters/{id}/osds            # All OSD states
GET  /api/v1/clusters/{id}/capacity        # Latest capacity
GET  /api/v1/clusters/{id}/capacity/history # Historical (with ?days=7)
GET  /api/v1/clusters/{id}/pgs             # PG state summary
GET  /api/v1/alerts                        # Active alerts across all clusters
GET  /api/v1/alerts/{id}                   # Single alert detail
PATCH /api/v1/alerts/{id}/acknowledge      # Ack alert (ops/admin only)
PATCH /api/v1/alerts/{id}/resolve          # Resolve alert (ops/admin only)
```

### Read-Only Ceph Commands Used

```bash
# All run as: sudo /usr/bin/ceph <cmd> --format json
# via SSH as sds-monitor user

sudo ceph status --format json
sudo ceph df --format json
sudo ceph osd tree --format json
sudo ceph osd df --format json
sudo ceph osd stat --format json
sudo ceph mon stat --format json
sudo ceph mgr stat --format json
sudo ceph pg stat --format json
sudo ceph health detail --format json
```

### Alert Thresholds (configurable in .env)

```bash
ALERT_OSD_DOWN_THRESHOLD=1          # >= 1 OSD down → WARNING
ALERT_PG_DEGRADED_THRESHOLD=100     # >= 100 degraded PGs → WARNING
ALERT_CAPACITY_WARNING_PERCENT=75   # >= 75% used → WARNING
ALERT_CAPACITY_CRITICAL_PERCENT=85  # >= 85% used → CRITICAL
ALERT_CLUSTER_UNHEALTHY=true        # Any HEALTH_WARN/ERR → alert
```

### Testing Module 1 in Production

```bash
# Manual trigger — run health check for all clusters immediately
python -m app.workers.cluster_monitor --run-once

# Check results in database
psql $DATABASE_URL -c "
  SELECT name, health_status, last_checked_at
  FROM clusters WHERE is_active = true;"

# Check alerts raised
psql $DATABASE_URL -c "
  SELECT title, severity, status, created_at
  FROM alerts ORDER BY created_at DESC LIMIT 20;"

# View capacity snapshots
psql $DATABASE_URL -c "
  SELECT recorded_at, used_gb, total_gb, used_percent
  FROM capacity_history ORDER BY recorded_at DESC LIMIT 5;"
```

---

## 4. Module 2 — Node Monitoring

### What It Collects

| Metric | Method | Command / Source | Interval |
|---|---|---|---|
| CPU usage % | SSH | `top -bn1` or `/proc/stat` | 5 min |
| Load average | SSH | `cat /proc/loadavg` | 5 min |
| Memory usage | SSH | `cat /proc/meminfo` | 5 min |
| Disk usage per mount | SSH | `df -h` | 5 min |
| Disk read/write I/O | SSH | `cat /proc/diskstats` | 5 min |
| Network tx/rx bytes | SSH | `cat /proc/net/dev` | 5 min |
| CPU temperature | SSH | `sudo sensors -j` | 5 min |
| Disk temperature | SSH | `sudo smartctl -a /dev/sdX` | 30 min |
| SMART status | SSH | `sudo smartctl -H /dev/sdX` | 30 min |
| OS / kernel version | SSH | `uname -r` | On discovery |

### Files to Implement

```
app/services/node_monitoring/
├── __init__.py
├── collector.py        ← SSH-based metric collection per node
├── node_service.py     ← Orchestration: collect, persist, alert
├── smart_collector.py  ← SMART disk health (separate — slower interval)
├── parser.py           ← Parse /proc/* output into typed structures
└── schemas.py          ← NodeMetricSnapshot, DiskInfo, NetworkInfo

app/workers/
└── node_monitor.py     ← APScheduler job: 5-min metrics, 30-min SMART

app/api/v1/endpoints/
└── nodes.py            ← REST endpoints for node status and metrics

app/repositories/
└── node.py             ← NodeRepository, NodeMetricRepository
```

### Implementation Steps

**Step 1 — Implement `parser.py`**

All `/proc` parsing lives here, never in the collector or service.
Pure functions, no I/O, fully unit-testable without SSH.

```python
def parse_meminfo(raw: str) -> MemoryInfo
def parse_loadavg(raw: str) -> LoadAverage
def parse_cpu_stat(raw: str) -> CPUStats        # Two reads, 1s apart for %
def parse_proc_net_dev(raw: str) -> dict[str, NetworkStats]
def parse_df_output(raw: str) -> list[DiskMount]
def parse_diskstats(raw: str) -> dict[str, DiskIOStats]
def parse_sensors_json(raw: str) -> SensorData
def parse_smartctl_json(raw: str) -> SMARTResult
```

**Step 2 — Implement `collector.py`**

Uses `SSHClient` (already built). One class per node, context-managed.

```python
class NodeMetricCollector:
    def __init__(self, ssh: SSHClient)
    def collect_all(self) -> NodeMetricSnapshot
    def collect_cpu(self) -> CPUStats
    def collect_memory(self) -> MemoryInfo
    def collect_network(self) -> dict[str, NetworkStats]
    def collect_disk_usage(self) -> list[DiskMount]
    def collect_temperatures(self) -> SensorData
```

**Step 3 — Implement `smart_collector.py`**

SMART is more expensive (one SSH call per disk device). Runs at 30-minute
interval separately from the main 5-minute metric collector.

```python
class SMARTCollector:
    def get_block_devices(self, ssh: SSHClient) -> list[str]
    def collect_smart_for_device(self, ssh: SSHClient, device: str) -> SMARTResult
    def collect_all_disks(self, ssh: SSHClient) -> list[SMARTResult]
    def get_overall_smart_status(self, results: list[SMARTResult]) -> SMARTStatus
```

**Step 4 — Implement `node_service.py`**

```python
class NodeMonitoringService:
    def discover_nodes(self, cluster: Cluster) -> list[Node]  # From osd tree
    def run_node_collection(self, node: Node) -> NodeMetricSnapshot
    def persist_metric_snapshot(self, node_id: int, snapshot: NodeMetricSnapshot)
    def check_alerts(self, node: Node, snapshot: NodeMetricSnapshot) -> list[Alert]
```

**Step 5 — SSH commands used (all read-only)**

```bash
# Run as sds-monitor via SSH

# CPU
cat /proc/stat ; sleep 1 ; cat /proc/stat   # Two reads for delta
cat /proc/loadavg

# Memory
cat /proc/meminfo

# Disk usage
df -PB1 --output=target,size,used,avail,pcent,fstype

# Network
cat /proc/net/dev

# Temperatures (requires sudo per sudoers.d rule)
sudo sensors -j 2>/dev/null || echo '{}'

# SMART (requires sudo per sudoers.d rule)
lsblk -dno NAME,TYPE | grep disk
sudo smartctl -a --json /dev/sda
sudo smartctl -H --json /dev/sdb

# OS info (one-time at discovery)
uname -r
cat /etc/os-release
nproc
grep "model name" /proc/cpuinfo | head -1
```

**Step 6 — Alert thresholds for nodes**

Add to `.env`:
```bash
ALERT_CPU_WARNING_PERCENT=80
ALERT_CPU_CRITICAL_PERCENT=95
ALERT_MEMORY_WARNING_PERCENT=80
ALERT_MEMORY_CRITICAL_PERCENT=90
ALERT_DISK_WARNING_PERCENT=75
ALERT_DISK_CRITICAL_PERCENT=85
ALERT_CPU_TEMP_WARNING_CELSIUS=70
ALERT_CPU_TEMP_CRITICAL_CELSIUS=85
ALERT_DISK_TEMP_WARNING_CELSIUS=45
ALERT_DISK_TEMP_CRITICAL_CELSIUS=55
```

### API Endpoints

```
GET /api/v1/nodes                         # All nodes across all clusters
GET /api/v1/clusters/{id}/nodes           # Nodes for a specific cluster
GET /api/v1/nodes/{id}                    # Single node detail
GET /api/v1/nodes/{id}/metrics            # Latest metric snapshot
GET /api/v1/nodes/{id}/metrics/history    # Historical (with ?hours=24)
GET /api/v1/nodes/{id}/disks              # Disk usage and SMART status
```

### Testing Module 2

```bash
# Test SSH metric collection for one node
python -c "
from app.utils.ssh_client import SSHClient
from app.core.config import get_settings
s = get_settings()
c = s.get_ceph_settings()
with SSHClient(c.admin_node, c.ssh_user, c.ssh_key_path) as ssh:
    result = ssh.run('cat /proc/meminfo')
    print(result.stdout[:500])
"

# Run node collection manually
python -m app.workers.node_monitor --run-once

# Check persisted metrics
psql \$DATABASE_URL -c "
  SELECT n.hostname, nm.cpu_usage_percent, nm.memory_used_percent,
         nm.recorded_at
  FROM node_metrics nm JOIN nodes n ON n.id = nm.node_id
  ORDER BY nm.recorded_at DESC LIMIT 10;"
```

---

## 5. Module 3 — Object Storage Monitoring

### What It Collects

| Data | API Call | Interval |
|---|---|---|
| All tenant/user list | RGW Admin API `GET /admin/metadata/user` | 1 hour |
| Tenant quota & usage | RGW Admin API `GET /admin/user?uid=X` | 1 hour |
| Bucket list per tenant | RGW Admin API `GET /admin/bucket?uid=X` | 1 hour |
| Bucket stats (size/objects) | RGW Admin API `GET /admin/bucket?bucket=X&stats=true` | 1 hour |
| Usage log (ops, bytes) | RGW Admin API `GET /admin/usage` | 1 hour |

### Access Method: RGW Admin API (Read-Only)

All data is collected via the **RadosGW Admin REST API** using the
`sds-nexus-monitor` RGW user created in Section 2.6. This uses signed
HTTP requests (AWS Signature V4) — **no SSH required for object storage**.

The `boto3` library handles request signing. However, the RGW Admin API
requires a custom endpoint — use `requests` + `botocore` auth signing for
admin calls that aren't standard S3 operations.

### Files to Implement

```
app/services/object_storage/
├── __init__.py
├── rgw_admin_client.py   ← Signed HTTP client for RGW Admin REST API
├── s3_client.py          ← Boto3 wrapper for S3 operations (if needed)
├── collector.py          ← Calls rgw_admin_client, returns typed objects
├── storage_service.py    ← Orchestration: collect, persist, detect growth
├── quota_checker.py      ← Quota threshold evaluation and alerts
├── growth_analyser.py    ← Growth rate calculation and trend detection
└── schemas.py            ← TenantData, BucketData, UsageSnapshot

app/workers/
└── storage_monitor.py    ← APScheduler job: hourly collection

app/api/v1/endpoints/
├── tenants.py            ← Tenant usage endpoints
└── buckets.py            ← Bucket detail and history endpoints

app/repositories/
└── storage.py            ← TenantRepository, BucketRepository
```

### Implementation Steps

**Step 1 — Implement `rgw_admin_client.py`**

The RGW Admin API uses AWS Signature V4. Use `requests` + `botocore.auth`
for signing. The `sds-nexus-monitor` RGW user's access/secret key is used.

```python
class RGWAdminClient:
    """
    HTTP client for the Ceph RadosGW Admin REST API.
    
    Uses read-only credentials (sds-nexus-monitor RGW user).
    All methods are read-only — GET requests only.
    """
    def __init__(self, endpoint: str, access_key: str, secret_key: str)
    
    # User/tenant methods
    def list_users(self) -> list[str]
    def get_user(self, uid: str) -> dict
    def get_user_quota(self, uid: str) -> dict
    def get_user_usage(self, uid: str) -> dict
    
    # Bucket methods
    def list_all_buckets(self) -> list[str]
    def list_user_buckets(self, uid: str) -> list[dict]
    def get_bucket_stats(self, bucket_name: str) -> dict
    def get_bucket_policy(self, bucket_name: str) -> dict
    
    # Usage logs
    def get_usage(self, uid: str = None,
                  start: datetime = None, end: datetime = None) -> dict
```

**Step 2 — Implement `collector.py`**

```python
class ObjectStorageCollector:
    def collect_all_tenants(self) -> list[TenantSnapshot]
    def collect_tenant_detail(self, uid: str) -> TenantSnapshot
    def collect_bucket_stats(self, uid: str) -> list[BucketSnapshot]
    def collect_usage_report(self) -> UsageReport
```

**Step 3 — Implement `growth_analyser.py`**

Uses historical `bucket_usage` rows to compute growth rate:
```python
class GrowthAnalyser:
    def calculate_growth_rate(self, history: list[BucketUsage]) -> float
    # Returns GB per day growth rate
    
    def project_full_date(self, current_gb: float,
                          quota_gb: float,
                          growth_gb_per_day: float) -> date | None
    # Returns estimated date when bucket will hit quota, or None
    
    def detect_anomaly(self, history: list[BucketUsage]) -> bool
    # True if growth rate in last 24h is > 3× the 7-day average
```

**Step 4 — Implement `quota_checker.py`**

```python
class QuotaChecker:
    def evaluate_tenant(self, tenant: Tenant) -> QuotaStatus
    def evaluate_bucket(self, bucket: Bucket) -> QuotaStatus
    def get_quota_percentage(self, used: int, quota: int) -> float
    def should_alert(self, old_status: QuotaStatus,
                     new_status: QuotaStatus) -> bool
```

**Step 5 — Configure RGW endpoint in .env**

> **Architecture reminder:** Both `RGW_ENDPOINT` and `RGW_ADMIN_ENDPOINT`
> must point to the **Load Balancer VIP**, not an individual Gateway node IP.
> The LB VIP is visible in the **Load Balancer** section of the SDS Nexus GUI.
> Using a gateway node IP directly will break if that node is rebooted or
> replaced — the LB handles failover automatically.

```bash
# ── CORRECT: Use the Load Balancer VIP ─────────────────────────────
RGW_ENDPOINT="http://<Load-Balancer-VIP>:7480"
RGW_ADMIN_ENDPOINT="http://<Load-Balancer-VIP>:7480/admin"

# ── WRONG: Do NOT use individual Gateway node IPs ──────────────────
# RGW_ENDPOINT="http://rgw-gateway-node1:7480"   ← breaks on node restart

# ── Full config ────────────────────────────────────────────────────
RGW_ACCESS_KEY="<sds-nexus-monitor access key from radosgw-admin>"
RGW_SECRET_KEY="<sds-nexus-monitor secret key from radosgw-admin>"
RGW_ADMIN_ACCESS_KEY="<same key — read-only caps>"
RGW_ADMIN_SECRET_KEY="<same secret>"
RGW_VERIFY_SSL=false    # Set true if LB has a valid TLS certificate

# ── Verify the endpoint works through the LB ───────────────────────
curl -v http://<Load-Balancer-VIP>:7480/
# Expected response header: Server: Ceph Object Gateway
```

### API Endpoints

```
GET /api/v1/tenants                          # All tenants summary
GET /api/v1/tenants/{id}                     # Tenant detail with current usage
GET /api/v1/tenants/{id}/buckets             # All buckets for tenant
GET /api/v1/tenants/{id}/usage/history       # Daily usage history (with ?days=30)
GET /api/v1/tenants/{id}/quota               # Quota status and percentage
GET /api/v1/buckets                          # All buckets (admin only)
GET /api/v1/buckets/{id}                     # Single bucket detail
GET /api/v1/buckets/{id}/usage/history       # Bucket growth history
GET /api/v1/buckets/{id}/growth              # Growth rate and projection
```

### Testing Module 3

```bash
# Test RGW Admin API connectivity
python -c "
import requests
from app.core.config import get_settings
cfg = get_settings().get_rgw_settings()
r = requests.get(
    f'{cfg.admin_endpoint}/metadata/user',
    params={'max-entries': 5},
    # Auth signing handled by RGWAdminClient
)
print(r.status_code, r.text[:200])
"

# Run storage collection manually
python -m app.workers.storage_monitor --run-once

# Check tenant data
psql \$DATABASE_URL -c "
  SELECT display_name, current_size_bytes/1073741824.0 AS size_gb,
         quota_status, last_synced_at
  FROM tenants ORDER BY current_size_bytes DESC LIMIT 10;"
```

---

## 6. Module 4 — Reporting

### Report Types

| Report | Trigger | Format | Recipients |
|---|---|---|---|
| 6-Hour Health Summary | Every 6 hours | HTML Email | Ops team |
| Daily Operations Report | 07:00 daily | HTML Email | Ops team |
| Monthly Excel Report | 1st of month 06:00 | .xlsx | Management |
| Monthly PDF Report | 1st of month 06:00 | .pdf | Management |
| Capacity Alert | When threshold crossed | HTML Email | Ops + alerts list |
| On-Demand | API call | .xlsx or .pdf | Requester |

### Files to Implement

```
app/services/reporting/
├── __init__.py
├── report_service.py       ← Orchestrates all report generation
├── email_report.py         ← HTML email builder (Jinja2 templates)
├── excel_report.py         ← OpenPyXL monthly workbook builder
├── pdf_report.py           ← PDF generation from Excel or HTML
├── chart_builder.py        ← Matplotlib/Plotly chart generation
├── data_aggregator.py      ← Pulls data from DB for report periods
└── email_sender.py         ← SMTP sending with retry and attachments

app/templates/              ← Jinja2 HTML templates
├── email/
│   ├── base.html           ← Shared layout (logo, footer, styles)
│   ├── daily_report.html
│   ├── six_hour_report.html
│   └── alert_notification.html

app/workers/
└── report_worker.py        ← APScheduler jobs for all report schedules

app/api/v1/endpoints/
└── reports.py              ← CRUD + download + re-send endpoints

app/repositories/
└── reporting.py            ← ReportRepository
```

### Implementation Steps

**Step 1 — Implement `data_aggregator.py`**

All report data queries are centralised here. Returns plain dataclasses,
not ORM objects — keeps reporting logic independent of DB schema changes.

```python
class ReportDataAggregator:
    def get_cluster_health_summary(self, cluster_id: int, period: ReportPeriod) -> ClusterSummary
    def get_capacity_trend(self, cluster_id: int, period: ReportPeriod) -> list[CapacityPoint]
    def get_osd_health_summary(self, cluster_id: int) -> OSDSummary
    def get_top_tenants_by_usage(self, limit: int = 10) -> list[TenantUsageSummary]
    def get_bucket_growth_report(self, period: ReportPeriod) -> list[BucketGrowth]
    def get_alert_summary(self, cluster_id: int, period: ReportPeriod) -> AlertSummary
    def get_monthly_usage_per_tenant(self, year: int, month: int) -> list[TenantMonthlyUsage]
```

**Step 2 — Implement `chart_builder.py`**

Generates chart image files (PNG) that are embedded in Excel and emails.

```python
class ChartBuilder:
    def capacity_trend_chart(self, data: list[CapacityPoint],
                             output_path: Path) -> Path
    # Line chart: date vs used_gb, available_gb, total_gb
    
    def tenant_usage_pie_chart(self, data: list[TenantUsageSummary],
                               output_path: Path) -> Path
    # Pie: top 10 tenants by GB, others grouped
    
    def osd_status_bar_chart(self, up_in: int, up_out: int,
                             down: int, output_path: Path) -> Path
    # Stacked bar: OSD states
    
    def bucket_growth_chart(self, data: list[BucketGrowth],
                            output_path: Path) -> Path
    # Bar chart: top 10 growing buckets
    
    def alert_timeline_chart(self, data: AlertSummary,
                             output_path: Path) -> Path
    # Timeline: alerts by severity over the period
```

**Step 3 — Implement `excel_report.py`**

Monthly Excel workbook — one sheet per section.

```python
class MonthlyExcelReport:
    def generate(self, year: int, month: int,
                 cluster_id: int = None) -> Path:
    # Returns path to generated .xlsx file
    
    # Sheets to implement:
    # 1. "Summary"       — KPIs, cluster health, headline numbers
    # 2. "Capacity"      — Daily capacity table + embedded trend chart
    # 3. "Tenants"       — Usage per tenant, growth %, quota status
    # 4. "Buckets"       — Top 50 buckets by size, growth rate
    # 5. "Chargeback"    — Cost per tenant (GBP + USD)
    # 6. "Alerts"        — Alert log for the month
    # 7. "Nodes"         — Node health summary
```

**Step 4 — Implement `email_report.py`**

```python
class EmailReportBuilder:
    def build_daily_report(self, cluster_id: int) -> EmailMessage
    def build_six_hour_report(self, cluster_id: int) -> EmailMessage
    def build_capacity_alert(self, cluster: Cluster,
                             capacity: CapacitySnapshot) -> EmailMessage
    def build_osd_alert(self, cluster: Cluster,
                        osd_event: OSDEvent) -> EmailMessage
```

**Step 5 — Implement `email_sender.py`**

```python
class EmailSender:
    # Uses aiosmtplib for async sending, tenacity for retry
    async def send(self, message: EmailMessage,
                   recipients: list[str]) -> bool
    async def send_with_attachment(self, message: EmailMessage,
                                   recipients: list[str],
                                   attachment_path: Path) -> bool
```

**Step 6 — Configure Jinja2 templates**

```bash
mkdir -p app/templates/email

# base.html — inline CSS (email clients strip <style> blocks)
# Sections: header with cluster name, content block, footer with timestamp
# Keep it simple — Outlook compatibility requires table-based layout
```

**Step 7 — Configure email settings**

```bash
SMTP_HOST="smtp.internal"
SMTP_PORT=587
SMTP_USER="sds-nexus@company.com"
SMTP_PASSWORD="your-smtp-password"
SMTP_USE_TLS=true
SMTP_FROM_ADDRESS="sds-nexus@company.com"
SMTP_FROM_NAME="SDS Nexus Platform"

EMAIL_OPS_TEAM="ops-lead@company.com,storage-ops@company.com"
EMAIL_MANAGEMENT="it-manager@company.com"
EMAIL_ALERTS="ops-team@company.com,on-call@company.com"

REPORT_OUTPUT_PATH="/var/sds-nexus/reports"
REPORT_DAILY_EMAIL_TIME="07:00"
REPORT_6H_SCHEDULE="0 */6 * * *"
REPORT_MONTHLY_DAY=1
```

### API Endpoints

```
GET    /api/v1/reports                        # List all reports
GET    /api/v1/reports/{id}                   # Report metadata
GET    /api/v1/reports/{id}/download          # Download report file
POST   /api/v1/reports/{id}/resend            # Re-send email
POST   /api/v1/reports/generate/monthly       # On-demand monthly report
POST   /api/v1/reports/generate/daily         # On-demand daily report
```

### Testing Module 4

```bash
# Test email connectivity
python -c "
import asyncio, aiosmtplib
asyncio.run(aiosmtplib.send(
    'Test', sender='test@test.com',
    recipients=['you@company.com'],
    hostname='smtp.internal', port=587
))
"

# Generate a report manually
python -c "
from app.services.reporting.report_service import ReportService
from app.db.session import get_db_context
with get_db_context() as db:
    svc = ReportService(db)
    path = svc.generate_monthly_excel(year=2025, month=6, cluster_id=1)
    print(f'Report saved: {path}')
"
```

---

## 7. Module 5 — Chargeback

### How Chargeback Works

```
Monthly Billing Cycle:
  1. Collect daily TenantUsage rows (from Module 3)
  2. On billing day (default: 1st of month), run chargeback calculation
  3. For each tenant, compute:
       avg_size_gb  = average daily size over the billing period
       peak_size_gb = maximum daily size over the billing period
       billable_gb  = avg_size_gb (configurable: avg or peak)
  4. Apply rate: billable_gb × rate_gbp_per_gb = subtotal_gbp
  5. Apply VAT: subtotal_gbp × (1 + vat_rate) = total_gbp
  6. Convert: total_gbp × exchange_rate = total_usd
  7. Save Chargeback row (status=DRAFT)
  8. Operations team reviews, then finalises (status=FINALISED)
  9. Generate chargeback Excel/PDF report
  10. Email to management and optionally to tenant contact
```

### Files to Implement

```
app/services/chargeback/
├── __init__.py
├── calculator.py         ← Core billing calculation engine
├── chargeback_service.py ← Orchestration: calculate, persist, report
├── forecaster.py         ← Linear/exponential capacity cost forecast
├── rate_manager.py       ← Read/write rates from DB settings table
└── schemas.py            ← ChargebackResult, ForecastResult

app/api/v1/endpoints/
├── chargeback.py         ← View, finalise, adjust chargeback records
└── forecasts.py          ← View cost/capacity forecasts

app/repositories/
└── chargeback.py         ← ChargebackRepository, ForecastRepository
```

### Implementation Steps

**Step 1 — Implement `calculator.py`**

Pure calculation class — no DB access, no external calls. Fully unit-testable.

```python
class ChargebackCalculator:
    def calculate(
        self,
        usage_records: list[TenantDailyUsage],
        rate_gbp: float,
        rate_usd: float,
        exchange_rate: float,
        vat_rate: float,
        billing_method: str = "average",  # "average" | "peak"
    ) -> ChargebackResult:
    
    def calculate_subtotal(self, billable_gb: float,
                           rate_per_gb: float) -> float
    def apply_vat(self, subtotal: float, vat_rate: float) -> tuple[float, float]
    def convert_currency(self, amount_gbp: float,
                         rate: float) -> float
    def calculate_average_gb(self, daily_usage: list[float]) -> float
    def calculate_peak_gb(self, daily_usage: list[float]) -> float
```

**Step 2 — Implement `rate_manager.py`**

Reads live rates from the `settings` table so ops can adjust without
redeployment. Falls back to `.env` values if DB settings are absent.

```python
class RateManager:
    def get_gbp_rate(self) -> float       # From DB settings or env
    def get_usd_rate(self) -> float
    def get_exchange_rate(self) -> float
    def get_vat_rate(self) -> float
    def update_rate(self, key: str, value: float) -> None  # admin only
```

**Step 3 — Implement `forecaster.py`**

```python
class CapacityForecaster:
    def forecast_linear(
        self,
        history: list[CapacityPoint],   # From capacity_history table
        days_ahead: int = 90,
    ) -> ForecastResult
    # Uses numpy linear regression on historical GB values
    # Returns forecasted_size_gb + confidence_interval + r_squared
    
    def forecast_cost(
        self,
        forecasted_gb: float,
        rate_gbp: float,
        rate_usd: float,
        vat_rate: float,
    ) -> CostForecast
    
    def estimate_capacity_full_date(
        self,
        total_gb: float,
        forecast: ForecastResult,
    ) -> date | None
    # Returns estimated date cluster reaches 100% capacity
```

**Step 4 — Implement `chargeback_service.py`**

```python
class ChargebackService:
    def run_monthly_chargeback(self, year: int, month: int) -> list[Chargeback]
    def get_tenant_usage_for_period(self, tenant_id: int,
                                    year: int, month: int) -> list[TenantUsage]
    def finalise_chargeback(self, chargeback_id: int,
                            user: User) -> Chargeback
    def apply_adjustment(self, chargeback_id: int,
                         amount_gbp: float, notes: str) -> Chargeback
    def generate_chargeback_report(self, year: int,
                                   month: int) -> Path  # Returns Excel path
```

**Step 5 — Configure rates in .env**

```bash
CHARGEBACK_GBP_PER_GB_MONTH=0.05       # £0.05 per GB per month
CHARGEBACK_USD_PER_GB_MONTH=0.06       # $0.06 per GB per month
CHARGEBACK_GBP_USD_RATE=1.27           # 1 GBP = 1.27 USD
CHARGEBACK_BILLING_DAY=1               # Run calculation on 1st of month
CHARGEBACK_INCLUDE_VAT=true
CHARGEBACK_VAT_RATE=0.20               # 20% UK VAT
```

### Excel Chargeback Report Layout

```
Sheet: "Chargeback - June 2025"
Row 1: Company / Cluster / Period header
Row 2: Generated date / Exchange rate used / VAT rate

Columns:
  Tenant Name | Cost Centre | Avg GB | Peak GB | Billable GB |
  Rate (GBP/GB) | Subtotal GBP | VAT GBP | Total GBP | Total USD |
  Adjustment | Final GBP | Status

Last row: TOTALS in bold, currency formatted
```

### API Endpoints

```
GET  /api/v1/chargeback                    # List chargeback records
GET  /api/v1/chargeback/{year}/{month}     # Monthly chargeback summary
GET  /api/v1/chargeback/{id}               # Single record detail
POST /api/v1/chargeback/calculate          # Trigger calculation (admin/billing)
PATCH /api/v1/chargeback/{id}/finalise     # Mark as finalised (billing role)
PATCH /api/v1/chargeback/{id}/adjust       # Apply credit/adjustment
GET  /api/v1/forecasts                     # All active forecasts
GET  /api/v1/forecasts/cluster/{id}        # Cluster-level forecast
GET  /api/v1/forecasts/tenant/{id}         # Tenant-level cost forecast
```

### Testing Module 5

```bash
# Test calculator with sample data
python -c "
from app.services.chargeback.calculator import ChargebackCalculator
calc = ChargebackCalculator()
result = calc.calculate(
    usage_records=[100.0, 110.0, 120.0],  # GB per day
    rate_gbp=0.05,
    rate_usd=0.06,
    exchange_rate=1.27,
    vat_rate=0.20,
)
print(f'Billable: {result.billable_gb:.2f} GB')
print(f'Total GBP: £{result.total_gbp:.2f}')
print(f'Total USD: \${result.total_usd:.2f}')
"

# Run chargeback for last month
python -c "
from datetime import date
from app.services.chargeback.chargeback_service import ChargebackService
from app.db.session import get_db_context
today = date.today()
with get_db_context() as db:
    svc = ChargebackService(db)
    records = svc.run_monthly_chargeback(today.year, today.month - 1)
    print(f'Generated {len(records)} chargeback records')
"
```

---

## 8. Module 6 — Dashboard

### Dashboard Types

| Dashboard | Audience | Data Shown |
|---|---|---|
| Operations | Storage Ops Team | Live cluster health, alerts, OSD status, recovery |
| Management | IT Management | Capacity trend, costs, tenant growth, report links |
| Customer / Tenant | Individual tenants | Their own usage, quota, bucket list, cost estimate |

### Technology Choice

**Backend:** FastAPI endpoints already provide the JSON APIs.  
**Frontend:** Two options — choose one based on your team skills:

**Option A — Plotly Dash (Python only)**
- Pros: No separate frontend — pure Python, same codebase
- Cons: Limited UI flexibility, harder to customise
- Best for: Small ops team, quick delivery

**Option B — React/Vue + existing FastAPI (recommended)**
- Pros: Full control, modern UI, reuses all v1 API endpoints
- Cons: Requires frontend developer
- Best for: Production enterprise with customer-facing portal

This guide covers the **backend API additions** needed for both options.

### Files to Implement

```
app/services/dashboard/
├── __init__.py
├── ops_dashboard.py        ← Aggregated real-time operations data
├── management_dashboard.py ← KPI summaries, cost overviews
└── tenant_dashboard.py     ← Per-tenant usage and quota view

app/api/v1/endpoints/
└── dashboard.py            ← Single-call endpoints for dashboard widgets

app/api/v1/endpoints/
└── auth.py                 ← Login endpoint (POST /auth/token)
```

### Implementation Steps

**Step 1 — Implement auth endpoint (required for all dashboards)**

```python
# POST /api/v1/auth/token
# Body: username + password (OAuth2PasswordRequestForm)
# Returns: access_token + refresh_token

class AuthService:
    def authenticate(self, username: str, password: str,
                     db: Session) -> User | None
    def login(self, user: User) -> TokenResponse
    def refresh(self, refresh_token: str) -> TokenResponse
```

**Step 2 — Implement ops dashboard data endpoints**

These are "summary" endpoints — they aggregate multiple tables into one
response to minimise round trips from dashboard clients.

```
GET /api/v1/dashboard/ops
Response: {
  cluster_health,       # status, health_status string
  osd_summary,          # total/up/down/in/out counts
  pg_summary,           # total/active_clean/degraded counts
  capacity,             # used_gb, total_gb, percent, trend_7d
  active_alerts,        # count by severity
  recent_alerts,        # last 10 alerts
  io_stats,             # read/write bytes/sec
  nodes_summary,        # online/offline count
  recovery_progress     # bytes_remaining, time_estimate
}

GET /api/v1/dashboard/ops/live
# Server-Sent Events stream for real-time updates
# Pushes new health status every 30 seconds
```

**Step 3 — Implement management dashboard endpoints**

```
GET /api/v1/dashboard/management
Response: {
  capacity_trend_30d,      # Daily capacity points for chart
  cost_current_month,      # Running total GBP/USD
  cost_last_month,         # Comparison figure
  cost_trend_6m,           # 6-month cost history
  top_tenants_by_usage,    # Top 10 tenant names + GB
  top_growing_tenants,     # Fastest growing tenants
  forecast_90d,            # Projected GB and cost in 90 days
  report_links,            # Latest Excel/PDF report links
  alert_summary_30d        # Alerts by severity over last 30 days
}
```

**Step 4 — Implement tenant dashboard endpoints (customer portal)**

Tenant users see ONLY their own data. Enforce at query level:

```
GET /api/v1/dashboard/tenant
# Returns data for the authenticated tenant user's account only
# Tenant user role added to User model

Response: {
  my_usage_gb,        # Current size
  my_quota_gb,        # Allocated quota
  quota_percent,      # 0–100
  my_buckets,         # List with name/size/objects
  growth_trend_30d,   # My daily usage history
  current_cost_gbp,   # Running month cost
  current_cost_usd,
  last_invoice        # Link to last month's chargeback report
}
```

**Step 5 — Configure Plotly Dash (Option A only)**

```python
# app/dashboard/app.py
import dash
from dash import dcc, html
import plotly.graph_objects as go

# Dash app mounts as a sub-application of the FastAPI app
# Use starlette-dash or mount separately on port 8050
```

### API Endpoints

```
POST /api/v1/auth/token               # Login
POST /api/v1/auth/refresh             # Refresh access token
POST /api/v1/auth/logout              # Invalidate refresh token

GET  /api/v1/dashboard/ops            # Operations dashboard data
GET  /api/v1/dashboard/ops/live       # SSE stream (real-time)
GET  /api/v1/dashboard/management     # Management dashboard data
GET  /api/v1/dashboard/tenant         # Tenant self-service view
```

---

## 9. Database Setup & Migrations

### Initial Setup

```bash
# 1. Create PostgreSQL database and user
sudo -u postgres psql << 'EOF'
CREATE USER sds_nexus_user WITH PASSWORD 'your-strong-password-here';
CREATE DATABASE sds_nexus OWNER sds_nexus_user ENCODING 'UTF8'
    LC_COLLATE 'en_GB.UTF-8' LC_CTYPE 'en_GB.UTF-8' TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE sds_nexus TO sds_nexus_user;

-- Read-only role for reporting queries (optional)
CREATE ROLE sds_nexus_readonly;
GRANT CONNECT ON DATABASE sds_nexus TO sds_nexus_readonly;
GRANT USAGE ON SCHEMA public TO sds_nexus_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sds_nexus_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO sds_nexus_readonly;
EOF

# 2. Apply all migrations
cd /opt/sds-nexus
alembic upgrade head

# 3. Verify tables created
psql -U sds_nexus_user -d sds_nexus -c "\dt"

# 4. Seed initial data
python scripts/init_db.py --seed-cluster

# 5. Verify seed data
psql -U sds_nexus_user -d sds_nexus -c "
  SELECT username, role, created_at FROM users;
  SELECT category, key, value FROM settings ORDER BY category, key;"
```

### Creating New Migrations

When you add or modify a model:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "add_tenant_cost_centre_column"

# Review the generated file in alembic/versions/
# Always review before applying — autogenerate is not always perfect

# Apply
alembic upgrade head

# Rollback one step if needed
alembic downgrade -1

# View migration history
alembic history --verbose
```

### Database Backup (Production)

```bash
# Add to cron: daily pg_dump
sudo tee /etc/cron.d/sds-nexus-backup << 'EOF'
# SDS Nexus - Daily database backup at 02:00
0 2 * * * sds-nexus /opt/sds-nexus/scripts/backup_db.sh
EOF

# scripts/backup_db.sh content:
#!/bin/bash
BACKUP_DIR="/var/sds-nexus/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/sds_nexus_${DATE}.dump"

pg_dump -Fc -U sds_nexus_user sds_nexus > "${BACKUP_FILE}"
gzip "${BACKUP_FILE}"

# Retain last 30 daily backups
find "${BACKUP_DIR}" -name "*.dump.gz" -mtime +30 -delete

echo "Backup complete: ${BACKUP_FILE}.gz"
```

### Data Retention Policy

```sql
-- Run weekly via cron to prune old time-series data
-- Keeps data within retention policy, avoids unbounded table growth

-- Keep node_metrics for 90 days
DELETE FROM node_metrics WHERE recorded_at < NOW() - INTERVAL '90 days';

-- Keep bucket_usage hourly rows for 1 year, daily for forever
DELETE FROM bucket_usage
WHERE recorded_at < NOW() - INTERVAL '1 year';

-- Keep capacity_history for 2 years
DELETE FROM capacity_history
WHERE recorded_at < NOW() - INTERVAL '2 years';

-- Keep resolved alerts for 180 days
DELETE FROM alerts
WHERE status = 'resolved'
  AND resolved_at < NOW() - INTERVAL '180 days';
```

---

## 10. Scheduler & Worker Setup

### APScheduler Configuration

All background jobs are managed by APScheduler with a PostgreSQL job store
(for persistence across restarts). Configure in `app/workers/scheduler.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = BackgroundScheduler(
    jobstores={
        'default': SQLAlchemyJobStore(url=settings.get_db_settings().url)
    },
    timezone='UTC',
)
```

### Job Schedule Reference

| Job | Function | Schedule | Misfire Grace |
|---|---|---|---|
| Cluster health | `run_cluster_health_check` | Every 5 min | 60 sec |
| Capacity snapshot | `run_capacity_snapshot` | Every 1 hour | 5 min |
| Node metrics | `run_node_metrics_collection` | Every 5 min | 60 sec |
| SMART check | `run_smart_collection` | Every 30 min | 5 min |
| Object storage sync | `run_object_storage_sync` | Every 1 hour | 5 min |
| Daily report email | `send_daily_report` | 07:00 UTC daily | 30 min |
| 6-hour report | `send_six_hour_report` | Every 6 hours | 30 min |
| Monthly chargeback | `run_monthly_chargeback` | 1st, 06:00 UTC | 2 hours |
| Monthly reports | `generate_monthly_reports` | 1st, 06:30 UTC | 2 hours |
| Data retention | `run_data_retention_cleanup` | 03:00 UTC Sun | 1 hour |

### Starting Scheduler with FastAPI

```python
# In app/main.py lifespan() — add after DB check:
from app.workers.scheduler import scheduler
scheduler.start()
yield
scheduler.shutdown(wait=False)
```

---

## 11. Docker Production Deployment

### Install Docker on RHEL 10

RHEL 10 does not include Docker in its default repositories. Use either
**Podman** (Red Hat's preferred OCI runtime, included in RHEL 10) or install
Docker CE from the Docker repository.

**Option A — Podman (Recommended for RHEL 10)**

Podman is pre-installed on RHEL 10, daemonless, and rootless by default.
It is fully Docker CLI compatible via the `podman-docker` shim.

```bash
# Podman is already installed on RHEL 10 — verify
podman --version

# Install docker-compose compatible tool (podman-compose)
sudo dnf5 install -y podman-compose

# OR install the docker shim for full Docker CLI compatibility
sudo dnf5 install -y podman-docker

# Verify compatibility
docker --version   # Uses the podman shim
docker-compose --version
```

**Option B — Docker CE (if Docker specifically required)**

```bash
# Add Docker CE repository
sudo dnf5 config-manager --add-repo \
    https://download.docker.com/linux/rhel/docker-ce.repo

# Install Docker CE
sudo dnf5 install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
sudo systemctl enable --now docker

# Add sds-nexus service account to docker group
sudo usermod -aG docker sds-nexus

# Verify
docker --version
docker compose version
```

### Build and Push

```bash
# Build production image
docker build -t sds-nexus-platform:1.0.0 \
    -f docker/Dockerfile .

# Tag for registry
docker tag sds-nexus-platform:1.0.0 \
    your-registry.internal/sds-nexus-platform:1.0.0

docker push your-registry.internal/sds-nexus-platform:1.0.0
```

### Production docker-compose.prod.yml

```yaml
version: "3.9"

services:
  api:
    image: your-registry.internal/sds-nexus-platform:1.0.0
    container_name: sds-nexus-api
    restart: always
    environment:
      APP_ENV: production
      APP_HOST: "0.0.0.0"
      APP_PORT: "8000"
    env_file:
      - /etc/sds-nexus/production.env   # Secrets file — NOT in repo
    volumes:
      - /var/sds-nexus/reports:/var/sds-nexus/reports
      - /var/log/sds-nexus:/var/log/sds-nexus
      - /etc/sds-nexus/keys:/etc/sds-nexus/keys:ro  # SSH keys read-only
    ports:
      - "127.0.0.1:8000:8000"  # Only bind locally — Nginx proxies
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Nginx Reverse Proxy

```nginx
# /etc/nginx/conf.d/sds-nexus.conf
server {
    listen 443 ssl http2;
    server_name sds-nexus.internal;

    ssl_certificate     /etc/ssl/certs/sds-nexus.crt;
    ssl_certificate_key /etc/ssl/private/sds-nexus.key;

    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /docs {
        # Block in production — only allow from ops network
        allow 10.0.0.0/8;
        deny  all;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

---

## 12. Systemd Service Setup (Non-Docker Deployment)

For deployments without Docker on RHEL 10. Systemd provides service
management, automatic restarts, and journal logging — no separate
process manager (supervisord, PM2) is needed.

### Install Application (Non-Docker)

```bash
# Deploy application code
sudo -u sds-nexus git clone \
    https://your-repo.internal/sds-nexus-platform.git \
    /opt/sds-nexus/app

# OR copy from build artefact
sudo cp -r /build/sds-nexus-platform/* /opt/sds-nexus/
sudo chown -R sds-nexus:sds-nexus /opt/sds-nexus/

# Install Python dependencies
sudo -u sds-nexus /opt/sds-nexus/venv/bin/pip install \
    -r /opt/sds-nexus/requirements.txt

# Run database migrations
sudo -u sds-nexus bash -c "
    cd /opt/sds-nexus && \
    source /etc/sds-nexus/production.env && \
    ./venv/bin/alembic upgrade head
"

# Seed initial data
sudo -u sds-nexus bash -c "
    cd /opt/sds-nexus && \
    source /etc/sds-nexus/production.env && \
    ./venv/bin/python scripts/init_db.py
"
```

### Main API Service Unit

```bash
sudo tee /etc/systemd/system/sds-nexus-api.service << 'EOF'
[Unit]
Description=SDS Nexus Storage Operations Platform API
Documentation=file:///opt/sds-nexus/docs/IMPLEMENTATION_GUIDE.md
After=network-online.target postgresql.service
Wants=network-online.target
Requires=postgresql.service

[Service]
Type=simple
User=sds-nexus
Group=sds-nexus
WorkingDirectory=/opt/sds-nexus
EnvironmentFile=/etc/sds-nexus/production.env
ExecStart=/opt/sds-nexus/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --no-access-log \
    --proxy-headers \
    --forwarded-allow-ips="*"
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10
TimeoutStartSec=60
TimeoutStopSec=30
KillMode=mixed
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sds-nexus-api

# RHEL 10 systemd security hardening
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=true
RestrictRealtime=true
RestrictSUIDSGID=true
LockPersonality=true
MemoryDenyWriteExecute=false    # Required for Python JIT
SystemCallFilter=@system-service
ReadWritePaths=/var/sds-nexus /var/log/sds-nexus /tmp/sds-nexus
ReadOnlyPaths=/etc/sds-nexus /opt/sds-nexus

[Install]
WantedBy=multi-user.target
EOF
```

### Worker Service Unit (APScheduler background jobs)

```bash
sudo tee /etc/systemd/system/sds-nexus-worker.service << 'EOF'
[Unit]
Description=SDS Nexus Background Workers (Monitoring + Reporting)
After=sds-nexus-api.service
BindsTo=sds-nexus-api.service

[Service]
Type=simple
User=sds-nexus
Group=sds-nexus
WorkingDirectory=/opt/sds-nexus
EnvironmentFile=/etc/sds-nexus/production.env
ExecStart=/opt/sds-nexus/venv/bin/python -m app.workers.main
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sds-nexus-worker
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/sds-nexus /var/log/sds-nexus /tmp/sds-nexus
ReadOnlyPaths=/etc/sds-nexus /opt/sds-nexus

[Install]
WantedBy=multi-user.target
EOF
```

### Systemd Timer Units (Alternative to APScheduler)

If you prefer OS-level scheduling instead of in-process APScheduler,
create one timer per job. Timers survive application restarts and
integrate with `systemctl list-timers` for visibility.

```bash
# --- Cluster Health Check (every 5 minutes) ---
sudo tee /etc/systemd/system/sds-nexus-cluster-health.service << 'EOF'
[Unit]
Description=SDS Nexus Cluster Health Collection (one-shot)
After=network-online.target postgresql.service

[Service]
Type=oneshot
User=sds-nexus
Group=sds-nexus
WorkingDirectory=/opt/sds-nexus
EnvironmentFile=/etc/sds-nexus/production.env
ExecStart=/opt/sds-nexus/venv/bin/python \
    -m app.workers.cluster_monitor --run-once
TimeoutStartSec=120
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sds-nexus-cluster-health
EOF

sudo tee /etc/systemd/system/sds-nexus-cluster-health.timer << 'EOF'
[Unit]
Description=SDS Nexus Cluster Health Check — every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true
AccuracySec=30s

[Install]
WantedBy=timers.target
EOF

# --- Node Metrics (every 5 minutes) ---
sudo tee /etc/systemd/system/sds-nexus-node-metrics.service << 'EOF'
[Unit]
Description=SDS Nexus Node Metrics Collection (one-shot)
After=network-online.target

[Service]
Type=oneshot
User=sds-nexus
WorkingDirectory=/opt/sds-nexus
EnvironmentFile=/etc/sds-nexus/production.env
ExecStart=/opt/sds-nexus/venv/bin/python \
    -m app.workers.node_monitor --run-once
TimeoutStartSec=120
SyslogIdentifier=sds-nexus-node-metrics
EOF

sudo tee /etc/systemd/system/sds-nexus-node-metrics.timer << 'EOF'
[Unit]
Description=SDS Nexus Node Metrics — every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true
AccuracySec=30s

[Install]
WantedBy=timers.target
EOF

# --- Object Storage Sync (every 1 hour) ---
sudo tee /etc/systemd/system/sds-nexus-storage-sync.timer << 'EOF'
[Unit]
Description=SDS Nexus Object Storage Sync — hourly

[Timer]
OnCalendar=hourly
Persistent=true
AccuracySec=5min

[Install]
WantedBy=timers.target
EOF

# --- Daily Report (07:00 UTC) ---
sudo tee /etc/systemd/system/sds-nexus-daily-report.timer << 'EOF'
[Unit]
Description=SDS Nexus Daily Email Report — 07:00 UTC

[Timer]
OnCalendar=*-*-* 07:00:00 UTC
Persistent=true
AccuracySec=5min

[Install]
WantedBy=timers.target
EOF

# --- Monthly Chargeback (1st of month, 06:00 UTC) ---
sudo tee /etc/systemd/system/sds-nexus-monthly-chargeback.timer << 'EOF'
[Unit]
Description=SDS Nexus Monthly Chargeback — 1st of month 06:00 UTC

[Timer]
OnCalendar=*-*-01 06:00:00 UTC
Persistent=true
AccuracySec=30min

[Install]
WantedBy=timers.target
EOF
```

### Enable and Start All Units

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start the API and worker
sudo systemctl enable --now sds-nexus-api.service
sudo systemctl enable --now sds-nexus-worker.service

# Enable all timers
sudo systemctl enable --now sds-nexus-cluster-health.timer
sudo systemctl enable --now sds-nexus-node-metrics.timer
sudo systemctl enable --now sds-nexus-storage-sync.timer
sudo systemctl enable --now sds-nexus-daily-report.timer
sudo systemctl enable --now sds-nexus-monthly-chargeback.timer

# Verify services are running
sudo systemctl status sds-nexus-api
sudo systemctl status sds-nexus-worker

# Verify timers are scheduled
systemctl list-timers | grep sds-nexus

# Tail the API log
sudo journalctl -u sds-nexus-api -f

# Tail worker log
sudo journalctl -u sds-nexus-worker -f

# View last 100 lines from all sds-nexus units combined
sudo journalctl -t sds-nexus-api -t sds-nexus-worker \
    --since "1 hour ago" --no-pager
```

### RHEL 10 Log Rotation

RHEL 10 uses `journald` for service logs. Configure retention:

```bash
sudo tee /etc/systemd/journald.conf.d/sds-nexus.conf << 'EOF'
[Journal]
SystemMaxUse=2G
SystemKeepFree=500M
SystemMaxFileSize=100M
MaxRetentionSec=30day
EOF

sudo systemctl restart systemd-journald
```

---

## 13. Environment Variable Reference

Complete `.env` for production deployment. Copy to `/etc/sds-nexus/production.env`
and set `chmod 600`.

```bash
# =============================================================================
# APPLICATION
# =============================================================================
APP_NAME="SDS Nexus Platform"
APP_VERSION="1.0.0"
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
APP_DEBUG=false
APP_SECRET_KEY=<generated: python -c "import secrets; print(secrets.token_hex(32))">

# =============================================================================
# DATABASE
# =============================================================================
DB_HOST=your-postgres-host.internal
DB_PORT=5432
DB_NAME=sds_nexus
DB_USER=sds_nexus_user
DB_PASSWORD=<your-strong-db-password>
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_ECHO_SQL=false

# =============================================================================
# CEPH CLUSTER (Read-Only sds-monitor account)
# =============================================================================
CEPH_CLUSTER_NAME=prod-cluster-01
CEPH_CLUSTER_DISPLAY_NAME="Production Ceph Cluster"
CEPH_MONITOR_HOST=mon01.ceph.internal
CEPH_ADMIN_NODE=admin.ceph.internal
CEPH_SSH_USER=sds-monitor                      # Read-only local account
CEPH_SSH_KEY_PATH=/etc/sds-nexus/keys/sds_monitor_ed25519
CEPH_SSH_PORT=22
CEPH_SSH_TIMEOUT=30
CEPH_SSH_RETRY_ATTEMPTS=3
CEPH_SSH_RETRY_DELAY=5

# =============================================================================
# RGW (sds-nexus-monitor RGW user — read caps only)
# =============================================================================
RGW_ENDPOINT=http://rgw01.ceph.internal:7480
RGW_ACCESS_KEY=<from radosgw-admin user info --uid sds-nexus-monitor>
RGW_SECRET_KEY=<from radosgw-admin user info --uid sds-nexus-monitor>
RGW_ADMIN_ENDPOINT=http://rgw01.ceph.internal:7480/admin
RGW_ADMIN_ACCESS_KEY=<same as RGW_ACCESS_KEY>
RGW_ADMIN_SECRET_KEY=<same as RGW_SECRET_KEY>
RGW_VERIFY_SSL=false
RGW_TIMEOUT=30

# =============================================================================
# EMAIL
# =============================================================================
SMTP_HOST=smtp.company.internal
SMTP_PORT=587
SMTP_USER=sds-nexus@company.com
SMTP_PASSWORD=<smtp-password>
SMTP_USE_TLS=true
SMTP_FROM_ADDRESS=sds-nexus@company.com
SMTP_FROM_NAME="SDS Nexus Platform"

EMAIL_OPS_TEAM=ops-lead@company.com,storage-ops@company.com
EMAIL_MANAGEMENT=it-manager@company.com
EMAIL_ALERTS=ops-team@company.com,on-call@company.com

# =============================================================================
# CHARGEBACK
# =============================================================================
CHARGEBACK_CURRENCY_PRIMARY=GBP
CHARGEBACK_CURRENCY_SECONDARY=USD
CHARGEBACK_GBP_PER_GB_MONTH=0.05
CHARGEBACK_USD_PER_GB_MONTH=0.06
CHARGEBACK_GBP_USD_RATE=1.27
CHARGEBACK_BILLING_DAY=1
CHARGEBACK_INCLUDE_VAT=true
CHARGEBACK_VAT_RATE=0.20

# =============================================================================
# ALERT THRESHOLDS
# =============================================================================
ALERT_OSD_DOWN_THRESHOLD=1
ALERT_PG_DEGRADED_THRESHOLD=100
ALERT_CAPACITY_WARNING_PERCENT=75
ALERT_CAPACITY_CRITICAL_PERCENT=85
ALERT_CLUSTER_UNHEALTHY=true

# =============================================================================
# MONITORING INTERVALS (seconds)
# =============================================================================
MONITOR_CLUSTER_HEALTH_INTERVAL=300
MONITOR_NODE_INTERVAL=300
MONITOR_OBJECT_STORAGE_INTERVAL=3600
MONITOR_CAPACITY_INTERVAL=3600

# =============================================================================
# REPORTING
# =============================================================================
REPORT_OUTPUT_PATH=/var/sds-nexus/reports
REPORT_RETENTION_DAYS=365
REPORT_DAILY_EMAIL_TIME=07:00
REPORT_MONTHLY_DAY=1

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_OUTPUT_PATH=/var/log/sds-nexus
LOG_ROTATION=100 MB
LOG_RETENTION=30 days

# =============================================================================
# SECURITY
# =============================================================================
JWT_SECRET_KEY=<generated: python -c "import secrets; print(secrets.token_hex(32))">
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## 14. Security Hardening Checklist

Complete before going live in production.

### Credentials

- [ ] Change default admin password set by `init_db.py` (`ChangeMe123!`)
- [ ] Generate strong `APP_SECRET_KEY` (min 64 hex chars)
- [ ] Generate strong `JWT_SECRET_KEY` (min 64 hex chars)
- [ ] SSH key for `sds-monitor` uses ED25519 (not RSA 2048)
- [ ] SSH key has no passphrase (required for automation)
- [ ] `/etc/sds-nexus/keys/` directory mode is `700`
- [ ] SSH private key mode is `600`, owned by `sds-nexus`
- [ ] `.env` / `production.env` mode is `600`, owned by `sds-nexus`
- [ ] RGW `sds-nexus-monitor` user has `read` caps only — verify with `radosgw-admin user info`
- [ ] Ceph `client.sds-monitor` keyring has `allow r` only — verify with `ceph auth get`

### Network

- [ ] API port 8000 bound to `127.0.0.1` only (Nginx proxies it)
- [ ] Nginx serves only HTTPS (TLS 1.2+)
- [ ] `/docs` and `/redoc` blocked from external networks
- [ ] PostgreSQL port 5432 not exposed externally
- [ ] SSH port on Ceph nodes allows only platform server IP

### Application

- [ ] `APP_ENV=production` (disables `/docs`, `/redoc`, `/openapi.json`)
- [ ] `APP_DEBUG=false`
- [ ] `DB_ECHO_SQL=false` (never log SQL in production)
- [ ] `LOG_DIAGNOSE=false` (prevents variable values in tracebacks)
- [ ] Rate limiting configured on API endpoints

### Database

- [ ] `sds_nexus_user` has no SUPERUSER privilege
- [ ] Regular automated backups configured and tested
- [ ] `pg_hba.conf` limits connections to `sds_nexus_user` from platform IP only

---

## 15. Troubleshooting

### SSH Connection Failures

```bash
# Test manually as the monitoring user
ssh -i /etc/sds-nexus/keys/sds_monitor_ed25519 \
    -v sds-monitor@ceph-admin.internal \
    "echo connected"

# Common causes:
# - Key not in sds-monitor's authorized_keys
# - Wrong key permissions (must be 600)
# - sshd_config PubkeyAuthentication=no on Ceph node
# - FirewallD / iptables blocking port 22 from platform IP
```

### Ceph Command Permission Denied

```bash
# Test sudo access for sds-monitor
ssh -i /etc/sds-nexus/keys/sds_monitor_ed25519 \
    sds-monitor@ceph-admin.internal \
    "sudo /usr/bin/ceph status --format json"

# Common causes:
# - sudoers.d/sds-nexus-monitor not present on that node
# - Wrong command path (use which ceph to verify)
# - requiretty set in sudoers (add Defaults !requiretty for sds-monitor)
```

### RGW Admin API 403 Forbidden

```bash
# Check caps on the RGW user
sudo radosgw-admin user info --uid="sds-nexus-monitor" | python3 -m json.tool

# Re-add caps if missing
sudo radosgw-admin caps add \
    --uid="sds-nexus-monitor" \
    --caps="users=read;buckets=read;metadata=read;usage=read;zone=read"

# Test with curl (signing required — use boto3 in practice)
```

### Database Connection Refused

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection from platform server
psql -h your-db-host -U sds_nexus_user -d sds_nexus -c "SELECT 1"

# Check pg_hba.conf allows platform server IP
sudo grep sds_nexus /etc/postgresql/*/main/pg_hba.conf
```

### Reports Not Being Generated

```bash
# Check scheduler is running
curl http://localhost:8000/api/v1/health

# Check report output directory permissions
ls -la /var/sds-nexus/reports/
sudo chown -R sds-nexus:sds-nexus /var/sds-nexus/reports

# Check application logs
tail -100 /var/log/sds-nexus/sds_nexus_errors_$(date +%Y-%m-%d).log

# Trigger a manual report
python -c "
from app.services.reporting.report_service import ReportService
from app.db.session import get_db_context
with get_db_context() as db:
    svc = ReportService(db)
    svc.send_daily_report(cluster_id=1)
"
```

### High Memory Usage

```bash
# Check DB connection pool — reduce if too many connections
# DB_POOL_SIZE=5 (down from 10) in .env

# Check report files accumulating in temp dir
du -sh /tmp/sds-nexus/*
# Increase cleanup frequency in report_service.py

# Check for large JSON payloads from ceph osd df on large clusters
# Add pagination or compression to SSH transfer
```

---

*Last Updated: Production v1.0.0*  
*Storage Operations Team — Internal Use Only*
