# Kubernetes Integration for SDS Nexus Platform

## Overview

This guide shows how to leverage your Docker Desktop Kubernetes cluster to enhance the SDS Nexus Platform with:

1. **Production-Grade Deployment** - Deploy the entire stack on Kubernetes
2. **High Availability** - Multiple replicas with automatic failover
3. **Auto-Scaling** - Scale based on load
4. **Development Environment** - Local testing before production
5. **CI/CD Pipeline** - Automated testing and deployment
6. **Service Mesh** - Advanced networking and observability

---

## What You Can Do with Kubernetes

### Option 1: Local Development & Testing (Recommended Starting Point)
- Test Kubernetes manifests locally before production
- Develop and test the application in a K8s environment
- Validate Helm charts
- Practice disaster recovery
- Train team on Kubernetes

### Option 2: Production Deployment
- Deploy the entire SDS Nexus Platform on Kubernetes
- High availability with multiple replicas
- Auto-scaling based on metrics
- Rolling updates with zero downtime
- Built-in health checks and self-healing

### Option 3: Hybrid Approach
- Keep Ceph on VMs (current setup)
- Deploy SDS Nexus Platform on Kubernetes
- Best of both worlds

---

## Quick Start: Deploy on Your Local Kubernetes

### Prerequisites
- ✅ Docker Desktop with Kubernetes enabled (you have this!)
- ✅ kubectl installed
- ✅ Helm installed (optional, but recommended)

### Step 1: Verify Kubernetes Cluster

```bash
# Check cluster is running
kubectl cluster-info

# Check nodes
kubectl get nodes

# Expected output:
# NAME             STATUS   ROLES           AGE   VERSION
# docker-desktop   Ready    control-plane   Xd    vX.XX.X
```

### Step 2: Create Namespace

```bash
kubectl create namespace sds-nexus
kubectl config set-context --current --namespace=sds-nexus
```

### Step 3: Deploy PostgreSQL

```bash
# Create PostgreSQL deployment
kubectl apply -f k8s/postgresql.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=postgresql --timeout=120s
```

### Step 4: Deploy API

```bash
# Create ConfigMap with environment variables
kubectl create configmap sds-nexus-config --from-env-file=.env.production.example

# Deploy API
kubectl apply -f k8s/api-deployment.yaml

# Expose API service
kubectl apply -f k8s/api-service.yaml
```

### Step 5: Deploy Monitoring Stack

```bash
# Deploy Prometheus
kubectl apply -f k8s/prometheus.yaml

# Deploy Grafana
kubectl apply -f k8s/grafana.yaml
```

### Step 6: Access Services

```bash
# Port forward to access locally
kubectl port-forward service/sds-nexus-api 8000:8000
kubectl port-forward service/prometheus 9090:9090
kubectl port-forward service/grafana 3000:3000

# Access:
# API: http://localhost:8000
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

---

## Architecture Options

### Architecture 1: Full Kubernetes Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ API Pod x3   │  │ Worker Pod   │  │ PostgreSQL   │      │
│  │ (replicas)   │  │              │  │ StatefulSet  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ Prometheus   │  │ Grafana      │                        │
│  │ StatefulSet  │  │ Deployment   │                        │
│  └──────────────┘  └──────────────┘                        │
│                                                              │
│  ┌─────────────────────────────────────┐                   │
│  │         Ingress Controller           │                   │
│  │  (nginx / traefik / istio)          │                   │
│  └─────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
                   External Access
            (LoadBalancer / NodePort)
                         │
                         ▼
                  Ceph Cluster (VMs)
           (Existing infrastructure)
```

### Architecture 2: Hybrid (Recommended)

```
┌──────────────────────────────────────┐
│      Kubernetes Cluster              │
│                                      │
│  ┌──────────────┐  ┌──────────────┐ │
│  │ API Pod x3   │  │ Worker Pod   │ │
│  └──────────────┘  └──────────────┘ │
│                                      │
│  ┌──────────────┐  ┌──────────────┐ │
│  │ Prometheus   │  │ Grafana      │ │
│  └──────────────┘  └──────────────┘ │
└──────────────────────────────────────┘
              │
              ▼
    ┌─────────────────┐
    │   PostgreSQL    │
    │   (External)    │
    └─────────────────┘
              │
              ▼
    ┌─────────────────┐
    │  Ceph Cluster   │
    │     (VMs)       │
    └─────────────────┘
```

---

## Kubernetes Manifests

I'll create comprehensive Kubernetes manifests for you. Let me structure them properly:

### Directory Structure

