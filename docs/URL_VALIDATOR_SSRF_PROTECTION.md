# URL Validator Service - SSRF Protection

## Overview

The URL validator service (`services/url_validator.py`) provides SSRF (Server-Side Request Forgery) protection by validating URLs and resolving DNS before making HTTP requests. This prevents DNS rebinding attacks (TOCTOU vulnerabilities) where an attacker can change DNS records between validation and request.

## Requirements Implemented

- **Requirement 3.1**: DNS resolution to IP address before HTTP requests
- **Requirement 3.2**: Check against private IP ranges (RFC 1918, loopback, link-local, multicast)
- **Requirement 3.3**: Return resolved IP for Host header binding

## How It Works

### The Problem: DNS Rebinding Attack (TOCTOU)

Traditional URL validation has a Time-of-Check-Time-of-Use (TOCTOU) vulnerability:

1. **Check**: Validate URL hostname is not private (e.g., `attacker.com` → `1.2.3.4`)
2. **Use**: Make HTTP request to `attacker.com`
3. **Attack**: Attacker changes DNS to private IP (`attacker.com` → `169.254.169.254`)
4. **Result**: HTTP library resolves DNS again, gets private IP, SSRF succeeds

### The Solution: Resolve DNS Once

Our solution resolves DNS during validation and uses the resolved IP directly:

1. **Validate**: Resolve `attacker.com` → `1.2.3.4`, check if public
2. **Use**: Make HTTP request to `1.2.3.4` (not `attacker.com`)
3. **Attack Fails**: Even if attacker changes DNS, we use the validated IP

## Usage

### Basic Usage

```python
from services.url_validator import validate_url_for_ssrf
from urllib.parse import urlparse
import requests

# Step 1: Validate URL and get resolved IP
logo_url = "https://cdn.example.com/logo.png"
is_valid, resolved_ip, error = validate_url_for_ssrf(logo_url)

if not is_valid:
    # Handle validation error
    return error_response(error)

# Step 2: Make HTTP request using resolved IP
parsed = urlparse(logo_url)
safe_url = f"{parsed.scheme}://{resolved_ip}{parsed.path}"

# Use Host header to preserve hostname for virtual hosting
response = requests.get(
    safe_url,
    headers={'Host': parsed.hostname},
    timeout=5,
    verify=True  # Always verify SSL certificates
)
```

### Integration with Invoice Logo Validation

```python
from services.url_validator import validate_url_for_ssrf

# Validate logo URL
logo_url = data.get("business_logo_url")
if logo_url:
    # Step 1: SSRF protection
    is_valid, resolved_ip, error = validate_url_for_ssrf(logo_url)
    
    if not is_valid:
        return error(
            f"Invalid logo URL: {error}",
            "VALIDATION_ERROR",
            400
        )
    
    # Step 2: Fetch logo using resolved IP
    from urllib.parse import urlparse
    parsed = urlparse(logo_url)
    safe_url = f"{parsed.scheme}://{resolved_ip}{parsed.path}"
    
    try:
        response = requests.get(
            safe_url,
            headers={'Host': parsed.hostname},
            timeout=5,
            verify=True
        )
        
        if response.status_code != 200:
            return error(
                f"Logo URL is not accessible (HTTP {response.status_code})",
                "VALIDATION_ERROR",
                400
            )
        
        # Validate content type
        content_type = response.headers.get('Content-Type', '')
        valid_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
        
        if not any(ct in content_type for ct in valid_types):
            return error(
                "Logo URL must return a valid image format (PNG, JPG, or SVG)",
                "VALIDATION_ERROR",
                400
            )
        
        # Logo is valid
        business_logo_url = logo_url
        
    except requests.Timeout:
        return error(
            "Logo URL request timed out",
            "VALIDATION_ERROR",
            400
        )
    except requests.RequestException as e:
        logger.error("Logo URL fetch failed | url=%s error=%s", logo_url, e)
        return error(
            "Logo URL is not accessible",
            "VALIDATION_ERROR",
            400
        )
```

