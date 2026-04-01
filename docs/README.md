# OnePay Documentation

Welcome to the OnePay documentation. This directory contains all project documentation organized for easy access.

## Quick Links

- [API Keys Documentation](API_KEYS.md) - Machine-to-machine API access and authentication
- [Security Documentation](SECURITY.md) - Security features, best practices, and audit history
- [Deployment Guide](DEPLOYMENT.md) - Production deployment checklist and instructions
- [Upgrade Guide](UPGRADE_GUIDE.md) - Database migration and upgrade procedures
- [Webhook Verification](WEBHOOK_VERIFICATION.md) - Webhook implementation and verification guide

## Documentation Structure

```
docs/
├── README.md (this file)
├── API_KEYS.md - API key authentication and M2M integration
├── SECURITY.md - Consolidated security documentation
├── DEPLOYMENT.md - Production deployment guide
├── UPGRADE_GUIDE.md - Migration and upgrade instructions
├── WEBHOOK_VERIFICATION.md - Webhook integration guide
└── archive/ - Historical documentation and audit reports
```

## API Integration

OnePay supports programmatic API access for machine-to-machine integrations:

- **API Keys**: Generate API keys for server-to-server authentication
- **OpenAPI Spec**: Complete API documentation available at `/static/openapi.json`
- **Rate Limits**: Higher rate limits for API clients (100 req/min vs 10 req/min for web UI)
- **CSRF Bypass**: API key requests automatically bypass CSRF validation

See [API_KEYS.md](API_KEYS.md) for complete documentation including:
- How to generate and manage API keys
- Authentication examples (cURL, Python, Node.js)
- Security best practices
- Rate limiting details
- Error handling

## Archive

The `archive/` directory contains historical documentation including:
- Security audit reports
- Codebase reviews
- Applied fixes documentation
- Design prompts and improvements

These files are preserved for reference but the current documentation in the main docs/ directory should be used for active development.

## Getting Started

1. **For Developers**: Start with the main project README in the root directory
2. **For API Integration**: Review [API_KEYS.md](API_KEYS.md) and `/static/openapi.json`
3. **For Security**: Review [SECURITY.md](SECURITY.md)
4. **For Deployment**: Follow [DEPLOYMENT.md](DEPLOYMENT.md)
5. **For Webhooks**: See [WEBHOOK_VERIFICATION.md](WEBHOOK_VERIFICATION.md)

## Contributing

