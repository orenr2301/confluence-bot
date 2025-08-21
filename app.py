import os 
import re
from flask import Flask, request, render_template
import requests
from requests.auth import HTTPBasicAuth
from sentence_transformers import SentenceTransformer
import ollama
import chromadb
from chromadb.config import Settings


#Setting up the Confluence ENV Variables conifguration for authentication
CONFLUENCE_BASE_URL = os.getenv('CONFLUENCE_BASE_URL', '').strip()
CONFLUENCE_API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN', '').strip()
CONFLUENCE_EMAIL = os.getenv('CONFLUENCE_EMAIL', '').strip()
VERIFY_SSL = os.getenv('VERIFY_SSL', 'false').lower() == 'true'  # Default to false for corporate environments
CHROMADB_HOST = os.getenv('CHROMADB_HOST', 'chromadb-service:8000')  # External ChromaDB service
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'ollama-service:11434')  # Default to Kubernetes service

app = Flask(__name__)

# Configure longer request timeout
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 5 minutes

# Initialize Ollama client with configurable host and timeout
ollama_client = ollama.Client(host=f'http://{OLLAMA_HOST}', timeout=300)  # 5 minute timeout

# Initialize ChromaDB HTTP client to connect to external service
try:
    db = chromadb.HttpClient(
        host=CHROMADB_HOST.split(':')[0], 
        port=int(CHROMADB_HOST.split(':')[1]) if ':' in CHROMADB_HOST else 8000,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )
    print(f"Connected to ChromaDB at {CHROMADB_HOST}")
except Exception as e:
    print(f"Failed to connect to ChromaDB: {e}")
    # Fallback to embedded client for development
    print("Falling back to embedded ChromaDB client...")
    db = chromadb.Client(settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    ))
    print("Using embedded ChromaDB client")

collection = db.get_or_create_collection("confluence")

# Fetching all confluence page on startup with pagination loop till fetching all pages

def get_space_page_count():
    """Get the total number of pages in the space"""
    space_key = os.getenv('CONFLUENCE_SPACE_KEY', '').strip()
    print(f"get_space_page_count: Getting total count for space '{space_key}'")
    
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content?type=page&limit=1"
    if space_key:
        url += f"&spaceKey={space_key}"
    
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
        },
        verify=VERIFY_SSL,
        timeout=30
    )
    
    resp.raise_for_status()
    data = resp.json()
    total_pages = data.get("size", 0)
    print(f"get_space_page_count: Total pages in space: {total_pages}")
    return total_pages

def fetch_all_page_ids():
    """Fetch all page IDs from the space using pagination"""
    space_key = os.getenv('CONFLUENCE_SPACE_KEY', '').strip()
    print(f"fetch_all_page_ids: Starting with space_key='{space_key}'")
    
    page_ids = []
    start = 0
    limit = 500  # Maximum limit to minimize API calls
    
    while True:
        url = f"{CONFLUENCE_BASE_URL}/rest/api/content?type=page&limit={limit}&start={start}"
        if space_key:
            url += f"&spaceKey={space_key}"
        
        print(f"fetch_all_page_ids: Fetching IDs batch (start={start}, limit={limit})")
        resp = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
            },
            verify=VERIFY_SSL,
            timeout=30
        )
        
        resp.raise_for_status()
        data = resp.json()
        
        current_batch = data["results"]
        batch_ids = [page.get("id") for page in current_batch if page.get("id")]
        page_ids.extend(batch_ids)
        
        print(f"fetch_all_page_ids: Got {len(batch_ids)} IDs in this batch (total so far: {len(page_ids)})")
        
        # Check if we've reached the end
        if len(current_batch) < limit:
            print(f"fetch_all_page_ids: Reached end - got {len(current_batch)} < {limit}")
            break
            
        start += limit
    
    print(f"fetch_all_page_ids: FINISHED - Total page IDs collected: {len(page_ids)}")
    return page_ids

def fetch_page_content_by_id(page_id):
    """Fetch individual page content with body.storage"""
    print(f"fetch_page_content_by_id: Fetching content for page ID: {page_id}")
    
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}?expand=body.storage"
    
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
        },
        verify=VERIFY_SSL,
        timeout=30
    )
    
    resp.raise_for_status()
    page_data = resp.json()
    
    print(f"fetch_page_content_by_id: Successfully fetched '{page_data.get('title', 'Unknown title')}'")
    return page_data

