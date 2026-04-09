---
inclusion: auto
---

# OAuth Integration Skill

Test and debug Google and GitHub OAuth authentication.

## When to Use
- User reports login with Google/GitHub not working
- Testing OAuth flow
- Adding new OAuth provider

## OAuth Providers
1. **Google OAuth**: `services/google_oauth.py`
2. **GitHub OAuth**: `services/github_oauth.py`

## Test OAuth
```bash
pytest tests/integration/test_google_oauth_flow.py -v
```

## OAuth Flow
1. User clicks "Login with Google/GitHub"
2. Redirect to provider's auth page
3. User approves
4. Provider redirects back with code
5. Code exchanged for access token
6. User info retrieved and user created/updated

## Key Files
- `blueprints/auth.py` - OAuth routes
- `services/google_oauth.py` - Google OAuth
- `services/github_oauth.py` - GitHub OAuth

## Environment Variables
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- GitHub: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`

## Debug Tips
- Check OAuth callback URL matches registered redirect URI
- Verify scopes: `openid email profile`
- Check token expiration handling