```
k8s/
├── base/                    # Base configurations
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   └── kustomization.yaml
├── database/
│   ├── postgresql-pvc.yaml
│   ├── postgresql-deployment.yaml
│   └── postgresql-service.yaml
├── api/
│   ├── api-deployment.yaml
│   ├── api-service.yaml
│   ├── api-hpa.yaml        # Horizontal Pod Autoscaler
│   └── api-ingress.yaml
├── workers/
│   ├── worker-deployment.yaml
│   └── worker-cronjob.yaml
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus-config.yaml
│   │   ├── prometheus-deployment.yaml
│   │   ├── prometheus-service.yaml
│   │   └── prometheus-pvc.yaml
│   └── grafana/
│       ├── grafana-config.yaml
│       ├── grafana-deployment.yaml
│       ├── grafana-service.yaml
│       └── grafana-pvc.yaml
├── overlays/               # Environment-specific
│   ├── development/
│   ├── staging/
│   └── production/
└── helm/                   # Helm chart (optional)
    └── sds-nexus/
```

---

## Benefits of Using Kubernetes

### 1. High Availability
- Multiple API replicas
- Automatic pod restart on failure
- Load balancing across pods
- Rolling updates with zero downtime

### 2. Scalability
```yaml
# Auto-scale based on CPU
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sds-nexus-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sds-nexus-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 3. Resource Management
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### 4. Health Checks
```yaml
livenessProbe:
  httpGet:
    path: /api/v1/health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /api/v1/health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

### 5. Configuration Management
- ConfigMaps for non-sensitive config
- Secrets for sensitive data (encrypted at rest)
- Easy environment-specific overrides

### 6. Monitoring & Observability
- Built-in Prometheus metrics
- Kubernetes metrics (CPU, memory, network)
- Distributed tracing (with Istio/Jaeger)
- Centralized logging (with EFK stack)

---

## Use Cases for Your Setup

### Use Case 1: Development & Testing

**Scenario:** Test changes before deploying to production

```bash
# Build and test locally
docker build -t sds-nexus:dev .

# Load into K8s
kubectl apply -f k8s/dev/

# Test
kubectl port-forward svc/sds-nexus-api 8000:8000
curl http://localhost:8000/api/v1/health/live

# Debug
kubectl logs -f deployment/sds-nexus-api
kubectl describe pod <pod-name>
```

### Use Case 2: CI/CD Pipeline

**Scenario:** Automated testing and deployment

```yaml
# .github/workflows/deploy.yml
name: Deploy to Kubernetes

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build Docker image
        run: docker build -t sds-nexus:${{ github.sha }} .
      
      - name: Push to registry
        run: docker push sds-nexus:${{ github.sha }}
      
      - name: Deploy to K8s
        run: |
          kubectl set image deployment/sds-nexus-api \
            api=sds-nexus:${{ github.sha }}
```

### Use Case 3: Load Testing

**Scenario:** Test how system handles load

```bash
# Scale up for testing
kubectl scale deployment sds-nexus-api --replicas=5

# Run load test
kubectl run -it --rm load-test --image=williamyeh/hey --restart=Never -- \
  -z 60s -c 50 http://sds-nexus-api:8000/api/v1/health/live

# Monitor
kubectl top pods
watch kubectl get pods
```

### Use Case 4: Disaster Recovery Testing

**Scenario:** Test recovery procedures

```bash
# Simulate pod failure
kubectl delete pod sds-nexus-api-xxxxx

# Verify auto-recovery
kubectl get pods -w

# Simulate node failure
kubectl drain docker-desktop --ignore-daemonsets

# Verify recovery
kubectl uncordon docker-desktop
```

### Use Case 5: Multi-Environment Management

**Scenario:** Manage dev, staging, prod on same cluster

```bash
# Deploy to different namespaces
kubectl apply -f k8s/overlays/development/ -n sds-nexus-dev
kubectl apply -f k8s/overlays/staging/ -n sds-nexus-staging
kubectl apply -f k8s/overlays/production/ -n sds-nexus-prod

# Switch between environments
kubectl config set-context --current --namespace=sds-nexus-dev
kubectl config set-context --current --namespace=sds-nexus-prod
```

---

## Advanced Integrations

### 1. Service Mesh (Istio)

**Benefits:**
- Advanced traffic routing
- A/B testing and canary deployments
- Circuit breaking
- Mutual TLS between services
- Distributed tracing

**Example: Canary Deployment**
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: sds-nexus-api
spec:
  hosts:
  - sds-nexus-api
  http:
  - match:
    - headers:
        version:
          exact: "v2"
    route:
    - destination:
        host: sds-nexus-api
        subset: v2
  - route:
    - destination:
        host: sds-nexus-api
        subset: v1
      weight: 90
    - destination:
        host: sds-nexus-api
        subset: v2
      weight: 10
```

### 2. GitOps with ArgoCD

**Benefits:**
- Declarative deployments
- Git as source of truth
- Automatic sync
- Rollback capability

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Deploy SDS Nexus via ArgoCD
argocd app create sds-nexus \
  --repo https://github.com/Dinesh1496/SDS.git \
  --path k8s/overlays/production \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace sds-nexus
```