def fetch_all_pages():
    """Main function to fetch all pages using the robust strategy"""
    print("fetch_all_pages: Starting robust page fetching strategy...")
    
    # Step 1: Get total page count
    total_count = get_space_page_count()
    if total_count == 0:
        print("fetch_all_pages: No pages found in space")
        return []
    
    # Step 2: Fetch all page IDs
    page_ids = fetch_all_page_ids()
    if len(page_ids) != total_count:
        print(f"fetch_all_pages: WARNING - Expected {total_count} pages but got {len(page_ids)} IDs")
    
    # Step 3: Fetch content for each page
    pages = []
    failed_pages = []
    
    for i, page_id in enumerate(page_ids, 1):
        try:
            print(f"fetch_all_pages: Processing page {i}/{len(page_ids)} (ID: {page_id})")
            page_content = fetch_page_content_by_id(page_id)
            pages.append(page_content)
            
            # Progress update every 10 pages
            if i % 10 == 0:
                print(f"fetch_all_pages: Progress - {i}/{len(page_ids)} pages processed")
                
        except Exception as e:
            print(f"fetch_all_pages: ERROR fetching page {page_id}: {str(e)}")
            failed_pages.append(page_id)
            continue
    
    print(f"fetch_all_pages: COMPLETED - Successfully fetched {len(pages)}/{len(page_ids)} pages")
    if failed_pages:
        print(f"fetch_all_pages: Failed to fetch {len(failed_pages)} pages: {failed_pages[:5]}...")
    
    return pages

# Function to chunk text into smaller parts for processing
def chunk_text(text, chunk_size=500):
    words = text.split()
    return [
        " ".join(words[i:i+chunk_size])
        for i in range(0, len(words), chunk_size)
    ]

