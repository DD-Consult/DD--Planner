# Deployment Guide for Production (MongoDB Atlas + Kubernetes)

## Overview
This application is ready for deployment to Kubernetes with MongoDB Atlas. All necessary configurations have been implemented to support production environments.

---

## Required Environment Variables

### Backend (`/app/backend`)

**CRITICAL - Must Set:**
```bash
SECRET_KEY=<secure-random-string-min-32-chars>
MONGO_URL=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority
MONGO_DB_NAME=resource_planner
```

**Optional:**
```bash
EMERGENT_LLM_KEY=<your-emergent-key>  # For AI features
CORS_ORIGINS=https://your-domain.com  # Or * for development
```

### Frontend (`/app/frontend`)

```bash
REACT_APP_BACKEND_URL=https://your-api-domain.com
```

---

## MongoDB Atlas Configuration

### Connection String Format
```
mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority
```

### Required Atlas Settings
1. **Network Access**: Add your Kubernetes cluster IP ranges to IP whitelist
2. **Database User**: Create user with `readWrite` role on your database
3. **Replica Set**: Atlas provides this automatically
4. **TLS/SSL**: Enabled by default with `mongodb+srv://`

### Connection Settings Applied
- **Server Selection Timeout**: 5 seconds
- **Connection Timeout**: 10 seconds
- **Socket Timeout**: 30 seconds
- **Connection Pool**: Min 10, Max 50
- **Retry Writes**: Enabled
- **Write Concern**: Majority

---

## Security Features

### SECRET_KEY Validation
- ✅ **Production Check**: App will REFUSE to start if using default SECRET_KEY with Atlas
- ✅ **Error Message**: Clear error if SECRET_KEY not set properly
- ✅ **Detection**: Automatically detects Atlas connection (`mongodb+srv://` or `mongodb.net`)

