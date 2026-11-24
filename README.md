# HRPulse — Complete Step-by-Step Guide

**BITS Scalable Services Assignment-2 | Deadline: 5 December 2026**

Domain: SAP SuccessFactors HR/HCM  
Core Principle: **Single Responsibility Principle** — each service owns one bounded context with its own data store.

---

## Prerequisites — Install These First

```bash
# macOS (Homebrew)
brew install docker
brew install minikube
brew install kubectl

# Verify
docker --version        # Docker 24+
minikube version        # v1.32+
kubectl version --client
```

Create a Docker Hub account at hub.docker.com if you don't have one.
Your Docker Hub username is used throughout — replace `YOUR_DOCKER_USERNAME` everywhere below.

---

## Project Structure

```
hrpulse/
├── services/
│   ├── employee-service/     # Port 8001 — Employee profiles + Org Chart
│   ├── leave-service/        # Port 8002 — Leave requests + RabbitMQ publisher
│   ├── payroll-service/      # Port 8003 — Payroll + Circuit Breaker + RabbitMQ consumer
│   └── performance-service/  # Port 8004 — Performance reviews + RabbitMQ publisher
├── gateway/
│   └── nginx.conf
├── k8s/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── employee-service/deployment.yaml
│   ├── leave-service/deployment.yaml     ← 2 replicas (self-healing demo)
│   ├── payroll-service/deployment.yaml   ← circuit breaker here
│   ├── performance-service/deployment.yaml
│   ├── databases/postgres.yaml
│   ├── databases/mongodb.yaml
│   ├── rabbitmq/rabbitmq.yaml
│   └── nginx/gateway.yaml
├── docker-compose.yml
└── .env.example
```

---

## PHASE 1 — Local Development Setup

### Step 1.1 — Copy the .env file

```bash
cd hrpulse
cp .env.example .env
```

Open `.env` and add your Docker Hub username:
```
DOCKER_USERNAME=your_dockerhub_username
```

### Step 1.2 — Run the full application locally

```bash
docker compose up --build
```

This single command:
- Builds all 4 service images
- Starts 3 PostgreSQL instances, MongoDB, RabbitMQ, 4 services, and NGINX
- Applies health-based start order (databases start → services start → gateway starts)

Wait ~60 seconds for everything to be healthy.

### Step 1.3 — Verify all services are healthy

Open a new terminal and run:

```bash
# API Gateway
curl http://localhost:8080/health

# Individual services
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health

# RabbitMQ management UI
open http://localhost:15672    # login: guest / guest
```

### Step 1.4 — Test the full flow