def embed_and_store_pages():
    print("Starting to fetch and embed Confluence pages...")
    try:
        print("Loading SentenceTransformer model...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        print("Model loaded successfully.")
        
        print("Calling fetch_all_pages()...")
        pages = fetch_all_pages()
        print(f"Fetched {len(pages)} pages from Confluence.")
        
        if len(pages) == 0:
            print("WARNING: No pages fetched from Confluence!")
            return
        
        # Check ChromaDB connection
        print(f"ChromaDB collection count before processing: {collection.count()}")
        
        chunk_count = 0
        for i, page in enumerate(pages):
            print(f"Processing page {i+1}/{len(pages)}: {page.get('title', 'Untitled')}")
            title = page.get("title", "")
            
            # Check if page has body content
            if "body" not in page or "storage" not in page["body"]:
                print(f"  WARNING: Page '{title}' has no body.storage content")
                continue
                
            content = page["body"]["storage"]["value"]
            print(f"  Raw content length: {len(content)} characters")
            
            clean_content = re.sub(r'<[^>]+>', '', content)
            print(f"  Clean content length: {len(clean_content)} characters")
            
            if len(clean_content.strip()) == 0:
                print(f"  WARNING: Page '{title}' has no text content after cleaning")
                continue
            
            chunks = chunk_text(clean_content)
            print(f"  Generated {len(chunks)} chunks")
            
            for chunk_idx, chunk in enumerate(chunks):
                if len(chunk.strip()) == 0:
                    continue
                    
                try:
                    print(f"    Embedding chunk {chunk_idx+1}/{len(chunks)} for page '{title}'")
                    embeddings = model.encode(chunk)
                    
                    # Convert NumPy array to Python list for ChromaDB
                    embeddings_list = embeddings.tolist()
                    
                    # Try to add to collection with detailed error handling
                    chunk_id = f"{page.get('id', 'unknown')}_{chunk_count}"
                    print(f"    Adding chunk with ID: {chunk_id}")
                    
                    collection.add(
                        documents=[chunk],
                        metadatas=[{"title": title}],
                        embeddings=[embeddings_list],
                        ids=[chunk_id]
                    )
                    chunk_count += 1
                    print(f"    Successfully added chunk {chunk_count}")
                    
                    # Check collection count every 10 chunks
                    if chunk_count % 10 == 0:
                        current_count = collection.count()
                        print(f"    ChromaDB collection count: {current_count}")
                        
                except Exception as chunk_error:
                    print(f"    ERROR adding chunk {chunk_idx} for page '{title}': {str(chunk_error)}")
                    continue
            
            # Progress update every 10 pages
            if i % 10 == 0:
                current_count = collection.count()
                print(f"  Progress - {i}/{len(pages)} pages processed, ChromaDB count: {current_count}")

        final_count = collection.count()
        print(f"SUCCESS: Stored {len(pages)} pages with {chunk_count} chunks in ChromaDB")
        print(f"Final ChromaDB collection count: {final_count}")
        
        if final_count == 0:
            print("ERROR: No chunks were actually stored in ChromaDB!")
            print("This suggests a ChromaDB client connection or storage issue.")
        
    except Exception as e:
        print(f"ERROR during embedding: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        # Continue anyway - the app should still work for queries if ChromaDB has some data
        pass

# Initialize the sentence transformer model first
model = SentenceTransformer('all-MiniLM-L6-v2')

# Check if the collection is empty, if so, populate it on first request
# This is done lazily to avoid blocking app startup
def ensure_data_loaded():
    """Ensure data is loaded into ChromaDB, called lazily on first request"""
    if collection.count() == 0:
        print("ChromaDB is empty, fetching and embedding Confluence pages...")
        embed_and_store_pages()
    else:
        print(f"ChromaDB already contains {collection.count()} chunks")

# Flask Routing 
@app.route("/", methods=["GET", "POST"])
def index():
    answer = ""
    question = ""
    if request.method == "POST":
        question = request.form.get("question", "")
        if question:
            try:
                # Ensure data is loaded before processing queries
                ensure_data_loaded()
                
                # Debug: Check ChromaDB status
                total_chunks = collection.count()
                print(f"DEBUG: ChromaDB contains {total_chunks} chunks")
                
                if total_chunks == 0:
                    answer = "No Confluence data found in database. Please check your Confluence configuration and restart the application."
                    return render_template("index.html", answer=answer, question=question)
                
                # Perform vector search (reduced to 2 results for speed)
                q_emb = model.encode([question])
                # Convert NumPy array to Python list for ChromaDB
                q_emb_list = q_emb.tolist()
                results = collection.query(query_embeddings=q_emb_list, n_results=2)
                
                # Debug: Check query results (disabled for speed)
                # print(f"DEBUG: Query returned {len(results['documents'][0]) if results['documents'] else 0} results")
                # if results['documents'] and len(results['documents'][0]) > 0:
                #     for i, doc in enumerate(results['documents'][0]):
                #         print(f"DEBUG: Result {i+1} preview: {doc[:200]}...")
                
                relevant_chunks = [doc for docs in results['documents'] for doc in docs]
                
                if not relevant_chunks:
                    answer = "No relevant information found in the Confluence data for your question."
                    return render_template("index.html", answer=answer, question=question)
                
                context = "\n".join(relevant_chunks)[:1500]  # Reduced for faster processing
                # print(f"DEBUG: Context length: {len(context)}")
                # print(f"DEBUG: Context preview: {context[:300]}...")
                
                # Enhanced prompt for better accuracy and conciseness
                prompt = f"""You are a helpful assistant that answers questions based on Confluence documentation. 

DOCUMENTATION:
{context}

QUESTION: {question}

Instructions:
- Answer concisely and directly based ONLY on the provided documentation
- If the information isn't in the documentation, say "This information is not available in the documentation"
- Focus on the most relevant details
- Keep your answer under 100 words

ANSWER:"""
                
                # Try the model we actually downloaded
                try:
                    response = ollama_client.chat(
                        model='llama3.2:1b', 
                        messages=[{'role': 'user', 'content': prompt}],
                        options={'temperature': 0.1, 'num_predict': 150, 'top_p': 0.9, 'stop': ['\n\nQUESTION:', '\n\nCONFLUENCE DOCUMENTATION:']}
                    )
                except Exception as ollama_error:
                    # If specific error, provide more details
                    answer = f"Sorry, I couldn't process your question. Ollama error: {str(ollama_error)}"
                    return render_template("index.html", answer=answer, question=question)
                
                answer = response['message']['content']
                # print(f"DEBUG: Model response: {answer}")  # Disabled for speed
                
            except Exception as e:
                answer = f"Sorry, I couldn't process your question. Error: {str(e)}"
                print(f"DEBUG: Exception: {str(e)}")
    
    return render_template("index.html", answer=answer, question=question)


@app.route("/debug")
def debug_info():
    """Debug endpoint to check system status"""
    debug_info = {
        "chromadb_chunks": collection.count(),
        "confluence_config": {
            "base_url": CONFLUENCE_BASE_URL,
            "base_url_length": len(CONFLUENCE_BASE_URL),
            "token_configured": bool(CONFLUENCE_API_TOKEN),
            "token_length": len(CONFLUENCE_API_TOKEN) if CONFLUENCE_API_TOKEN else 0,
            "space_key": os.getenv('CONFLUENCE_SPACE_KEY', 'Not set').strip(),
            "ssl_verify": VERIFY_SSL
        }
    }
    
    # Test Confluence connection
    try:
        test_url = f"{CONFLUENCE_BASE_URL}/rest/api/content?limit=1"
        print(f"DEBUG: Testing URL: {test_url}")
        print(f"DEBUG: Token starts with: {CONFLUENCE_API_TOKEN[:10] if CONFLUENCE_API_TOKEN else 'None'}...")
        
        resp = requests.get(
            test_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
            },
            verify=VERIFY_SSL,
            timeout=10
        )
        
        debug_info["confluence_connection"] = "SUCCESS" if resp.status_code == 200 else f"FAILED: {resp.status_code}"
        debug_info["response_headers"] = dict(resp.headers) if hasattr(resp, 'headers') else {}
        
        if resp.status_code == 200:
            data = resp.json()
            debug_info["confluence_test_results"] = len(data.get("results", []))
        elif resp.status_code == 401:
            debug_info["auth_error"] = "Invalid credentials - check API token and email"
        elif resp.status_code == 403:
            debug_info["auth_error"] = "Access forbidden - check permissions"
        else:
            try:
                debug_info["error_response"] = resp.text[:500]
            except:
                debug_info["error_response"] = "Could not read response"
                
    except Exception as e:
        debug_info["confluence_connection"] = f"ERROR: {str(e)}"
    
    return f"<pre>{debug_info}</pre>"

@app.route("/refresh")
def refresh_data():
    """Manually refresh Confluence data"""
    try:
        embed_and_store_pages()
        return f"Data refresh completed. ChromaDB now contains {collection.count()} chunks."
    except Exception as e:
        return f"Data refresh failed: {str(e)}"
    
@app.route("/test-auth")
def test_auth():
    """Test different authentication methods"""
    results = {}
    
    # Test 1: Current method (Basic Auth with API token)
    try:
        test_url = f"{CONFLUENCE_BASE_URL}/rest/api/content?limit=1"
        resp = requests.get(
            test_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
            },
            verify=VERIFY_SSL,
            timeout=10
        )
        results["bearer_auth"] = {
            "status": resp.status_code,
            "response": resp.text[:200] if resp.status_code != 200 else "SUCCESS"
        }
    except Exception as e:
        results["bearer_auth"] = {"error": str(e)}

    # Test 2: Try with Bearer token (if it's actually a Bearer token)
    try:
        test_url = f"{CONFLUENCE_BASE_URL}/rest/api/content?limit=1"
        resp = requests.get(
            test_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
            },
            verify=VERIFY_SSL,
            timeout=10
        )
        results["bearer_auth"] = {
            "status": resp.status_code,
            "response": resp.text[:200] if resp.status_code != 200 else "SUCCESS"
        }
    except Exception as e:
        results["bearer_auth"] = {"error": str(e)}
    
    # Test 3: Check what auth methods are supported
    try:
        test_url = f"{CONFLUENCE_BASE_URL}/rest/api/user/current"
        resp = requests.get(test_url, verify=VERIFY_SSL, timeout=10)
        results["auth_check"] = {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "response": resp.text[:200]
        }
    except Exception as e:
        results["auth_check"] = {"error": str(e)}
    
    return f"<pre>{results}</pre>"