## Protected IP Ranges

The validator blocks the following IP ranges:

### IPv4
- `10.0.0.0/8` - Private network (RFC 1918)
- `172.16.0.0/12` - Private network (RFC 1918)
- `192.168.0.0/16` - Private network (RFC 1918)
- `127.0.0.0/8` - Loopback
- `169.254.0.0/16` - Link-local (RFC 3927)
- `224.0.0.0/4` - Multicast
- `240.0.0.0/4` - Reserved
- `0.0.0.0/8` - Current network

### IPv6
- `::1/128` - Loopback
- `fe80::/10` - Link-local
- `fc00::/7` - Unique local
- `ff00::/8` - Multicast

### Special Cases
- `169.254.169.254` - AWS metadata endpoint (explicit check with specific error)

## API Reference

### `validate_url_for_ssrf(url: str) -> Tuple[bool, Optional[str], Optional[str]]`

Validate URL and resolve to safe IP address with SSRF protection.

**Parameters:**
- `url` (str): The URL to validate (must be HTTP or HTTPS)

**Returns:**
- Tuple of `(is_valid, resolved_ip, error_message)`:
  - `is_valid` (bool): True if URL is safe to use, False otherwise
  - `resolved_ip` (str | None): The resolved IP address if valid, None otherwise
  - `error_message` (str | None): Human-readable error if invalid, None if valid

**Example:**
```python
is_valid, ip, error = validate_url_for_ssrf("https://example.com/logo.png")
if is_valid:
    print(f"Safe to use: {ip}")
else:
    print(f"Blocked: {error}")
```

### `is_private_ip(ip_str: str) -> bool`

Check if an IP address is private, loopback, link-local, or multicast.

**Parameters:**
- `ip_str` (str): IP address as string (IPv4 or IPv6)

**Returns:**
- `bool`: True if IP is private/internal, False if public

**Example:**
```python
is_private_ip("192.168.1.1")  # True
is_private_ip("8.8.8.8")      # False
```

## Security Considerations

### Why This Matters

SSRF vulnerabilities can allow attackers to:
- Access AWS metadata endpoint (`169.254.169.254`) to steal credentials
- Scan internal network infrastructure
- Access internal APIs and services
- Bypass firewall restrictions
- Read local files via `file://` protocol (blocked by scheme check)

### Defense in Depth

This service is one layer of defense. Additional protections:

1. **Network Segmentation**: Application servers should not have access to sensitive internal resources
2. **Firewall Rules**: Block outbound connections to private IP ranges at network level
3. **Least Privilege**: Application should run with minimal permissions
4. **Monitoring**: Log and alert on SSRF attempts (already implemented in this service)

### Known Limitations

1. **IPv6 Support**: Currently only resolves IPv4 addresses via `socket.gethostbyname()`. For full IPv6 support, use `socket.getaddrinfo()`.
2. **DNS Cache**: Python's socket library may cache DNS results. This is acceptable as we resolve once during validation.
3. **Redirects**: If the HTTP request follows redirects, the redirect target is not validated. Consider disabling redirects or validating redirect targets.

## Testing

The service includes comprehensive tests:

- **Unit Tests** (`tests/test_url_validator.py`): 35 tests covering all IP ranges and edge cases
- **Integration Tests** (`tests/test_url_validator_integration.py`): 6 tests demonstrating real-world usage patterns

Run tests:
```bash
pytest tests/test_url_validator*.py -v
```

## References

- [CWE-918: Server-Side Request Forgery (SSRF)](https://cwe.mitre.org/data/definitions/918.html)
- [OWASP: Server-Side Request Forgery](https://owasp.org/www-community/attacks/Server_Side_Request_Forgery)
- [RFC 1918: Address Allocation for Private Internets](https://tools.ietf.org/html/rfc1918)
- [RFC 3927: Dynamic Configuration of IPv4 Link-Local Addresses](https://tools.ietf.org/html/rfc3927)
- [AWS SSRF Prevention](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html)