```bash
# 1. Create an employee
curl -s -X POST http://localhost:8080/api/employees \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Rahul Sharma",
    "email": "rahul@hrpulse.com",
    "department": "Engineering",
    "designation": "Software Engineer",
    "salary_grade": "L3",
    "bank_account": "HDFC-001234",
    "joining_date": "2024-01-15"
  }' | python3 -m json.tool

# Save the returned "id" field — use it in commands below as EMPLOYEE_ID

EMPLOYEE_ID="paste-id-here"

# 2. View org chart
curl -s http://localhost:8080/api/org-chart | python3 -m json.tool

# 3. Request leave (sync call: Leave Service → Employee Service)
curl -s -X POST http://localhost:8080/api/leave/request \
  -H "Content-Type: application/json" \
  -d "{
    \"employee_id\": \"$EMPLOYEE_ID\",
    \"leave_type\": \"annual\",
    \"start_date\": \"2026-12-10\",
    \"end_date\": \"2026-12-12\",
    \"reason\": \"Family vacation\"
  }" | python3 -m json.tool

# Save the leave "id" as LEAVE_ID
LEAVE_ID="paste-leave-id-here"

# 4. Approve leave (this publishes async event to RabbitMQ → Payroll receives it)
curl -s -X PUT "http://localhost:8080/api/leave/request/$LEAVE_ID/approve" | python3 -m json.tool

# Check RabbitMQ → the leave_approved queue should now be consumed by payroll-service

# 5. Create a performance review (async: Performance → Payroll via RabbitMQ)
curl -s -X POST http://localhost:8080/api/reviews \
  -H "Content-Type: application/json" \
  -d "{
    \"employee_id\": \"$EMPLOYEE_ID\",
    \"reviewer_id\": \"manager-001\",
    \"period\": \"Q3-2026\",
    \"goals\": \"Deliver 3 features, improve test coverage\",
    \"achievements\": \"Delivered 4 features, coverage 80%\"
  }" | python3 -m json.tool

REVIEW_ID="paste-review-id-here"

# 6. Submit and rate the review (this publishes performance_rated to RabbitMQ)
curl -s -X PUT "http://localhost:8080/api/reviews/$REVIEW_ID/submit" | python3 -m json.tool
curl -s -X PUT "http://localhost:8080/api/reviews/$REVIEW_ID/rate" \
  -H "Content-Type: application/json" \
  -d '{"rating": 5}' | python3 -m json.tool

# 7. Run payroll (uses circuit breaker to call Employee Service)
curl -s -X POST http://localhost:8080/api/payroll/run \
  -H "Content-Type: application/json" \
  -d "{
    \"employee_id\": \"$EMPLOYEE_ID\",
    \"month\": 11,
    \"year\": 2026
  }" | python3 -m json.tool

# View payslip
curl -s "http://localhost:8003/payroll/$EMPLOYEE_ID" | python3 -m json.tool
```

---

## PHASE 2 — Docker Hub Push

### Step 2.1 — Login to Docker Hub

```bash
docker login
# Enter your Docker Hub username and password
```

### Step 2.2 — Tag and push all images

Replace `YOUR_DOCKER_USERNAME` with your actual Docker Hub username.

```bash
export DOCKER_USERNAME=YOUR_DOCKER_USERNAME

# Build with the correct tags
docker build -t $DOCKER_USERNAME/employee-service:1.0.0 ./services/employee-service
docker build -t $DOCKER_USERNAME/leave-service:1.0.0 ./services/leave-service
docker build -t $DOCKER_USERNAME/payroll-service:1.0.0 ./services/payroll-service
docker build -t $DOCKER_USERNAME/performance-service:1.0.0 ./services/performance-service

# Push all 4 images
docker push $DOCKER_USERNAME/employee-service:1.0.0
docker push $DOCKER_USERNAME/leave-service:1.0.0
docker push $DOCKER_USERNAME/payroll-service:1.0.0
docker push $DOCKER_USERNAME/performance-service:1.0.0

echo "All images pushed to Docker Hub"
```

Verify at: https://hub.docker.com/u/YOUR_DOCKER_USERNAME

### Step 2.3 — Update Kubernetes manifests with your image names

```bash
# Replace DOCKER_USERNAME placeholder in all k8s deployment files
sed -i '' "s/DOCKER_USERNAME/$DOCKER_USERNAME/g" \
  k8s/employee-service/deployment.yaml \
  k8s/leave-service/deployment.yaml \
  k8s/payroll-service/deployment.yaml \
  k8s/performance-service/deployment.yaml

# Verify
grep "image:" k8s/employee-service/deployment.yaml
```

---

## PHASE 3 — Kubernetes Deployment

### Step 3.1 — Start Minikube

```bash
minikube start --memory=4096 --cpus=4
minikube status
```

### Step 3.2 — Deploy everything to Kubernetes

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Apply secrets and config
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml

# 3. Deploy databases (PostgreSQL × 3 + MongoDB)
kubectl apply -f k8s/databases/postgres.yaml
kubectl apply -f k8s/databases/mongodb.yaml

# 4. Deploy RabbitMQ
kubectl apply -f k8s/rabbitmq/rabbitmq.yaml

# 5. Wait for databases to be ready (~60s)
kubectl get pods -n hrpulse -w
# Press Ctrl+C when all database pods show Running

