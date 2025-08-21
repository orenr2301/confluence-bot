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
