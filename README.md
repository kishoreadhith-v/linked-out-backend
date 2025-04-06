# Linked-Out: Web Content Analysis and Chat API

Linked-Out is a powerful API service that allows users to analyze, search, and interact with web content using advanced AI capabilities. It combines web scraping, semantic search, and Retrieval Augmented Generation (RAG) to provide intelligent responses about web content.

## Features

- 🔐 User authentication and authorization
- 🌐 Web content scraping and storage
- 🔍 Semantic search across stored content
- 💬 AI-powered chat interface with web content
- 📊 Elasticsearch for efficient content indexing
- 🧠 Groq-powered RAG for intelligent responses
- 🔄 Real-time content processing

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- pip (Python package manager)
- Git

## Project Structure

```
linked-out/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
├── API_REFERENCE.md   # API documentation
└── README.md          # Project documentation
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd linked-out
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root with the following variables:

```env
ELASTIC_PASSWORD=your_elastic_password
ELASTIC_CERT_PATH=/path/to/elastic/cert
ELASTIC_HOST=localhost
ELASTIC_PORT=9200
ELASTIC_USE_SSL=true
GROQ_API_KEY=your_groq_api_key
JWT_SECRET_KEY=your_jwt_secret
```

### 3. Start Elasticsearch with Docker

```bash
# Create a directory for Elasticsearch data
mkdir -p elasticsearch/data

# Start Elasticsearch container
docker run -d \
  --name elasticsearch \
  -p 9200:9200 \
  -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=true" \
  -e "ELASTIC_PASSWORD=your_elastic_password" \
  -v $(pwd)/elasticsearch/data:/usr/share/elasticsearch/data \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.0
```

### 4. Set Up Python Environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 5. Initialize Elasticsearch

```bash
# Generate Elasticsearch certificates
docker exec -it elasticsearch bin/elasticsearch-certutil ca
docker exec -it elasticsearch bin/elasticsearch-certutil cert --ca elastic-stack-ca.p12

# Copy certificates to your local machine
docker cp elasticsearch:/usr/share/elasticsearch/elastic-certificates.p12 ./elastic-certificates.p12
```

### 6. Run the Application

```bash
# Start the Flask application
python app.py
```

The API will be available at `http://localhost:8888`

## Usage

### 1. Register a User

```bash
curl -X POST http://localhost:8888/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "confirm_password": "password123"
  }'
```

### 2. Login and Get Token

```bash
curl -X POST http://localhost:8888/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

### 3. Add a URL for Analysis

```bash
curl -X POST http://localhost:8888/api/urls \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com"
  }'
```

### 4. Chat with URL Content

```bash
curl -X POST http://localhost:8888/api/chat \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "query": "What is this website about?"
  }'
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest
```

### Code Style

This project follows PEP 8 style guidelines. Use the following tools to maintain code quality:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run linter
flake8

# Run formatter
black .
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

## Acknowledgments

- Elasticsearch for powerful search capabilities
- Groq for high-performance AI inference
- Flask for the web framework
- All contributors and maintainers
