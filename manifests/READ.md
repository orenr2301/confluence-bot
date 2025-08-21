# CNFL-Scrapper AI Bot – Microservices Architecture & Interactions

## Overview

The CNFL-Scrapper AI Bot is built as a set of cooperating microservices, each with a distinct responsibility. This architecture enables scalable, maintainable, and modular AI-powered search and Q&A over your Confluence documentation.

---

## Microservices & Their Roles

### 1. **Ollama (LLM Model Server)**
- **Role:** Hosts and serves large language models (LLMs) such as Llama3.
- **Why Needed:** Provides the AI capabilities for answering user questions, generating text, and semantic understanding.
- **How Used:** Receives prompts from the Flask API and returns generated responses.

### 2. **ChromaDB (Vector Database)**
- **Role:** Stores vector embeddings of your Confluence documentation.
- **Why Needed:** Enables fast semantic search and retrieval of relevant documentation chunks for the LLM to use as context.
- **How Used:** Queried by the Flask API to find the most relevant documentation for a user’s question.

### 3. **Flask API (cnfl-scrap-flask)**
- **Role:** The main application logic and user interface.
- **Why Needed:** Orchestrates the workflow: receives user questions, retrieves relevant docs from ChromaDB, sends context and questions to Ollama, and returns answers to the user.
- **How Used:** Exposes browser and API routes for users and acts as the glue between Ollama, ChromaDB, and Confluence.

---

## How They Talk to Each Other

- **Flask API → ChromaDB:**  
  When a user asks a question, the Flask API queries ChromaDB to find the most relevant documentation chunks (using vector similarity search).

- **Flask API → Ollama:**  
  The Flask API sends the user’s question and the retrieved documentation context to Ollama, which generates an AI-powered answer.

- **Flask API → Confluence:**  
  On refresh or scheduled sync, the Flask API fetches documentation from Confluence, processes it, and stores embeddings in ChromaDB.

- **User → Flask API:**  
  Users interact with the system via the Flask API’s browser UI or REST endpoints.

---

## Why Each Service is Needed

| Service    | Needed For...                                                                 |
|------------|-------------------------------------------------------------------------------|
| Ollama     | Running the LLM to generate answers and perform semantic reasoning            |
| ChromaDB   | Fast, scalable semantic search over your documentation                        |
| Flask API  | Orchestrating the workflow, exposing UI/API, and integrating all components   |
| Confluence | Source of truth for your documentation                                        |

---

## Architecture Diagram

```plaintext
+-------------------+         +-------------------+         +-------------------+
|                   |         |                   |         |                   |
|    User Browser   +-------->+    Flask API      +-------->+     Ollama LLM    |
|                   |  HTTP   | (cnfl-scrap-flask)|  HTTP   |   (Model Server)  |
+-------------------+         +-------------------+         +-------------------+
         |                             |                             ^
         |                             |                             |
         |                             v                             |
         |                   +-------------------+                   |
         |                   |                   |                   |
         +------------------>+    ChromaDB       +------------------+
                             | (Vector DB)       |
                             +-------------------+
                                      |
                                      v
                             +-------------------+
                             |                   |
                             |   Confluence      |
                             | (Documentation)   |
                             +-------------------+
```

---

## Example Workflow

1. **User asks a question** in the UI (`/` route).
2. **Flask API** receives the question, queries **ChromaDB** for relevant docs.
3. **Flask API** sends the question + context to **Ollama** for an answer.
4. **Ollama** returns the answer, which is shown to the user.
5. On refresh, **Flask API** fetches docs from **Confluence**, embeds them, and stores vectors in **ChromaDB**.

---

## Summary Table

| From         | To           | Protocol | Purpose                                  |
|--------------|--------------|----------|------------------------------------------|
| User         | Flask API    | HTTP     | Ask questions, view UI                   |
| Flask API    | ChromaDB     | HTTP     | Semantic search for relevant docs        |
| Flask API    | Ollama       | HTTP     | Get AI-generated answers                 |
| Flask API    | Confluence   | HTTP(S)  | Fetch documentation for embedding        |

---

**This modular architecture ensures each component can scale, be maintained, and be upgraded independently, while providing a seamless AI-powered documentation search experience.**


# Confluence Scraper Kubernetes Deployment

## Overview
This project contains a Kubernetes deployment for a Confluence scraper application that consists of three main components:
- **Flask App** (main application) - Scrapes Confluence data
- **Ollama** - LLM inference server
- **ChromaDB** - Vector database for embeddings

## Architecture Diagram
```
[Internet] 
    ↓
[Ingress] → [Service] → [Flask App Deployment]
                            ↓ (depends on)
                       [Ollama Service] ← [Ollama Deployment]
                            ↓ (depends on)
                       [ChromaDB Service] ← [ChromaDB StatefulSet]
                            ↓ (uses)
                       [Secret (confluence-secrets)]
```

## Manifest Dependencies & Relationships

### 1. **Secret (`secret.yaml`)** 
**Used by:** `deployment.yaml`
- **Purpose:** Stores sensitive configuration data
- **Contains:**
  - `base-url`: Confluence API base URL
  - `api-token`: Confluence API authentication token
  - `space-key`: Confluence space identifier
  - `cacrt`: Corporate CA certificate for SSL verification

### 2. **Flask App Deployment (`deployment.yaml`)**
**Dependencies:**
- **Secrets:** References `confluence-secrets` for environment variables
- **Services:** Waits for and connects to:
  - `ollama-service:11434` (Ollama LLM service)
  - `chromadb-service:8000` (ChromaDB vector database)

