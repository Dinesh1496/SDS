# Kubernetes Deployment for SDS Nexus Platform

## 🚀 Quick Start

**Deploy to your Docker Desktop Kubernetes in 20 minutes!**

### Prerequisites
- ✅ Docker Desktop with Kubernetes enabled
- ✅ kubectl installed and configured
- ✅ Docker image built

### One-Command Deployment

```bash
# Build image
docker build -t sds-nexus:latest -f docker/Dockerfile .

# Deploy everything
kubectl apply -f k8s/base/
kubectl apply -f k8s/database/
kubectl apply -f k8s/api/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod --all -n sds-nexus --timeout=300s

# Access API
kubectl port-forward -n sds-nexus svc/sds-nexus-api 8000:8000

# Test
curl http://localhost:8000/api/v1/health/live
```

---

## 📋 Detailed Guide

See **[QUICK_START_K8S.md](QUICK_START_K8S.md)** for step-by-step instructions.

---

## 📁 Directory Structure

```
k8s/
├── README.md                        # This file
├── QUICK_START_K8S.md              # Detailed deployment guide
├── base/                            # Base configurations
│   ├── namespace.yaml              # sds-nexus namespace
│   ├── configmap.yaml              # Non-sensitive config
│   └── secrets.yaml                # Secrets template
├── database/                        # PostgreSQL
│   ├── postgresql-pvc.yaml         # Persistent volume claim
│   ├── postgresql-deployment.yaml  # PostgreSQL deployment
│   └── postgresql-service.yaml     # PostgreSQL service
├── api/                             # API service
│   ├── api-deployment.yaml         # API deployment (2 replicas)
│   ├── api-service.yaml            # API service (LoadBalancer)
│   └── api-hpa.yaml                # Horizontal Pod Autoscaler
└── monitoring/                      # Monitoring stack (optional)
    ├── prometheus/
    └── grafana/
```

---

## 🎯 What You Get

### High Availability
- **2 API replicas** (can scale to 10)
- **Automatic pod restart** on failure
- **Load balancing** across pods
- **Health checks** (liveness & readiness probes)

### Auto-Scaling
- **CPU-based scaling** (70% threshold)
- **Memory-based scaling** (80% threshold)
- **Scale from 2 to 10 pods** automatically

### Resource Management
- **Resource requests** defined
- **Resource limits** enforced
- **Efficient scheduling**

### Observability
- **Prometheus metrics** auto-discovered
- **Structured logging**
- **Pod health monitoring**

---

## 🔧 Common Operations

### View All Resources
```bash
kubectl get all -n sds-nexus
```

### View Logs
```bash
# API logs
kubectl logs -f deployment/sds-nexus-api -n sds-nexus

# PostgreSQL logs
kubectl logs -f deployment/postgresql -n sds-nexus
```

### Scale Manually
```bash
kubectl scale deployment sds-nexus-api --replicas=5 -n sds-nexus
```

### Update Image
```bash
# Build new image
docker build -t sds-nexus:v2 -f docker/Dockerfile .

# Update deployment
kubectl set image deployment/sds-nexus-api api=sds-nexus:v2 -n sds-nexus

# Watch rollout
kubectl rollout status deployment/sds-nexus-api -n sds-nexus
```

### Rollback
```bash
kubectl rollout undo deployment/sds-nexus-api -n sds-nexus
```

### Access Shell in Pod
```bash
kubectl exec -it deployment/sds-nexus-api -n sds-nexus -- sh
```

### Port Forward Services
```bash
# API
kubectl port-forward -n sds-nexus svc/sds-nexus-api 8000:8000

# PostgreSQL
kubectl port-forward -n sds-nexus svc/postgresql 5432:5432

# Prometheus (if deployed)
kubectl port-forward -n sds-nexus svc/prometheus 9090:9090

# Grafana (if deployed)
kubectl port-forward -n sds-nexus svc/grafana 3000:3000
```

---

## 🧪 Testing

### Health Checks
```bash
# Liveness
curl http://localhost:8000/api/v1/health/live

# Readiness
curl http://localhost:8000/api/v1/health/ready

# Metrics
curl http://localhost:8000/api/v1/metrics | head -20
```

### Load Testing
```bash
# Generate load
kubectl run -it --rm load-test --image=williamyeh/hey --restart=Never -n sds-nexus -- \
  -z 60s -c 10 http://sds-nexus-api:8000/api/v1/health/live

# Watch auto-scaling
kubectl get hpa -n sds-nexus -w
```

### Resilience Testing
```bash
# Delete a pod (watch it auto-restart)
kubectl delete pod -l app=sds-nexus-api -n sds-nexus --force

# Watch recovery
kubectl get pods -n sds-nexus -w
```

---

## 🔐 Security Notes

### Before Deploying

1. **Update secrets** in `k8s/base/secrets.yaml`
   ```bash
   # Generate secure secrets
   openssl rand -base64 32
   ```

2. **Or create secrets via kubectl**
   ```bash
   kubectl create secret generic sds-nexus-secrets \
     --from-literal=app-secret-key=$(openssl rand -base64 32) \
     --from-literal=jwt-secret-key=$(openssl rand -base64 32) \
     --from-literal=db-password=YOUR_SECURE_PASSWORD \
     -n sds-nexus
   ```

3. **Never commit real secrets** to Git!

---

## 📊 Monitoring

### Check HPA Status
```bash
kubectl get hpa -n sds-nexus
```

### View Resource Usage
```bash
kubectl top pods -n sds-nexus
kubectl top nodes
```

### Check Events
```bash
kubectl get events -n sds-nexus --sort-by='.lastTimestamp'
```

---

## 🗑️ Cleanup

### Delete All Resources
```bash
kubectl delete namespace sds-nexus
```

### Delete Specific Resources
```bash
# Delete API only
kubectl delete -f k8s/api/

# Delete database only
kubectl delete -f k8s/database/
```

---

## 🆘 Troubleshooting

### Pods Not Starting
```bash
# Check pod status
kubectl describe pod <pod-name> -n sds-nexus

# View logs
kubectl logs <pod-name> -n sds-nexus

# Check events
kubectl get events -n sds-nexus
```

### ImagePullBackOff
```bash
# Image not found locally
# Make sure you built the image:
docker build -t sds-nexus:latest -f docker/Dockerfile .

# Verify image exists
docker images | grep sds-nexus
```

### Database Connection Issues
```bash
# Check PostgreSQL is running
kubectl get pods -l app=postgresql -n sds-nexus

# Test connection
kubectl exec -it deployment/postgresql -n sds-nexus -- \
  psql -U sds_nexus_user -d sds_nexus -c "SELECT 1;"
```

---

## 🎓 Next Steps

1. ✅ Deploy to local Kubernetes (20 min)
2. ✅ Test auto-scaling
3. ✅ Practice rolling updates
4. ✅ Add Prometheus and Grafana
5. ✅ Set up Ingress controller
6. ✅ Implement CI/CD pipeline

---

## 📚 Additional Resources

- **[KUBERNETES_INTEGRATION.md](../KUBERNETES_INTEGRATION.md)** - Comprehensive Kubernetes guide
- **[QUICK_START_K8S.md](QUICK_START_K8S.md)** - Step-by-step deployment
- **[PRODUCTION_DEPLOYMENT_GUIDE.md](../PRODUCTION_DEPLOYMENT_GUIDE.md)** - Production deployment (VMs)

---

**Platform**: SDS Nexus v1.0.0  
**Kubernetes**: Compatible with v1.24+  
**Tested On**: Docker Desktop Kubernetes  
**Status**: Production Ready ✅

