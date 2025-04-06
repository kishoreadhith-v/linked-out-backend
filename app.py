from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
from urllib.parse import urljoin
import jwt
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import re
from groq import Groq

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
es = None

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400  # 24 hours

# Get Elasticsearch credentials from environment variables
ELASTIC_PASSWORD = os.getenv('ELASTIC_PASSWORD')
ELASTIC_CERT_PATH = os.getenv('ELASTIC_CERT_PATH')
ELASTIC_HOST = os.getenv('ELASTIC_HOST', 'localhost')
ELASTIC_PORT = os.getenv('ELASTIC_PORT', '9200')
ELASTIC_USE_SSL = os.getenv('ELASTIC_USE_SSL', 'true').lower() == 'true'

# Initialize Groq client
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not found in environment variables. Chat functionality will be disabled.")
    groq_client = None
else:
    groq_client = Groq(api_key=GROQ_API_KEY)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            current_user = get_user_by_id(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

def create_elasticsearch_client():
    """Create Elasticsearch client with appropriate configuration"""
    try:
        config = {
            'hosts': [f"{'https' if ELASTIC_USE_SSL else 'http'}://{ELASTIC_HOST}:{ELASTIC_PORT}"],
            'basic_auth': ("elastic", ELASTIC_PASSWORD)
        }
        
        if ELASTIC_USE_SSL:
            config.update({
                'ca_certs': ELASTIC_CERT_PATH,
                'verify_certs': True
            })
        else:
            config.update({
                'verify_certs': False
            })
            
        client = Elasticsearch(**config)
        if client.ping():
            print("Successfully connected to Elasticsearch!")
            return client
        else:
            print("Failed to ping Elasticsearch")
            return None
    except Exception as e:
        print(f"Failed to connect to Elasticsearch: {str(e)}")
        return None

# Initialize Elasticsearch client
es = create_elasticsearch_client()

def get_user_by_id(user_id):
    if not es:
        return None
    try:
        result = es.get(index="users", id=user_id)
        if result["found"]:
            user_data = result["_source"]
            user_data["_id"] = result["_id"]
            return user_data
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
    return None

def get_user_by_email(email):
    if not es:
        return None
    try:
        result = es.search(index="users", body={
            "query": {
                "term": {
                    "email.keyword": email
                }
            }
        })
        if result["hits"]["total"]["value"] > 0:
            user_data = result["hits"]["hits"][0]["_source"]
            user_data["_id"] = result["hits"]["hits"][0]["_id"]
            return user_data
    except Exception as e:
        logger.error(f"Error getting user by email: {str(e)}")
    return None

@app.route('/api/register', methods=['POST'])
def register():
    if not es:
        return jsonify({'error': 'Elasticsearch is not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required_fields = ['username', 'email', 'password', 'confirm_password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    if data['password'] != data['confirm_password']:
        return jsonify({'error': 'Passwords do not match'}), 400

    # Validate email format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        return jsonify({'error': 'Invalid email format'}), 400

    # Check if email already exists
    existing_user = get_user_by_email(data['email'])
    if existing_user:
        return jsonify({'error': 'Email already registered'}), 400

    try:
        user_data = {
            "username": data['username'],
            "email": data['email'],
            "password_hash": generate_password_hash(data['password']),
            "created_at": datetime.utcnow().isoformat()
        }

        result = es.index(index="users", body=user_data)
        logger.info(f"User registered successfully: {data['email']}")
        return jsonify({
            'message': 'User registered successfully',
            'user_id': result['_id']
        }), 201
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        return jsonify({'error': 'Failed to register user'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    if not es:
        return jsonify({'error': 'Elasticsearch is not available'}), 503

    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        user = get_user_by_email(data['email'])
        if not user:
            logger.warning(f"Login attempt with non-existent email: {data['email']}")
            return jsonify({'error': 'Invalid email or password'}), 401

        if not check_password_hash(user['password_hash'], data['password']):
            logger.warning(f"Failed login attempt for user: {data['email']}")
            return jsonify({'error': 'Invalid email or password'}), 401

        token = jwt.encode(
            {
                'user_id': user['_id'],
                'exp': datetime.utcnow().timestamp() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
            },
            app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )

        logger.info(f"User logged in successfully: {data['email']}")
        return jsonify({
            'token': token,
            'user': {
                'id': user['_id'],
                'username': user['username'],
                'email': user['email']
            }
        })
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

def scrape_url(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get title
        title = soup.title.string if soup.title else "No title"
        
        # Find favicon
        favicon = None
        favicon_link = soup.find('link', rel=lambda r: r and ('icon' in r.lower() or 'shortcut' in r.lower()))
        if favicon_link and favicon_link.get('href'):
            favicon = urljoin(url, favicon_link['href'])
        else:
            # Try default favicon location
            default_favicon = urljoin(url, '/favicon.ico')
            try:
                favicon_response = requests.head(default_favicon)
                if favicon_response.status_code == 200:
                    favicon = default_favicon
            except:
                pass

        text = soup.get_text(separator=' ', strip=True)
        return {
            "title": title,
            "content": text,
            "favicon": favicon
        }
    except Exception as e:
        return None

@app.route('/api/urls', methods=['POST'])
@token_required
def add_url(current_user):
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data['url']
    scraped_data = scrape_url(url)
    if not scraped_data:
        return jsonify({"error": "Failed to scrape URL"}), 400

    try:
        es.index(index="webpages", body={
            "url": url,
            "title": scraped_data["title"],
            "content": scraped_data["content"],
            "favicon": scraped_data["favicon"],
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user['_id']
        })
        return jsonify({"message": "URL added successfully"})
    except Exception as e:
        logger.error(f"Error adding URL: {str(e)}")
        return jsonify({"error": "Failed to store URL"}), 500

@app.route('/api/urls', methods=['GET'])
@token_required
def list_urls(current_user):
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503

    try:
        results = es.search(index="webpages", body={
            "query": {
                "term": {
                    "user_id": current_user['_id']
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": 100
        })
        
        urls = [{
            "url": hit["_source"]["url"],
            "title": hit["_source"]["title"],
            "favicon": hit["_source"].get("favicon"),
            "timestamp": hit["_source"]["timestamp"]
        } for hit in results["hits"]["hits"]]
        
        return jsonify(urls)
    except Exception as e:
        logger.error(f"Error listing URLs: {str(e)}")
        return jsonify({"error": "Failed to list URLs"}), 500

@app.route('/api/urls/<path:url>', methods=['DELETE'])
@token_required
def delete_url(current_user, url):
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503

    try:
        # Search for the URL belonging to the current user
        result = es.search(index="webpages", body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"url": url}},
                        {"term": {"user_id": current_user['_id']}}
                    ]
                }
            }
        })

        if result["hits"]["total"]["value"] == 0:
            return jsonify({"error": "URL not found"}), 404

        # Delete the document
        doc_id = result["hits"]["hits"][0]["_id"]
        es.delete(index="webpages", id=doc_id)
        
        return jsonify({"message": "URL deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting URL: {str(e)}")
        return jsonify({"error": "Failed to delete URL"}), 500

@app.route('/api/search', methods=['GET'])
@token_required
def search(current_user):
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503

    query = request.args.get('q')
    if not query:
        return jsonify([])

    try:
        results = es.search(index="webpages", body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"user_id": current_user['_id']}},
                        {
                            "bool": {
                                "should": [
                                    {
                                        "match": {
                                            "title": {
                                                "query": query,
                                                "boost": 2.0,
                                                "fuzziness": "AUTO",
                                                "prefix_length": 2
                                            }
                                        }
                                    },
                                    {
                                        "match": {
                                            "content": {
                                                "query": query,
                                                "fuzziness": "AUTO",
                                                "prefix_length": 2
                                            }
                                        }
                                    }
                                ],
                                "minimum_should_match": 1
                            }
                        }
                    ]
                }
            },
            "highlight": {
                "fields": {
                    "content": {
                        "fragment_size": 150,
                        "number_of_fragments": 1,
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"]
                    },
                    "title": {
                        "fragment_size": 150,
                        "number_of_fragments": 1,
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"]
                    }
                }
            }
        })

        return jsonify([{
            "url": hit["_source"]["url"],
            "title": hit["_source"]["title"],
            "favicon": hit["_source"].get("favicon"),
            "score": hit["_score"],
            "highlight": hit.get("highlight", {}),
            "snippet": hit["highlight"]["content"][0] if "content" in hit.get("highlight", {}) else None
        } for hit in results["hits"]["hits"]])
    except Exception as e:
        logger.error(f"Error searching URLs: {str(e)}")
        return jsonify({"error": "Search failed"}), 500