**Key Features:**
- **Init Container:** Uses `busybox` to wait for dependent services before starting
- **Environment Variables from Secret:**
  ```yaml
  env:
  - name: CONFLUENCE_API_TOKEN
    valueFrom:
      secretKeyRef:
        name: confluence-secrets
        key: api-token
  ```
- **Volume Mounts:** Mounts CA certificate from secret for SSL verification
- **Health Checks:** Implements readiness and liveness probes

### 3. **Service (`service.yaml`)**
**Used by:** `ingress.yaml`
- **Purpose:** Exposes Flask app pods internally within the cluster
- **Selector:** Targets pods with label `app: cnfl-scrap-flask`
- **Ports:** Maps external port 80/443 to container port 5300

### 4. **Ingress (`ingress.yaml`)**
**Dependencies:**
- **Service:** Routes traffic to `cnfl-scrap-service`
- **TLS Secret:** References `cnfl-scrap-tls` (managed by cert-manager)

**Features:**
- **External Access:** Provides HTTPS access via `cnfl-scrap.nonprod-shared.lan.k8s.corp.zim.com`
- **SSL Termination:** Handles TLS certificates automatically
- **Timeouts:** Configured with extended timeouts for long-running operations

### 5. **Ollama Deployment (`ollama-deployment.yaml`)**
**Used by:** `deployment.yaml` (Flask app connects to this)
- **Components:**
  - **Deployment:** Runs Ollama LLM server
  - **PVC:** Persistent storage for model data (`ollama-pvc`)
  - **Service:** Exposes Ollama on port 11434 as `ollama-service`
- **Init Container:** Downloads LLM model (`llama3.2:1b`) before main container starts
- **Storage:** Uses PVC for persistent model storage (10Gi)

### 6. **ChromaDB StatefulSet (`chromadb-standalone.yaml`)**
**Used by:** `deployment.yaml` (Flask app connects to this)
- **Components:**
  - **StatefulSet:** Ensures stable storage and network identity
  - **Service:** Exposes ChromaDB on port 8000 as `chromadb-service`
  - **Volume Claim Template:** Provides persistent storage (20Gi)
- **Features:**
  - Persistent vector database storage
  - CORS enabled for web access
  - Stable hostname for consistent connections

## Deployment Order & Dependencies

### Required Deployment Sequence:
1. **`secret.yaml`** - Must be deployed first (contains credentials)
2. **`ollama-deployment.yaml`** - Deploy Ollama service
3. **`chromadb-standalone.yaml`** - Deploy ChromaDB service  
4. **`service.yaml`** - Create service for Flask app
5. **`deployment.yaml`** - Deploy Flask app (waits for services via init container)
6. **`ingress.yaml`** - Enable external access

### Service Communication Flow:
```
Flask App Container:
├── Reads secrets from: confluence-secrets
├── Connects to: ollama-service:11434
├── Connects to: chromadb-service:8000
└── Mounts CA cert from: confluence-secrets/cacrt

Init Container:
├── Waits for: ollama-service:11434
└── Waits for: chromadb-service:8000
```

## Environment Variables Mapping

| Variable | Source | Usage |
|----------|--------|-------|
| `CONFLUENCE_API_TOKEN` | `secret.yaml` | Authenticate with Confluence API |
| `CONFLUENCE_BASE_URL` | `secret.yaml` | Confluence server URL |
| `CONFLUENCE_SPACE_KEY` | `secret.yaml` | Target Confluence space |
| `CA_SSL` | `secret.yaml` | Corporate CA certificate |
| `OLLAMA_HOST` | Hardcoded | Points to `ollama-service:11434` |
| `CHROMADB_HOST` | Hardcoded | Points to `chromadb-service:8000` |

## Network Communication

### Internal Service Communication:
- **Flask App** → **Ollama**: `ollama-service:11434` (HTTP API calls)
- **Flask App** → **ChromaDB**: `chromadb-service:8000` (Vector storage)
- **Flask App** → **Confluence**: External HTTPS API calls

### External Access:
- **Users** → **Ingress** → **Service** → **Flask App**

## Storage Requirements

| Component | Storage Type | Size | Purpose |
|-----------|-------------|------|---------|
| Ollama | PVC | 10Gi | LLM model storage |
| ChromaDB | VolumeClaimTemplate | 20Gi | Vector database persistence |
| Flask App | Secret Volume | - | CA certificate mounting |

## Security Features

1. **Secret Management**: Sensitive data stored in Kubernetes secrets
2. **TLS Encryption**: HTTPS termination at ingress level
3. **CA Certificate**: Corporate CA for internal SSL verification
4. **Service Isolation**: ClusterIP services for internal communication only
5. **Resource Limits**: CPU and memory limits defined for all containers

## Health Monitoring

- **Readiness Probe**: Checks `/health` endpoint before accepting traffic
- **Liveness Probe**: Monitors `/` endpoint for container health
- **Init Containers**: Ensure service dependencies are ready before startup

## Quick Commands

```bash
# Deploy in correct order
kubectl apply -f config/secret.yaml
kubectl apply -f config/ollama-deployment.yaml
kubectl apply -f config/chromadb-standalone.yaml
kubectl apply -f config/service.yaml
kubectl apply -f config/deployment.yaml
kubectl apply -f config/ingress.yaml

# Check deployment status
kubectl get pods -l app=cnfl-scrap-flask
kubectl get pods -l app=ollama
kubectl get pods -l app=chromadb

# View logs
kubectl logs -l app=cnfl-scrap-flask -c ollama-flask
```

This architecture ensures high availability, proper dependency management, and secure communication between all components.