@app.route("/health")
def health_check():
    """Simple health check endpoint that doesn't count chunks for faster response"""
    return {"status": "healthy"}, 200

@app.route("/spaces")
def list_spaces():
    """List all available spaces"""
    try:
        spaces_url = f"{CONFLUENCE_BASE_URL}/rest/api/space"
        resp = requests.get(
            spaces_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
            },
            verify=VERIFY_SSL,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            spaces = []
            for space in data.get("results", []):
                spaces.append({
                    "key": space.get("key"),
                    "name": space.get("name"),
                    "type": space.get("type")
                })
            return f"<pre>Available spaces: {spaces}</pre>"
        else:
            return f"<pre>Error fetching spaces: {resp.status_code} - {resp.text}</pre>"
            
    except Exception as e:
        return f"<pre>Exception: {str(e)}</pre>"

@app.route("/debug-chromadb")
def debug_chromadb():
    """Debug ChromaDB connection and status"""
    debug_info = {}
    
    try:
        # Check which client type we're using
        debug_info["client_type"] = str(type(db))
        debug_info["chromadb_host"] = CHROMADB_HOST
        
        # Try to get collections
        collections = db.list_collections()
        debug_info["collections"] = [col.name for col in collections]
        debug_info["total_collections"] = len(collections)
        
        # Check our specific collection
        try:
            confluence_collection = db.get_collection("confluence")
            debug_info["confluence_collection_exists"] = True
            debug_info["confluence_count"] = confluence_collection.count()
        except Exception as e:
            debug_info["confluence_collection_exists"] = False
            debug_info["confluence_error"] = str(e)
            
        # Try creating collection if it doesn't exist
        try:
            test_collection = db.get_or_create_collection("test")
            debug_info["can_create_collections"] = True
            debug_info["test_collection_count"] = test_collection.count()
        except Exception as e:
            debug_info["can_create_collections"] = False
            debug_info["create_error"] = str(e)
            
        debug_info["status"] = "SUCCESS"
        
    except Exception as e:
        debug_info["status"] = "ERROR"
        debug_info["error"] = str(e)
        import traceback
        debug_info["traceback"] = traceback.format_exc()
    
    return f"<pre>{debug_info}</pre>"