def get_url_content(url, user_id):
    """Retrieve the content of a specific URL for a user"""
    if not es:
        return None
    try:
        result = es.search(index="webpages", body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"url": url}},
                        {"term": {"user_id": user_id}}
                    ]
                }
            }
        })
        if result["hits"]["total"]["value"] > 0:
            return result["hits"]["hits"][0]["_source"]
        return None
    except Exception as e:
        logger.error(f"Error retrieving URL content: {str(e)}")
        return None

def format_content_for_llm(content, query):
    """Format the content for the LLM prompt"""
    return f"""You are a direct and helpful assistant that answers questions about web content. Follow these rules strictly:

1. ONLY answer questions that can be directly answered using the provided content.
2. If the question is not related to the content, respond with: "I can only answer questions about the content of this webpage, which is about [brief topic]. Your question seems unrelated to this content."
3. If the question is related but there isn't enough information, respond with: "While this page is about [brief topic], I don't have enough information in the content to fully answer your question about [specific aspect]. You might want to:
   - Check other sections of the website
   - Search for [specific terms] online
   - Consult [relevant sources]"
4. Speak directly to the user in a clear, professional tone.
5. Never mention that you are an AI or assistant - just provide the answer.
6. Don't apologize or use phrases like "I think" or "I believe" - be confident in your responses when they're based on the content.

Here is the content to work with:

Title: {content['title']}
URL: {content['url']}
Content: {content['content']}

User Question: {query}"""

@app.route('/api/chat', methods=['POST'])
@token_required
def chat(current_user):
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503
    
    if not groq_client:
        return jsonify({"error": "Groq API is not configured"}), 503

    data = request.get_json()
    if not data or 'url' not in data or 'query' not in data:
        return jsonify({"error": "URL and query are required"}), 400

    url = data['url']
    query = data['query']

    # Get the content for the URL
    content = get_url_content(url, current_user['_id'])
    if not content:
        return jsonify({"error": "URL not found or not accessible"}), 404

    try:
        # Format the content for the LLM
        prompt = format_content_for_llm(content, query)
        
        # Get response from Groq
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "You are a direct and helpful assistant that answers questions about web content. Always speak directly to the user and only answer questions based on the provided content."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more focused responses
            max_tokens=1024
        )

        return jsonify({
            "response": response.choices[0].message.content,
            "url": url,
            "title": content['title']
        })
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        return jsonify({"error": "Failed to generate response"}), 500

if __name__ == '__main__':
    if not es:
        print("""
Note: Application will run in limited mode without Elasticsearch.
- URL submission will be disabled
- Search functionality will be disabled
""")
    app.run(host="0.0.0.0", port="8888", debug=True)