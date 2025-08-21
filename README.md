# confluence-bot
A confluence microservice bot which is deployed over kubernetes. To question your confluence space offline wth ollama


# CNFL-Scrapper AI Bot UI – Deployment & Usage Guide

## Overview

**CNFL-Scrapper** is an AI-powered bot UI designed to interact with LLMs (Large Language Models) using [Ollama](https://ollama.com/) as the backend model server. This guide will walk you through deploying the bot on Kubernetes, explain the deployment structure, and describe each API route so you can confidently install and operate it in your environment.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Deployment Instructions](#deployment-instructions)
4. [Kubernetes Resources Explained](#kubernetes-resources-explained)
5. [API Routes & Usage](#api-routes--usage)
6. [Troubleshooting & Tips](#troubleshooting--tips)

---

## Architecture

- **Ollama Model Server**: Hosts and serves LLMs (e.g., Llama3) via a REST API.
- **CNFL-Scrapper UI**: The user interface and API layer for interacting with the model.
- **Persistent Storage**: Ensures downloaded models and chat history are retained across pod restarts.

---

## Prerequisites

- Kubernetes cluster (v1.21+ recommended)
- `kubectl` access to your cluster
- Sufficient resources (at least 12Gi RAM, 6 CPUs for Ollama)
- [cert-manager](https://cert-manager.io/) if you plan to use TLS (optional)
- (Optional) A storage class for persistent volumes

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

## Contact & Support

For questions, issues, or feature requests, please open an issue in the repository or contact the maintainers.

---

**Happy