# 6. Deploy all 4 services
kubectl apply -f k8s/employee-service/deployment.yaml
kubectl apply -f k8s/leave-service/deployment.yaml
kubectl apply -f k8s/payroll-service/deployment.yaml
kubectl apply -f k8s/performance-service/deployment.yaml

# 7. Deploy NGINX gateway
kubectl apply -f k8s/nginx/gateway.yaml

# 8. Check all pods
kubectl get pods -n hrpulse
```

### Step 3.3 — Verify pods are running

```bash
kubectl get pods -n hrpulse
kubectl get services -n hrpulse
kubectl get deployments -n hrpulse
```

Expected output:
```
NAME                      READY   STATUS    RESTARTS
employee-service-xxx      1/1     Running   0
leave-service-xxx         1/1     Running   0    ← pod 1 of 2
leave-service-yyy         1/1     Running   0    ← pod 2 of 2 (2 replicas!)
payroll-service-xxx       1/1     Running   0
performance-service-xxx   1/1     Running   0
employee-db-xxx           1/1     Running   0
leave-db-xxx              1/1     Running   0
payroll-db-xxx            1/1     Running   0
mongo-xxx                 1/1     Running   0
rabbitmq-xxx              1/1     Running   0
gateway-xxx               1/1     Running   0
```

### Step 3.4 — Get the Minikube URL and test

```bash
# Get the gateway URL
minikube service gateway -n hrpulse --url

# Or use port-forward for direct access
kubectl port-forward service/gateway 8080:80 -n hrpulse &

# Test
curl http://localhost:8080/health
```

---

## PHASE 4 — Failure Demonstrations (Screenshot Everything!)

### Demo A — Circuit Breaker

The circuit breaker is in Payroll Service. It calls Employee Service via REST.
When Employee Service is down 5 times in a row, the circuit "opens" and returns a fallback.

**Configuration:** fail_max=5, reset_timeout=30 seconds

```bash
# 1. Confirm system is healthy
curl http://localhost:8003/circuit-breaker/status
# Expected: {"state": "closed", ...}

# 2. Take screenshot of healthy state

# 3. Scale down Employee Service to 0 (simulates it going down)
kubectl scale deployment employee-service --replicas=0 -n hrpulse

# 4. Send 6 payroll requests to trip the breaker
for i in {1..6}; do
  echo "--- Request $i ---"
  curl -s -X POST http://localhost:8003/payroll/run \
    -H "Content-Type: application/json" \
    -d '{"employee_id": "test-123", "month": 11, "year": 2026}'
  echo ""
  sleep 1
done

# 5. Check circuit breaker state — should now be OPEN
curl http://localhost:8003/circuit-breaker/status
# Expected: {"state": "open", "fail_count": 5, ...}

# 6. Run payroll again — should return FALLBACK response (not an error)
curl -s -X POST http://localhost:8003/payroll/run \
  -H "Content-Type: application/json" \
  -d '{"employee_id": "test-fallback", "month": 11, "year": 2026}' \
  | python3 -m json.tool
# Expected: payroll processed with fallback salary grade L2

# 7. Take screenshot of open breaker state

# 8. Restore Employee Service
kubectl scale deployment employee-service --replicas=1 -n hrpulse

# 9. Wait 30 seconds (reset_timeout), then check
sleep 30
curl http://localhost:8003/circuit-breaker/status
# Expected: {"state": "closed"} — recovered!

# 10. Take screenshot of recovery
```

**What to show in report:**
- State: closed → open → closed
- Fallback: used L2 salary grade from defaults instead of crashing
- Configured: fail_max=5, timeout=5s per request, reset_timeout=30s

---

### Demo B — Kubernetes Self-Healing

Leave Service has 2 replicas. When you delete one pod, Kubernetes (via ReplicaSet) automatically creates a replacement.

```bash
# Terminal 1 — Watch pods continuously
kubectl get pods -n hrpulse -w

