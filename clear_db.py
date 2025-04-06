from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Elasticsearch credentials
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

def clear_and_recreate_indices():
    es = create_elasticsearch_client()
    if not es:
        print("Failed to connect to Elasticsearch")
        return

    # List of indices to clear and recreate
    indices = ['users', 'webpages']

    for index in indices:
        try:
            # Delete index if it exists
            if es.indices.exists(index=index):
                es.indices.delete(index=index)
                print(f"Deleted index: {index}")

            # Create index with mappings
            if index == 'users':
                es.indices.create(index=index, body={
                    "mappings": {
                        "properties": {
                            "username": {"type": "keyword"},
                            "email": {
                                "type": "text",
                                "fields": {
                                    "keyword": {"type": "keyword"}
                                }
                            },
                            "password_hash": {"type": "keyword"},
                            "created_at": {"type": "date"}
                        }
                    }
                })
            elif index == 'webpages':
                es.indices.create(index=index, body={
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
                            "timestamp": {"type": "date"},
                            "user_id": {"type": "keyword"}
                        }
                    }
                })
            print(f"Created index: {index}")
        except Exception as e:
            print(f"Error processing index {index}: {str(e)}")

if __name__ == '__main__':
    clear_and_recreate_indices() 