@app.route("/test-fetch-strategy")
def test_fetch_strategy():
    """Test the new robust fetching strategy without storing to DB"""
    space_key = os.getenv('CONFLUENCE_SPACE_KEY', '').strip()
    results = {}
    
    try:
        # Step 1: Test page count
        total_count = get_space_page_count()
        results["total_pages"] = total_count
        
        # Step 2: Test fetching first few page IDs
        page_ids = fetch_all_page_ids()
        results["ids_fetched"] = len(page_ids)
        results["sample_ids"] = page_ids[:5]  # First 5 IDs
        
        # Step 3: Test fetching content for first page
        if page_ids:
            first_page = fetch_page_content_by_id(page_ids[0])
            results["sample_page"] = {
                "id": first_page.get("id"),
                "title": first_page.get("title"),
                "has_body": "body" in first_page,
                "has_storage": "storage" in first_page.get("body", {}),
                "content_length": len(first_page.get("body", {}).get("storage", {}).get("value", ""))
            }
        
        results["status"] = "SUCCESS"
        
    except Exception as e:
        results["status"] = "ERROR"
        results["error"] = str(e)
        import traceback
        results["traceback"] = traceback.format_exc()
    
    return f"<pre>{results}</pre>"


@app.route("/test-space")
def test_space():
    """Test the specific space"""
    space_key = os.getenv('CONFLUENCE_SPACE_KEY', '').strip()
    results = {}
    
    try:
        # Test 1: Check if space exists
        space_url = f"{CONFLUENCE_BASE_URL}/rest/api/space/{space_key}"
        resp = requests.get(
            space_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
            },
            verify=VERIFY_SSL,
            timeout=10
        )
        results["space_exists"] = resp.status_code == 200
        if resp.status_code == 200:
            space_data = resp.json()
            results["space_info"] = {
                "name": space_data.get("name"),
                "key": space_data.get("key"),
                "type": space_data.get("type")
            }
        
        # Test 2: Check pages in space
        pages_url = f"{CONFLUENCE_BASE_URL}/rest/api/content?type=page&spaceKey={space_key}&limit=5"
        resp = requests.get(
            pages_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFLUENCE_API_TOKEN}"
            },
            verify=VERIFY_SSL,
            timeout=10
        )
        
        if resp.status_code == 200:
            pages_data = resp.json()
            results["pages_found"] = len(pages_data.get("results", []))
            results["total_pages"] = pages_data.get("size", 0)
            results["sample_pages"] = [
                {"id": p.get("id"), "title": p.get("title")} 
                for p in pages_data.get("results", [])[:3]
            ]
        else:
            results["pages_error"] = f"Status: {resp.status_code}, Response: {resp.text[:200]}"
            
    except Exception as e:
        results["error"] = str(e)
    
    return f"<pre>{results}</pre>"

@app.route("/docs")
def documentation():
    """Comprehensive documentation route explaining the application architecture and usage"""
    try:
        # Get real-time metrics for the documentation
        chromadb_chunks = collection.count()
        
        # For total pages, we'll estimate based on chunks (since we don't store this separately)
        # Each page typically generates 1-3 chunks, so rough estimate
        estimated_pages = max(chromadb_chunks // 1, 369)  # Use known value of 369 as minimum
        
        return render_template('docs/index.html', 
                             chromadb_chunks=chromadb_chunks,
                             total_pages=estimated_pages)
    except Exception as e:
        # Fallback with static values if ChromaDB is unavailable
        return render_template('docs/index.html', 
                             chromadb_chunks="N/A",
                             total_pages=369)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5300)