# Terminal 2 — Get a leave-service pod name
kubectl get pods -n hrpulse | grep leave-service

# Note the pod name, e.g.: leave-service-7d9f8b-xkqmz
LEAVE_POD=$(kubectl get pods -n hrpulse -l app=leave-service -o jsonpath='{.items[0].metadata.name}')
echo "Will delete: $LEAVE_POD"

# Terminal 2 — Delete the pod
kubectl delete pod $LEAVE_POD -n hrpulse

# Terminal 1 — Watch Terminal 1!
# You will see:
# leave-service-7d9f8b-xkqmz   1/1     Terminating    0          5m
# leave-service-7d9f8b-newpod  0/1     Pending        0          0s
# leave-service-7d9f8b-newpod  0/1     ContainerCreating  0      0s
# leave-service-7d9f8b-newpod  1/1     Running        0          8s

# Terminal 2 — Confirm requests still work while pod was deleted
curl http://localhost:8002/health
```

**Screenshot this sequence in Terminal 1 — it's your evidence.**

**Explanation for report (3-4 lines):**
"The Deployment's ReplicaSet continuously reconciles the actual pod count against the desired count (replicas: 2). When we deleted one pod, the ReplicaSet detected the count dropped to 1 and immediately scheduled a new pod. The scheduler placed it on an available node and Kubernetes restarted the container automatically. Requests continued flowing to the surviving replica during the restart, demonstrating zero-downtime resilience."

---

## PHASE 5 — Report Checklist

Your report must be 10–12 pages covering these 8 sections:

### Section 1 — Domain and Objectives
- Domain: SAP SuccessFactors HR/HCM (you work at SAP)
- Problem: Monolithic HR systems are slow to scale; payroll, leave, and performance reviews have different scaling needs
- Objective: Build HRPulse as a 4-service microservices application

### Section 2 — Core Principle
"**Single Responsibility Principle (SRP)** — each service owns exactly one business domain and its own data store. In an HR system, payroll, leave, performance, and employee management have distinct domain logic, different scaling requirements, and different failure modes. SRP prevents cascading failures and allows each domain to evolve independently. Demonstrated by: 4 separate services, 4 separate databases, no shared schema."

### Section 3 — Architecture Diagram + Tables

**Service Table:**

| Service | Responsibility | Tech Stack | Data Store | Key Endpoints |
|---------|---------------|------------|-----------|---------------|
| Employee | Manages profiles, org chart, onboarding status | Python/FastAPI | PostgreSQL 15 | POST /employees, GET /org-chart, GET /health |
| Leave | Handles leave requests, approvals, balance tracking | Python/FastAPI + pika | PostgreSQL 15 | POST /leave/request, PUT /leave/request/{id}/approve, GET /health |
| Payroll | Computes salary, deductions, bonuses via circuit breaker | Python/FastAPI + pybreaker + pika | PostgreSQL 15 | POST /payroll/run, GET /payslip/{id}, GET /health |
| Performance | Manages review cycles and ratings | Python/FastAPI + motor | MongoDB 7 | POST /reviews, PUT /reviews/{id}/rate, GET /health |

**Communication Table:**

| From → To | Style | Sync/Async | Why | Failure Behavior |
|-----------|-------|-----------|-----|-----------------|
| Leave → Employee | REST | Sync | Must verify employee exists before accepting leave | Returns 503 if employee service unreachable |
| Payroll → Employee | REST + Circuit Breaker | Sync | Needs salary grade for computation | Fallback: use L2 grade defaults |
| Leave → Payroll | RabbitMQ queue | Async | Leave deduction happens independently of approval | Message is durable; retried if Payroll is down |
| Performance → Payroll | RabbitMQ queue | Async | Bonus calculation can happen after review is complete | Message is durable; retried if Payroll is down |

**Architectural Components:**

| Component | Tool | Demonstrated By |
|-----------|------|----------------|
| API Gateway | NGINX | All traffic enters via port 8080; routes to 4 upstreams by path prefix |
| Message Queue | RabbitMQ 3.13 | leave_approved queue (Leave→Payroll) and performance_rated queue (Performance→Payroll) |
| Circuit Breaker | pybreaker | Payroll→Employee: opens after 5 failures, 30s reset, fallback response |
| Service Registry | Kubernetes DNS | Services discover each other by name (employee-service, leave-service, etc.) |

### Section 4 — Architecture Decisions

**Decision 1: Why Python/FastAPI over Spring Boot for all services**
Spring Boot with resilience4j is the canonical circuit breaker choice, but setting up 4 Spring Boot services would take 4× longer with more boilerplate. pybreaker provides identical circuit breaker semantics in Python. FastAPI's async support handles concurrent requests efficiently. This is a valid production choice — Netflix, Uber, and Lyft all use Python microservices.

**Decision 2: Why RabbitMQ over Kafka for async messaging**
Kafka excels at high-throughput event streaming (millions of events/sec), but adds operational complexity (Zookeeper/KRaft, partition management). For HR workloads (hundreds of leave/payroll events per day), RabbitMQ's simpler publish-subscribe model is correct. Durable queues ensure messages survive broker restarts.

**Decision 3: Why MongoDB for Performance Service, not PostgreSQL**
Performance reviews have flexible, schema-evolving structure (goals, achievements, competency ratings vary by quarter and role level). MongoDB's document model fits this naturally without migrations. The other 3 services use PostgreSQL because their schemas are stable and they benefit from relational constraints (foreign keys, transactions).

### Section 5 — Docker Section
(Show your Dockerfiles, docker-compose.yml, before/after table, registry screenshots)

Before/After Docker Table:

| Aspect | Without Docker | With Docker |
|--------|---------------|------------|
| Setup | Install Python 3.12, PostgreSQL 15, MongoDB 7, RabbitMQ 3 manually on each machine. ~45 minutes | docker compose up --build: ~3 minutes |
| Dependencies | Python version conflicts; psycopg2 compilation issues on some OSes | Each service isolated in its own container |
| Start order | Start each process manually, remembering to start DBs first | Compose handles health-based order automatically |
| Consistency | "Works on my machine" but fails on team member's Windows machine | Same image in Compose (dev) and Kubernetes (prod) |
| Steps and time | 12+ manual steps, ~45 minutes | 1 command, ~3 minutes measured |

### Sections 6, 7, 8 — Kubernetes, Failure Demo, Conclusion
Use the commands and outputs from Phases 3 and 4 above with screenshots.

---

## Quick Reference — All Commands

```bash
# Start local dev
docker compose up --build

# Stop local dev
docker compose down -v

# Push to Docker Hub
docker push YOUR_USERNAME/employee-service:1.0.0
docker push YOUR_USERNAME/leave-service:1.0.0
docker push YOUR_USERNAME/payroll-service:1.0.0
docker push YOUR_USERNAME/performance-service:1.0.0

# Deploy to Kubernetes (all at once)
kubectl apply -f k8s/namespace.yaml -f k8s/secret.yaml -f k8s/configmap.yaml
kubectl apply -f k8s/databases/ -f k8s/rabbitmq/
kubectl apply -f k8s/employee-service/ -f k8s/leave-service/ \
              -f k8s/payroll-service/ -f k8s/performance-service/
kubectl apply -f k8s/nginx/

# Check status
kubectl get all -n hrpulse

# Access gateway
kubectl port-forward service/gateway 8080:80 -n hrpulse

# Delete everything (clean slate)
kubectl delete namespace hrpulse

# Circuit breaker check
curl http://localhost:8003/circuit-breaker/status

# Self-healing demo
kubectl get pods -n hrpulse -w &
kubectl delete pod $(kubectl get pods -n hrpulse -l app=leave-service -o jsonpath='{.items[0].metadata.name}') -n hrpulse
```
