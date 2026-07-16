# Monitoring & Alerting Integration Guide

## Overview

This guide covers integration with external monitoring and alerting systems for comprehensive operational visibility.

## Table of Contents

1. [Alertmanager Integration](#alertmanager-integration)
2. [Email Notifications](#email-notifications)
3. [Slack Integration](#slack-integration)
4. [PagerDuty Integration](#pagerduty-integration)
5. [ServiceNow Integration](#servicenow-integration)
6. [Custom Webhooks](#custom-webhooks)
7. [Log Aggregation](#log-aggregation)
8. [APM Integration](#apm-integration)

---

## 1. Alertmanager Integration

### Installation

```bash
# Download Alertmanager
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar xzf alertmanager-0.26.0.linux-amd64.tar.gz

# Install
sudo cp alertmanager-0.26.0.linux-amd64/alertmanager /usr/local/bin/
sudo cp alertmanager-0.26.0.linux-amd64/amtool /usr/local/bin/
sudo mkdir -p /etc/alertmanager /var/lib/alertmanager

# Create user
sudo useradd --system --shell /sbin/nologin alertmanager
sudo chown -R alertmanager:alertmanager /etc/alertmanager /var/lib/alertmanager
```

### Configuration

Create `/etc/alertmanager/alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.company.com:587'
  smtp_from: 'sds-nexus-alerts@company.com'
  smtp_auth_username: 'sds-nexus@company.com'
  smtp_auth_password: 'YOUR_SMTP_PASSWORD'
  smtp_require_tls: true

# Alert routing
route:
  group_by: ['alertname', 'cluster', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  
  routes:
    # Critical alerts go to on-call and email
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true
    
    # Cluster alerts go to storage team
    - match:
        component: ceph
      receiver: 'storage-team'
    
    # Chargeback alerts go to finance
    - match:
        component: chargeback
      receiver: 'finance-team'

receivers:
  - name: 'default'
    email_configs:
      - to: 'storage-ops@company.com'
        headers:
          Subject: '[SDS Nexus] Alert: {{ .GroupLabels.alertname }}'

  - name: 'critical-alerts'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
        description: '{{ .CommonAnnotations.summary }}'
    email_configs:
      - to: 'storage-alerts@company.com,oncall@company.com'
        headers:
          Subject: '[CRITICAL] SDS Nexus: {{ .GroupLabels.alertname }}'

  - name: 'storage-team'
    email_configs:
      - to: 'storage-team@company.com'
        headers:
          Subject: '[Storage Alert] {{ .GroupLabels.alertname }}'

  - name: 'finance-team'
    email_configs:
      - to: 'finance-team@company.com'
        headers:
          Subject: '[Cost Alert] {{ .GroupLabels.alertname }}'

inhibit_rules:
  # Inhibit warning if critical is firing
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'cluster']
  
  # Inhibit during maintenance windows
  - source_match:
      alertname: 'MaintenanceWindowActive'
    target_match_re:
      severity: '.*'
```

### Systemd Service

Create `/etc/systemd/system/alertmanager.service`:

```ini
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
    --web.listen-address=:9093 \
    --cluster.listen-address=:9094

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable alertmanager
sudo systemctl start alertmanager
```

---

## 2. Email Notifications

### SMTP Configuration

Update `.env` file:

```bash
# SMTP Configuration
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=sds-nexus@company.com
SMTP_PASSWORD=your_password_here
SMTP_USE_TLS=true
SMTP_FROM_ADDRESS=sds-nexus@company.com
SMTP_FROM_NAME=SDS Nexus Platform

# Email Distribution Lists
EMAIL_OPS_TEAM=storage-ops@company.com,platform-ops@company.com
EMAIL_MANAGEMENT=storage-mgmt@company.com
EMAIL_ALERTS=storage-alerts@company.com,oncall@company.com
```

### HTML Email Template

Customize email templates in `app/templates/email/alert.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .alert { padding: 20px; margin: 10px; border-left: 4px solid; }
        .critical { border-color: #dc3545; background-color: #f8d7da; }
        .warning { border-color: #ffc107; background-color: #fff3cd; }
        .info { border-color: #17a2b8; background-color: #d1ecf1; }
    </style>
</head>
<body>
    <h2>SDS Nexus Alert</h2>
    <div class="alert {{ severity }}">
        <h3>{{ alert_name }}</h3>
        <p><strong>Cluster:</strong> {{ cluster_name }}</p>
        <p><strong>Severity:</strong> {{ severity }}</p>
        <p><strong>Time:</strong> {{ timestamp }}</p>
        <p><strong>Description:</strong> {{ description }}</p>
        <p><strong>Action Required:</strong> {{ action }}</p>
    </div>
    <p>
        <a href="http://grafana.company.com/d/ceph-cluster">View Dashboard</a> |
        <a href="http://prometheus.company.com">View Alerts</a>
    </p>
</body>
</html>
```

---

## 3. Slack Integration

### Create Slack Webhook

1. Go to https://api.slack.com/apps
2. Create new app
3. Enable "Incoming Webhooks"
4. Create webhook for your channel
5. Copy webhook URL

### Configure Alertmanager for Slack

Add to `/etc/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'slack-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#sds-nexus-alerts'
        title: '{{ .CommonAnnotations.summary }}'
        text: |
          *Alert:* {{ .CommonLabels.alertname }}
          *Severity:* {{ .CommonLabels.severity }}
          *Cluster:* {{ .CommonLabels.cluster_name }}
          *Description:* {{ .CommonAnnotations.description }}
          *View:* <http://grafana.company.com|Dashboard>
        send_resolved: true
        color: |
          {{ if eq .Status "firing" }}
            {{ if eq .CommonLabels.severity "critical" }}danger{{ else }}warning{{ end }}
          {{ else }}good{{ end }}
```

### Custom Slack Bot (Python)

Create `scripts/slack_notifier.py`:

```python
import requests
import json
from datetime import datetime

def send_slack_alert(webhook_url, alert_data):
    """Send formatted alert to Slack"""
    
    severity_colors = {
        'critical': '#dc3545',
        'warning': '#ffc107',
        'info': '#17a2b8',
    }
    
    message = {
        "username": "SDS Nexus",
        "icon_emoji": ":warning:",
        "attachments": [{
            "color": severity_colors.get(alert_data['severity'], '#6c757d'),
            "title": alert_data['alert_name'],
            "text": alert_data['description'],
            "fields": [
                {"title": "Cluster", "value": alert_data['cluster'], "short": True},
                {"title": "Severity", "value": alert_data['severity'].upper(), "short": True},
                {"title": "Component", "value": alert_data['component'], "short": True},
                {"title": "Time", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "short": True},
            ],
            "footer": "SDS Nexus Monitoring",
            "ts": int(datetime.now().timestamp())
        }]
    }
    
    response = requests.post(webhook_url, data=json.dumps(message))
    return response.status_code == 200

# Usage
if __name__ == "__main__":
    alert = {
        'alert_name': 'CephOSDDown',
        'severity': 'critical',
        'cluster': 'ue-south-1',
        'component': 'osd',
        'description': '3 OSDs are down in the cluster'
    }
    send_slack_alert('YOUR_WEBHOOK_URL', alert)
```

---

## 4. PagerDuty Integration

### Setup PagerDuty Service

1. Login to PagerDuty
2. Go to Configuration → Services
3. Create new service: "SDS Nexus Platform"
4. Integration type: "Use our API directly: Events API v2"
5. Copy Integration Key

### Configure Alertmanager

Add to alertmanager.yml:

```yaml
receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - routing_key: 'YOUR_INTEGRATION_KEY'
        severity: 'critical'
        description: '{{ .CommonAnnotations.summary }}'
        details:
          cluster: '{{ .CommonLabels.cluster_name }}'
          alert: '{{ .CommonLabels.alertname }}'
          severity: '{{ .CommonLabels.severity }}'
        client: 'SDS Nexus Monitoring'
        client_url: 'http://grafana.company.com'
```

### Custom PagerDuty Integration (Python)

```python
import requests

def create_pagerduty_incident(integration_key, alert_data):
    """Create PagerDuty incident"""
    
    url = "https://events.pagerduty.com/v2/enqueue"
    
    payload = {
        "routing_key": integration_key,
        "event_action": "trigger",
        "payload": {
            "summary": alert_data['summary'],
            "severity": alert_data['severity'],
            "source": "SDS Nexus",
            "component": alert_data['component'],
            "group": alert_data['cluster'],
            "class": "storage",
            "custom_details": alert_data['details']
        },
        "links": [{
            "href": "http://grafana.company.com",
            "text": "View Dashboard"
        }]
    }
    
    response = requests.post(url, json=payload)
    return response.json()
```

---

## 5. ServiceNow Integration

### REST API Integration

```python
import requests
from requests.auth import HTTPBasicAuth

class ServiceNowIntegration:
    def __init__(self, instance, username, password):
        self.instance = instance
        self.auth = HTTPBasicAuth(username, password)
        self.base_url = f"https://{instance}.service-now.com/api/now"
    
    def create_incident(self, alert_data):
        """Create ServiceNow incident from alert"""
        
        url = f"{self.base_url}/table/incident"
        
        # Map severity to ServiceNow impact/urgency
        severity_mapping = {
            'critical': {'impact': '1', 'urgency': '1'},  # High impact/urgency
            'warning': {'impact': '2', 'urgency': '2'},   # Medium
            'info': {'impact': '3', 'urgency': '3'},      # Low
        }
        
        severity = severity_mapping.get(alert_data['severity'], {'impact': '3', 'urgency': '3'})
        
        payload = {
            'short_description': f"SDS Nexus Alert: {alert_data['alert_name']}",
            'description': f"""
            Cluster: {alert_data['cluster']}
            Severity: {alert_data['severity']}
            Component: {alert_data['component']}
            
            Details:
            {alert_data['description']}
            
            Dashboard: http://grafana.company.com
            """,
            'impact': severity['impact'],
            'urgency': severity['urgency'],
            'assignment_group': 'Storage Operations',
            'category': 'Storage',
            'subcategory': 'Object Storage',
            'caller_id': 'sds-nexus-system'
        }
        
        response = requests.post(url, json=payload, auth=self.auth)
        return response.json()
    
    def update_incident(self, incident_id, state, work_notes):
        """Update existing incident"""
        
        url = f"{self.base_url}/table/incident/{incident_id}"
        
        payload = {
            'state': state,  # 1=New, 2=In Progress, 6=Resolved, 7=Closed
            'work_notes': work_notes
        }
        
        response = requests.patch(url, json=payload, auth=self.auth)
        return response.json()

# Usage
snow = ServiceNowIntegration('your-instance', 'username', 'password')
alert = {
    'alert_name': 'CephClusterUnhealthy',
    'severity': 'critical',
    'cluster': 'ue-south-1',
    'component': 'cluster',
    'description': 'Cluster health status is HEALTH_ERR'
}
incident = snow.create_incident(alert)
print(f"Created incident: {incident['result']['number']}")
```

---

## 6. Custom Webhooks

### Generic Webhook Configuration

Add to Alertmanager:

```yaml
receivers:
  - name: 'webhook'
    webhook_configs:
      - url: 'http://your-webhook-endpoint.com/alerts'
        send_resolved: true
        http_config:
          bearer_token: 'YOUR_AUTH_TOKEN'
```

### Webhook Receiver Example (FastAPI)

```python
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

class Alert(BaseModel):
    status: str
    labels: dict
    annotations: dict
    startsAt: str
    endsAt: Optional[str]

class WebhookPayload(BaseModel):
    version: str
    groupKey: str
    status: str
    receiver: str
    groupLabels: dict
    commonLabels: dict
    commonAnnotations: dict
    alerts: List[Alert]

@app.post("/alerts")
async def receive_alert(
    payload: WebhookPayload,
    authorization: str = Header(None)
):
    """Receive and process Prometheus alerts"""
    
    # Verify authorization
    if not authorization or authorization != "Bearer YOUR_AUTH_TOKEN":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Process each alert
    for alert in payload.alerts:
        if alert.status == "firing":
            # Alert is firing
            process_firing_alert(alert)
        else:
            # Alert is resolved
            process_resolved_alert(alert)
    
    return {"status": "ok", "received": len(payload.alerts)}

def process_firing_alert(alert: Alert):
    """Process firing alert"""
    print(f"Alert firing: {alert.labels.get('alertname')}")
    # Add your custom logic here
    # - Create ticket
    # - Send to custom system
    # - Trigger automation

def process_resolved_alert(alert: Alert):
    """Process resolved alert"""
    print(f"Alert resolved: {alert.labels.get('alertname')}")
    # Add your custom logic here
```

---

## 7. Log Aggregation

### ELK Stack Integration

#### Filebeat Configuration

Create `/etc/filebeat/filebeat.yml`:

```yaml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/sds-nexus/*.log
    fields:
      service: sds-nexus
      environment: production
    multiline:
      pattern: '^\['
      negate: true
      match: after

  - type: docker
    containers.ids:
      - '*'
    processors:
      - add_docker_metadata: ~

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "sds-nexus-%{+yyyy.MM.dd}"

logging.level: info
```

### Splunk Integration

Create `/etc/splunk/inputs.conf`:

```ini
[monitor:///var/log/sds-nexus]
disabled = false
sourcetype = sds_nexus_logs
index = storage_operations

[monitor:///var/lib/prometheus/wal]
disabled = false
sourcetype = prometheus_wal
index = metrics
```

---

## 8. APM Integration

### New Relic

```python
# Install New Relic
pip install newrelic

# Add to application startup
import newrelic.agent
newrelic.agent.initialize('/etc/newrelic/newrelic.ini')

# Wrap WSGI application
app = newrelic.agent.WSGIApplicationWrapper(app)
```

### Datadog

```python
# Install Datadog
pip install ddtrace

# Run with Datadog tracer
ddtrace-run python app/main.py
```

---

## Testing Integrations

### Test Alertmanager

```bash
# Test configuration
amtool check-config /etc/alertmanager/alertmanager.yml

# Send test alert
amtool alert add test_alert \
  alertname=TestAlert \
  severity=info \
  cluster=test \
  --annotation=summary="Test alert from CLI"
```

### Test Email

```bash
curl -X POST http://localhost:8000/api/v1/test/email \
  -H "Content-Type: application/json" \
  -d '{
    "to": "test@company.com",
    "subject": "Test Alert",
    "body": "This is a test alert"
  }'
```

### Test Webhook

```bash
curl -X POST http://your-webhook-endpoint/alerts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d @test_alert.json
```

---

## Monitoring Integration Checklist

- [ ] Alertmanager installed and configured
- [ ] Email notifications working
- [ ] Slack integration tested
- [ ] PagerDuty integration for critical alerts
- [ ] ServiceNow integration (if required)
- [ ] Custom webhooks configured
- [ ] Log aggregation setup
- [ ] All integrations documented
- [ ] Test alerts sent and received
- [ ] On-call rotation configured
- [ ] Escalation procedures defined

---

**Document Version**: 1.0  
**Last Updated**: January 15, 2024  
**Owner**: Storage Operations Team