### 3. Observability Stack

**EFK Stack (Elasticsearch, Fluentd, Kibana)**
```bash
# Centralized logging
kubectl apply -f https://raw.githubusercontent.com/fluent/fluentd-kubernetes-daemonset/master/fluentd-daemonset-elasticsearch.yaml

# Access logs in Kibana
kubectl port-forward svc/kibana 5601:5601
```

**Jaeger for Tracing**
```bash
# Distributed tracing
kubectl apply -f https://raw.githubusercontent.com/jaegertracing/jaeger-operator/main/deploy/crds/jaegertracing.io_jaegers_crd.yaml
```

### 4. Secret Management

**Sealed Secrets**
```bash
# Encrypt secrets before committing to Git
kubeseal --format yaml < secret.yaml > sealed-secret.yaml
kubectl apply -f sealed-secret.yaml
```

**External Secrets Operator**
```yaml
# Sync from external vault
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: sds-nexus-secrets
spec:
  secretStoreRef:
    name: vault-backend
  target:
    name: sds-nexus-secrets
  data:
  - secretKey: db-password
    remoteRef:
      key: sds-nexus/database
      property: password
```

---

## Quick Wins for Your Setup

### 1. Local Development (5 minutes)

```bash
# Clone your repo
git clone https://github.com/Dinesh1496/SDS.git
cd SDS

# Deploy to local K8s
kubectl create namespace sds-nexus-dev
kubectl apply -f k8s/ -n sds-nexus-dev

# Access locally
kubectl port-forward -n sds-nexus-dev svc/sds-nexus-api 8000:8000
```

### 2. Auto-Scaling Demo (10 minutes)

```bash
# Deploy with HPA
kubectl apply -f k8s/api/api-hpa.yaml

# Generate load
kubectl run -it load-gen --rm --image=busybox --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://sds-nexus-api:8000; done"

# Watch auto-scaling
watch kubectl get hpa
watch kubectl get pods
```

### 3. Rolling Update Demo (5 minutes)

```bash
# Update image
kubectl set image deployment/sds-nexus-api api=sds-nexus:v2

# Watch rolling update
kubectl rollout status deployment/sds-nexus-api

# Rollback if needed
kubectl rollout undo deployment/sds-nexus-api
```

---

## Recommended Next Steps

### Phase 1: Learning & Testing (This Week)
1. ✅ Deploy to local Kubernetes
2. ✅ Test health checks and probes
3. ✅ Practice scaling and rollbacks
4. ✅ Set up port-forwarding for access

### Phase 2: CI/CD Integration (Next Week)
1. Set up GitHub Actions
2. Automate Docker builds
3. Automate K8s deployments
4. Add automated testing

### Phase 3: Advanced Features (Next Month)
1. Implement Helm charts
2. Add service mesh (Istio)
3. Set up GitOps (ArgoCD)
4. Implement centralized logging

### Phase 4: Production Readiness (Next Quarter)
1. High availability setup
2. Disaster recovery procedures
3. Performance tuning
4. Security hardening

---

## Cost Comparison

### Current: Docker Compose
- ✅ Simple setup
- ✅ Good for single server
- ❌ No auto-scaling
- ❌ Manual recovery
- ❌ No load balancing

### With Kubernetes
- ✅ Auto-scaling
- ✅ Self-healing
- ✅ Load balancing
- ✅ Rolling updates
- ✅ Resource optimization
- ⚠️ More complex (but worth it!)

---

## Getting Started Today

### Option 1: Quick Test (30 minutes)

I'll create the K8s manifests for you, and you can:
```bash
kubectl apply -f k8s/
kubectl get pods
kubectl logs -f <pod-name>
```

### Option 2: Comprehensive Setup (2-3 hours)

Full Kubernetes deployment with:
- Namespace isolation
- ConfigMaps and Secrets
- Persistent volumes
- Services and Ingress
- Monitoring stack
- Auto-scaling

### Option 3: Helm Chart (1 hour)

One-command deployment:
```bash
helm install sds-nexus ./helm/sds-nexus \
  --namespace sds-nexus \
  --create-namespace
```

---

## Want Me to Create the K8s Manifests?

I can create comprehensive Kubernetes manifests for you including:

1. **Base Manifests** - Namespace, ConfigMaps, Secrets
2. **Database** - PostgreSQL StatefulSet with PVC
3. **API** - Deployment with HPA and Service
4. **Workers** - CronJobs for scheduled tasks
5. **Monitoring** - Prometheus and Grafana
6. **Ingress** - External access configuration
7. **Helm Chart** - Package everything for easy deployment

**Let me know which option you want, and I'll create the files for you!**

Would you like me to:
1. Create basic K8s manifests for testing?
2. Create comprehensive production-ready manifests?
3. Create a Helm chart for easy deployment?
4. All of the above?