### Generate Secure SECRET_KEY
```bash
# Option 1: OpenSSL
openssl rand -hex 32

# Option 2: Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Health Check Endpoints

### `/health` - Kubernetes Probes
- **Purpose**: Liveness and Readiness probes
- **Checks**: Database connectivity
- **Response**: 200 OK if healthy, 503 Service Unavailable if database unreachable
- **Usage**: 
  ```yaml
  livenessProbe:
    httpGet:
      path: /health
      port: 8001
    initialDelaySeconds: 30
    periodSeconds: 10
  readinessProbe:
    httpGet:
      path: /health
      port: 8001
    initialDelaySeconds: 10
    periodSeconds: 5
  ```

### `/api/health` - API Monitoring
- **Purpose**: External health monitoring
- **Response**: Returns status even if database is degraded
- **Usage**: For monitoring services that should never get 5xx

---

## Database Initialization

### First Deployment (New Database)
The app will automatically create collections on first use. However, you need to seed initial data:

1. **Create Admin User**:
   ```python
   # Run this after first deployment
   from pymongo import MongoClient
   import bcrypt
   
   client = MongoClient(MONGO_URL)
   db = client[MONGO_DB_NAME]
   
   # Create super admin
   admin_user = {
       "email": "admin@yourcompany.com",
       "password_hash": bcrypt.hashpw("ChangeMe123!".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
       "role": "super_admin",
       "must_change_password": True
   }
   db.users.insert_one(admin_user)
   ```

2. **Or use the seed endpoint** (if implemented):
   ```bash
   curl -X POST https://your-api/api/admin/seed-initial-data
   ```

---

## Port Configuration

- **Backend**: Binds to `0.0.0.0:8001` (Kubernetes-compatible)
- **Frontend**: Binds to `0.0.0.0:3000` (Kubernetes-compatible)

---

## Kubernetes Deployment Checklist

### Pre-Deployment
- [ ] MongoDB Atlas cluster created and accessible
- [ ] Database user created with proper permissions
- [ ] Network access configured (IP whitelist or VPC peering)
- [ ] SECRET_KEY generated (32+ character secure random string)
- [ ] Environment variables prepared
- [ ] CORS origins configured for your domain

### Deployment
- [ ] Backend service deployed with env vars
- [ ] Frontend service deployed with env vars
- [ ] Ingress configured for routing
- [ ] Health checks configured
- [ ] Resource limits set (CPU/Memory)

### Post-Deployment
- [ ] Health check returns 200 OK
- [ ] Database connection verified
- [ ] Admin user login works
- [ ] Create test project and verify CRUD operations
- [ ] Check logs for any warnings

---

## Common Issues & Solutions

### Issue: "Database unhealthy" on health check
**Cause**: Cannot connect to MongoDB Atlas
**Solutions**:
1. Verify MONGO_URL is correct
2. Check Atlas network access (IP whitelist)
3. Verify database user credentials
4. Check if cluster is paused

### Issue: "CRITICAL SECURITY ERROR: SECRET_KEY"
**Cause**: Deploying to production without setting SECRET_KEY
**Solution**: Set `SECRET_KEY` environment variable to a secure random string

### Issue: Connection timeout
**Cause**: Network latency or Atlas region mismatch
**Solutions**:
1. Deploy app in same region as Atlas cluster
2. Increase timeout values if needed (currently 5s/10s/30s)

### Issue: Write concern errors
**Cause**: Replica set majority write not achievable
**Solutions**:
1. Verify Atlas cluster has at least 3 nodes
2. Check cluster health in Atlas dashboard

---

## Monitoring Recommendations

### Metrics to Track
- Health check response time
- Database connection pool usage
- API response times
- Error rates (4xx, 5xx)
- Active user sessions

### Logging
- Backend logs to stdout (Kubernetes will capture)
- Include correlation IDs for request tracing
- Log database connection events
- Log authentication attempts

### Alerts
- Health check failures (> 2 consecutive)
- Database connection pool exhaustion
- High error rates (> 5% of requests)
- Slow query performance (> 1s)

---

## Rollback Plan

If deployment fails:
1. **Check logs**: `kubectl logs <pod-name>`
2. **Verify env vars**: `kubectl describe pod <pod-name>`
3. **Test health check**: `kubectl exec <pod-name> -- curl localhost:8001/health`
4. **Rollback**: `kubectl rollout undo deployment/<deployment-name>`

---

## Performance Tuning

### Connection Pool
Current settings (suitable for most deployments):
- Min: 10 connections
- Max: 50 connections

Adjust based on:
- **Higher traffic**: Increase max pool size
- **Limited Atlas tier**: Decrease to match tier connection limits

### Timeouts
Current settings:
- Server selection: 5s
- Connection: 10s
- Socket: 30s

Adjust if:
- **High latency network**: Increase timeouts
- **Local deployment**: Decrease for faster failure detection

---

## Testing in Production

### Smoke Tests (Run After Deployment)
```bash
# 1. Health check
curl https://your-api/health

# 2. Login test
curl -X POST https://your-api/api/auth/login \
  -d "username=admin@yourcompany.com&password=ChangeMe123!"

# 3. List projects (should return empty array initially)
curl https://your-api/api/projects \
  -H "Authorization: Bearer <token>"
```

### Load Testing (Before Production Traffic)
Use tools like:
- Apache Bench (ab)
- JMeter
- k6

Target: 100 concurrent users, <500ms response time

---

## Support

For deployment issues, collect:
1. Pod logs: `kubectl logs <pod-name> --tail=100`
2. Pod events: `kubectl describe pod <pod-name>`
3. Environment variables (sanitized)
4. Atlas cluster status
5. Network connectivity test results

---

## Version Information

- **MongoDB Driver**: motor (AsyncIOMotorClient)
- **Python**: 3.9+
- **FastAPI**: Latest
- **Kubernetes**: 1.20+
- **MongoDB Atlas**: M10+ recommended for production

---

## Quick Start Commands

```bash
# Set environment variables
export SECRET_KEY=$(openssl rand -hex 32)
export MONGO_URL="mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true&w=majority"
export MONGO_DB_NAME="resource_planner"

# Deploy to Kubernetes (example)
kubectl create secret generic app-secrets \
  --from-literal=SECRET_KEY=$SECRET_KEY \
  --from-literal=MONGO_URL=$MONGO_URL

kubectl apply -f k8s/deployment.yaml

# Check deployment
kubectl get pods
kubectl logs -f <pod-name>

# Test health
kubectl port-forward <pod-name> 8001:8001
curl http://localhost:8001/health
```

---

## Conclusion

The application is now **production-ready** with:
✅ Atlas-compatible MongoDB connection
✅ Kubernetes health checks
✅ Security validation
✅ Connection pooling and timeouts
✅ Proper error handling
✅ Environment-based configuration

Deploy with confidence! 🚀
