# confluence-bot
## This project is a a learning project done due to my AI & LLM learning path to achive  MLOPS skills to my abillities as this area going to be at the hard front
## And i want to be there to be able to support and connect and do DevOps at the AI area which is MLOPS as well  
## The RAG code part was created via Copilot using Cluade Sonnaet 4 Model
## Eventually  did the wrapping and was able to fix and put logic and add crucial part that Copilot wasnt able to solve correctly
## At my role As DevOps engineer i was able to establish a full deployment and bring this app and project to live :) 
## I Only can say that i'v i learned alot during this process to become a better DevOps enigneer who is stepping into the MLOPS world 

A confluence microservice bot which is deployed over kubernetes. To question your confluence space offline wth ollama

The RAG code PART was build via Copilot - 
# CNFL-Scrapper AI Bot UI – Deployment & Usage Guide

## Overview

**CNFL-Scrapper** is an AI-powered bot UI designed to interact with LLMs (Large Language Models) using [Ollama](https://ollama.com/) as the backend model server. This guide will walk you through deploying the bot on Kubernetes, explain the deployment structure, and describe each API route so you can confidently install and operate it in your environment.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Deployment & Configuration](#deployment--configuration)
4. [Deployment Instructions](#deployment-instructions)
5. [Kubernetes Resources Explained](#kubernetes-resources-explained)
6. [Browser Routes & Usage](#browser-routes--usage)
7. [API Routes & Usage](#api-routes--usage)
8. [Troubleshooting & Tips](#troubleshooting--tips)

---

## Architecture

- **Ollama Model Server**: Hosts and serves LLMs (e.g., Llama3) via a REST API.
- **CNFL-Scrapper UI**: The user interface and API layer for interacting with the model.
- **Persistent Storage**: Ensures downloaded models and chat history are retained across pod restarts.

- **Flask App**: Provides the UI and API endpoints.
- **Ollama**: Runs the LLM (e.g., Llama3) for answering questions.
- **ChromaDB**: Stores vector embeddings of your Confluence pages for semantic search.
- **Confluence**: Source of documentation, accessed via REST API.

---

## Prerequisites

- Kubernetes cluster (v1.21+ recommended)
- `kubectl` access to your cluster
- Sufficient resources (at least 12Gi RAM, 6 CPUs for Ollama)
- [cert-manager](https://cert-manager.io/) if you plan to use TLS (optional)
- (Optional) A storage class for persistent volumes

---

## Deployment & Configuration

1. **Set Environment Variables**  
   - `CONFLUENCE_BASE_URL`: Your Confluence instance URL. (Absorbed from secret)
   - `CONFLUENCE_API_TOKEN`: API token for Confluence access.(Absorbed from secret)
   - `CONFLUENCE_SPACE_KEY`: (Optional) Limit to a specific space. (Absorbed from secret)
   - `CHROMADB_HOST`: Host:port for ChromaDB (default: `chromadb-service:8000`).
   - `OLLAMA_HOST`: Host:port for Ollama (default: `ollama-service:11434`).
   - `VERIFY_SSL`: Set to `true` or `false` for SSL verification.
   - `CA_SSL`: The ssl certificate to use if using self signerd or corporate instance. (Absorbed from secret)

2. **Deploy on Kubernetes**  
   - Use the provided `ollama-deployment.yaml` and other manifests.
   - Ensure persistent storage for models and embeddings.

3. **Start the Flask App**  
   - Run with `python app.py` or via your preferred WSGI server.
   - Default port: `5300`.

---

## Deployment Instructions

1. **Clone the Repository**

   ```sh
   git clone <your-repo-url>
   cd cnfl-scrapper/config
   ```

2. **Review and Edit the Deployment YAML**

   - Open `ollama-deployment.yaml`.
   - Adjust resource requests/limits as needed.
   - If your cluster requires a specific storage class, uncomment and set `storageClassName` in the PVC section.

3. **Apply the Deployment**

   ```sh
   kubectl apply -f ollama-deployment.yaml
   ```

4. **Verify the Deployment**

   ```sh
   kubectl get pods
   kubectl get svc
   ```

   - Ensure the `ollama` pod is running.
   - The service `ollama-service` should be available on port `11434`.

5. **Access the UI**

   - If you have an Ingress or LoadBalancer, expose the service as needed.
   - For local testing, you can port-forward:

     ```sh
     kubectl port-forward svc/ollama-service 11434:11434
     ```

   - Then access the UI/API at `http://localhost:11434`.

---

## Kubernetes Resources Explained

### 1. **Deployment**

- **Init Container (`model-downloader`)**:  
  Downloads the Llama3 model before the main container starts, ensuring the model is available on first run.
- **Main Container (`ollama`)**:  
  Runs the Ollama server, serving the LLM API on port 11434.
- **Resource Requests/Limits**:  
  Ensures the pod has enough CPU and memory for efficient model inference.

### 2. **PersistentVolumeClaim (PVC)**

- **ollama-pvc**:  
  Provides persistent storage for downloaded models and chat data.  
  - Default: 10Gi (enough for Llama3 and some extra data)
  - Adjust as needed for larger models or more history.

### 3. **Service**

- **ollama-service**:  
  Exposes the Ollama API on port 11434 within the cluster.

---
## Browser Routes & Usage

### `/`  
**Main UI page**  
- Ask questions about your Confluence documentation.
- Enter your question and get an AI-generated answer based on your docs.

---

### `/debug`  
**Debug information page**  
- Shows ChromaDB status, Confluence config, and connection test results.
- Useful for troubleshooting configuration and connectivity.

---

### `/refresh`  
**Manual data refresh**  
- Triggers a full fetch and embedding of all Confluence pages into ChromaDB.
- Use after updating Confluence content or changing config.

---

### `/test-auth`  
**Authentication test page**  
- Tests different authentication methods to Confluence.
- Helps debug token or permission issues.

---

### `/health`  
**Health check endpoint**  
- Returns a simple JSON status.
- Used for readiness/liveness probes or to check if the app is running.

---

### `/spaces`  
**List Confluence spaces**  
- Shows all spaces your token can access.
- Useful for verifying connectivity and permissions.

---

### `/debug-chromadb`  
**ChromaDB debug page**  
- Shows ChromaDB client type, collections, and counts.
- Useful for diagnosing vector DB issues.

---

### `/test-fetch-strategy`  
**Fetch strategy test**  
- Tests the page fetching logic from Confluence (does not store data).
- Shows page count, sample IDs, and a sample page.

---

### `/test-space`  
**Test configured space**  
- Checks if the configured space exists and fetches a sample of pages.
- Shows space info and sample page titles/IDs.

---

### `/docs`  
**Documentation page**  
- Shows live metrics (number of chunks/pages) and explains the app’s architecture and usage.
- Good starting point for new users or admins.

---

## API/Debug Routes

- All debug/test routes return raw data in `<pre>` format for easy inspection.
- The `/` and `/docs` routes are user-friendly HTML pages.

---
## API Routes & Usage

Below are the main API routes exposed by the Ollama server (and thus available to the CNFL-Scrapper UI):

### 1. **POST `/api/chat`**

- **Purpose**: Send a chat prompt to the LLM and receive a response.
- **Request Body**:
  ```json
  {
    "model": "llama3.2:1b",
    "messages": [
      {"role": "user", "content": "Hello, who are you?"}
    ]
  }
  ```
- **Response**:
  ```json
  {
    "id": "chatcmpl-xyz",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "llama3.2:1b",
    "choices": [
      {
        "message": {
          "role": "assistant",
          "content": "I'm an AI language model..."
        }
      }
    ]
  }
  ```

### 2. **POST `/api/generate`**

- **Purpose**: Generate text from a prompt (single-turn completion).
- **Request Body**:
  ```json
  {
    "model": "llama3.2:1b",
    "prompt": "Write a poem about Kubernetes."
  }
  ```
- **Response**:
  ```json
  {
    "response": "Kubernetes, clusters so bright..."
  }
  ```

### 3. **GET `/api/models`**

- **Purpose**: List all available models on the Ollama server.
- **Response**:
  ```json
  {
    "models": [
      {"name": "llama3.2:1b", "size": "5GB"},
      ...
    ]
  }
  ```

### 4. **POST `/api/pull`**

- **Purpose**: Download a new model from Ollama's registry.
- **Request Body**:
  ```json
  {
    "name": "llama3.2:1b"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success"
  }
  ```

### 5. **GET `/api/health`**

- **Purpose**: Health check endpoint for readiness/liveness probes.

---

## Troubleshooting & Tips

- **Model Download Issues**:  
  If the pod fails to start, check logs for model download errors. Ensure your cluster has internet access or pre-load models into the PVC.

- **Resource Limits**:  
  If you see OOMKilled or CPU throttling, increase the resource requests/limits in the deployment.

- **Persistent Storage**:  
  Make sure your PVC is bound and has enough space for the models you plan to use.

- **Exposing the Service**:  
  For production, use an Ingress or LoadBalancer to expose the Ollama API/UI securely.

- **Security**:  
  Consider enabling authentication or network policies to restrict access to the Ollama API in sensitive environments.

---

**Happy
