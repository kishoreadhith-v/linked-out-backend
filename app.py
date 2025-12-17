from flask import Flask, request, render_template, jsonify
from elasticsearch import Elasticsearch
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
from urllib.parse import urljoin

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
es = None

# Get Elasticsearch credentials from environment variables
ELASTIC_PASSWORD = os.getenv('ELASTIC_PASSWORD')
ELASTIC_CERT_PATH = os.getenv('ELASTIC_CERT_PATH')
ELASTIC_HOST = os.getenv('ELASTIC_HOST', 'localhost')
ELASTIC_PORT = os.getenv('ELASTIC_PORT', '9200')
ELASTIC_USE_SSL = os.getenv('ELASTIC_USE_SSL', 'true').lower() == 'true'

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

if es:
    try:
        if not es.indices.exists(index="webpages"):
            es.indices.create(index="webpages", body={
                "settings": {
                    "analysis": {
                        "analyzer": {
                            "custom_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase", "custom_edge_ngram"]
                            }
                        },
                        "filter": {
                            "custom_edge_ngram": {
                                "type": "edge_ngram",
                                "min_gram": 2,
                                "max_gram": 10
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "url": {"type": "keyword"},
                        "content": {
                            "type": "text",
                            "analyzer": "custom_analyzer",
                            "search_analyzer": "standard"
                        },
                        "title": {
                            "type": "text",
                            "analyzer": "custom_analyzer",
                            "search_analyzer": "standard",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        },
                        "favicon": {"type": "keyword"},
                        "timestamp": {"type": "date"}
                    }
                }
            })
            print("Created 'webpages' index with edge ngram analyzer")
    except Exception as e:
        print(f"Error creating index: {str(e)}")
        es = None

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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/add_url', methods=['POST'])
def add_url():
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503

    url = request.form.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    scraped_data = scrape_url(url)
    if not scraped_data:
        return jsonify({"error": "Failed to scrape URL"}), 400

    try:
        es.index(index="webpages", body={
            "url": url,
            "title": scraped_data["title"],
            "content": scraped_data["content"],
            "favicon": scraped_data["favicon"],
            "timestamp": datetime.utcnow().isoformat()  # Add timestamp
        })
        return jsonify({"message": "URL added successfully"})
    except Exception as e:
        app.logger.error(f"Elasticsearch indexing error: {str(e)}")
        return jsonify({"error": "Failed to store URL content"}), 500

@app.route('/search', methods=['GET'])
def search():
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503

    query = request.args.get('q')
    if not query:
        return jsonify([])

    try:
        results = es.search(index="webpages", body={
            "query": {
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
                        },
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["title", "content"],
                                "type": "phrase_prefix"
                            }
                        }
                    ],
                    "minimum_should_match": 1
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
        app.logger.error(f"Elasticsearch search error: {str(e)}")
        return jsonify({"error": "Search failed"}), 500

@app.route('/urls', methods=['GET'])
def list_urls():
    if not es:
        logger.error("Elasticsearch client is not initialized")
        return jsonify({"error": "Elasticsearch is not available"}), 503

    try:
        results = es.search(index="webpages", body={
            "query": {"match_all": {}},
            "sort": [{"timestamp": {"order": "desc"}}],  # Sort by timestamp
            "size": 100  # Limit to latest 100 URLs
        })
        
        urls = [{
            "url": hit["_source"]["url"],
            "title": hit["_source"]["title"],
            "favicon": hit["_source"].get("favicon"),
            "timestamp": hit["_source"]["timestamp"]
        } for hit in results["hits"]["hits"]]
        
        logger.info(f"Successfully fetched {len(urls)} URLs")
        return jsonify(urls)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error fetching URLs: {error_msg}")
        return jsonify({"error": f"Failed to fetch URLs: {error_msg}"}), 500

@app.route('/url/<path:url>', methods=['DELETE'])
def delete_url(url):
    if not es:
        return jsonify({"error": "Elasticsearch is not available"}), 503

    try:
        # Clean the URL (remove potential double encoding)
        clean_url = url.strip()
        
        # Log the URL for debugging
        logger.info(f"Attempting to delete URL: {clean_url}")

        # Search for the exact URL
        result = es.search(index="webpages", body={
            "size": 1,
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "url": clean_url
                            }
                        }
                    ]
                }
            }
        })

        # Check if URL was found
        if result["hits"]["total"]["value"] == 0:
            logger.warning(f"URL not found: {clean_url}")
            return jsonify({"error": "URL not found"}), 404

        # Delete the document
        doc_id = result["hits"]["hits"][0]["_id"]
        es.delete(index="webpages", id=doc_id)
        
        logger.info(f"Successfully deleted URL: {clean_url}")
        return jsonify({"message": "URL deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting URL: {str(e)}")
        return jsonify({"error": f"Failed to delete URL: {str(e)}"}), 500

if __name__ == '__main__':
    if not es:
        print("""
Note: Application will run in limited mode without Elasticsearch.
- URL submission will be disabled
- Search functionality will be disabled
""")
    app.run(host="0.0.0.0", port="8888", debug=True)