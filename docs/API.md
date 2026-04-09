# OnePay API Documentation

## Base URL

All API endpoints are prefixed with `/api/v1`.

---

## Response Format

### Success Response

Successful responses include a `success: true` field along with the relevant data payload.

```json
{
  "success": true,
  "data": { ... }
}
```

### Error Response

All error responses follow a standard JSON format:

```json
{
  "success": false,
  "message": "Human-readable description of the error",
  "error_code": "MACHINE_READABLE_CODE"
}
```

| Field        | Type    | Description                                                  |
|--------------|---------|--------------------------------------------------------------|
| `success`    | boolean | Always `false` for error responses                           |
| `message`    | string  | Human-readable error description safe to display to users    |
| `error_code` | string  | Machine-readable code for programmatic error handling        |

---

## HTTP Status Codes

| Status | Meaning                                                      |
|--------|--------------------------------------------------------------|
| `200`  | OK — request succeeded                                       |
| `400`  | Bad Request — invalid input or missing required fields       |
| `401`  | Unauthorized — authentication required or failed            |
| `403`  | Forbidden — authenticated but not authorized                 |
| `404`  | Not Found — resource does not exist                          |
| `413`  | Payload Too Large — request body exceeds 1 MB limit          |
| `429`  | Too Many Requests — rate limit exceeded                      |
| `500`  | Internal Server Error — unexpected server-side failure       |
| `502`  | Bad Gateway — upstream payment provider returned an error    |
| `503`  | Service Unavailable — payment provider circuit breaker open  |

---

## Error Code Reference

### Application Errors

| Error Code           | HTTP Status | Description                                                        |
|----------------------|-------------|--------------------------------------------------------------------|
| `VALIDATION_ERROR`   | 400         | Input validation failed (missing or malformed field)               |
| `AUTHENTICATION_ERROR` | 401       | Authentication required or credentials are invalid                 |
| `UNAUTHENTICATED`    | 401         | Request lacks valid authentication credentials                     |
| `AUTHORIZATION_ERROR` | 403        | Authenticated user does not have permission for this action        |
| `FORBIDDEN`          | 403         | Access to the requested resource is denied                         |
| `NOT_FOUND`          | 404         | The requested resource does not exist                              |
| `REQUEST_TOO_LARGE`  | 413         | Request body exceeds the 1 MB maximum size                         |
| `RATE_LIMITED`       | 429         | Too many requests — client should wait before retrying             |
| `INTERNAL_ERROR`     | 500         | Unexpected server error; no implementation details are exposed     |

### Payment Provider Errors

| Error Code             | HTTP Status | Description                                                      |
|------------------------|-------------|------------------------------------------------------------------|
| `PROVIDER_ERROR`       | 502         | Generic failure from an external payment provider               |
| `CIRCUIT_OPEN`         | 503         | KoraPay circuit breaker is open; service temporarily unavailable |
| `RATE_LIMIT`           | 429         | KoraPay API rate limit exceeded after maximum retries            |
| `TIMEOUT`             | 502         | Payment provider request timed out after all retries             |
| `CONNECTION_ERROR`     | 502         | Could not connect to the payment provider after all retries      |
| `SSL_ERROR`            | 502         | SSL/TLS verification failed when contacting payment provider     |
| `INVALID_JSON`         | 502         | Payment provider returned a non-JSON response                    |
| `INVALID_RESPONSE`     | 502         | Payment provider response is missing required fields             |
| `INVALID_AMOUNT`       | 400         | Payment amount is outside the allowed range (₦100–₦999,999,999) |
| `SERVER_ERROR`         | 502         | Payment provider returned a 5xx error after all retries          |
| `MAX_RETRIES_EXCEEDED` | 502         | Request to payment provider failed after the maximum retry count |

---

## Authentication

### Session Authentication

Browser-based clients authenticate via session cookie obtained after login.

### API Key Authentication

API clients authenticate by including an API key in the `Authorization` header:

```
Authorization: Bearer <api_key>
```

---

## Request Tracing

Every response includes the following headers for distributed tracing:

| Header             | Description                                      |
|--------------------|--------------------------------------------------|
| `X-Request-ID`     | Unique identifier for this request               |
| `X-Correlation-ID` | Correlation ID for tracing across services       |

To propagate your own trace ID, send it in the `X-Request-ID` request header and it will be echoed back in both response headers.

---

## Rate Limiting

Rate-limited endpoints return HTTP `429` with a `Retry-After` header indicating how many seconds to wait before retrying.

```json
{
  "success": false,
  "message": "Too many requests — please wait before trying again",
  "error_code": "RATE_LIMITED"
}
```
