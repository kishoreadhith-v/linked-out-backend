# API Reference

## Authentication

All API endpoints (except `/api/register` and `/api/login`) require JWT authentication. Include the JWT token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

## Endpoints

### Register User

```http
POST /api/register
```

Register a new user.

**Request Body:**

```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "confirm_password": "string"
}
```

**Response:**

- Success (201):

```json
{
  "message": "User registered successfully",
  "user_id": "string"
}
```

- Error (400): Invalid input
- Error (500): Server error

### Login

```http
POST /api/login
```

Authenticate and get JWT token.

**Request Body:**

```json
{
  "email": "string",
  "password": "string"
}
```

**Response:**

- Success (200):

```json
{
  "token": "string",
  "user": {
    "id": "string",
    "username": "string",
    "email": "string"
  }
}
```

- Error (401): Invalid credentials
- Error (500): Server error

### Add URL

```http
POST /api/urls
```

Add a new URL to the system. The URL will be scraped, processed, and stored for future queries.

**Headers:**

- Authorization: Bearer token required

**Request Body:**

```json
{
  "url": "string"
}
```

**Response:**

- Success (200):

```json
{
  "message": "URL added successfully"
}
```

- Error (400): Invalid URL
- Error (401): Unauthorized
- Error (500): Server error

### List URLs

```http
GET /api/urls
```

Get a list of all URLs added by the authenticated user.

**Headers:**

- Authorization: Bearer token required

**Response:**

- Success (200):

```json
[
  {
    "url": "string",
    "title": "string",
    "favicon": "string",
    "timestamp": "string"
  }
]
```

- Error (401): Unauthorized
- Error (500): Server error

### Delete URL

```http
DELETE /api/urls/{url}
```

Delete a specific URL from the system.

**Headers:**

- Authorization: Bearer token required

**Response:**

- Success (200):

```json
{
  "message": "URL deleted successfully"
}
```

- Error (404): URL not found
- Error (401): Unauthorized
- Error (500): Server error

### Search

```http
GET /api/search?q={query}
```

Search across all URLs for the authenticated user.

**Headers:**

- Authorization: Bearer token required

**Query Parameters:**

- `q`: Search query string

**Response:**

- Success (200):

```json
[
    {
        "url": "string",
        "title": "string",
        "favicon": "string",
        "score": number,
        "highlight": {
            "content": ["string"],
            "title": ["string"]
        },
        "snippet": "string"
    }
]
```

- Error (401): Unauthorized
- Error (500): Server error

### Chat

```http
POST /api/chat
```

Chat with the content of a specific URL using RAG (Retrieval Augmented Generation).

**Headers:**

- Authorization: Bearer token required

**Request Body:**

```json
{
  "url": "string",
  "query": "string"
}
```

**Response:**

- Success (200):

```json
{
  "response": "string",
  "url": "string",
  "title": "string"
}
```

- Error (400): Invalid input
- Error (401): Unauthorized
- Error (404): URL not found or no relevant content
- Error (500): Server error

## Error Handling

All error responses follow this format:

```json
{
  "error": "string",
  "details": "string" // Optional, provides additional error information
}
```

## Rate Limiting

Currently, there are no rate limits implemented. However, please use the API responsibly.

## Best Practices

1. Always handle authentication errors (401) by redirecting to login
2. Implement proper error handling for all API calls
3. Cache responses where appropriate
4. Implement retry logic for failed requests
5. Use proper content-type headers for all requests
