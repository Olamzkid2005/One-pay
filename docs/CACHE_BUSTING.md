# Cache Busting Implementation

## Overview

OnePay implements content-based filename hashing for static assets (CSS and JavaScript) to enable long-term browser caching while ensuring users always receive the latest version when files change.

## How It Works

### 1. Build Process

The build pipeline generates hashed filenames based on file content:

```bash
npm run build
```

This runs three steps:
1. `npm run build:css` - Builds and minifies Tailwind CSS
2. `npm run hash:assets` - Generates content-hashed filenames
3. `npm run build:js` - Minifies JavaScript files

### 2. Hash Generation

The `scripts/hash-assets.js` script:
- Reads each static asset (CSS/JS)
- Computes an 8-character MD5 hash of the content
- Copies the file to a hashed filename (e.g., `output.a09f3865.css`)
- Generates a manifest mapping original → hashed filenames
- Cleans up old hashed versions

Example:
```
output.css → output.a09f3865.css
login.js → login.3c8f8089.js
```

### 3. Manifest File

The build process creates `static/manifest.json`:

```json
{
  "css/output.css": "css/output.a09f3865.css",
  "js/login.js": "js/login.3c8f8089.js",
  "js/dashboard.js": "js/dashboard.6faffb9a.js",
  "js/verify.js": "js/verify.1777a9d9.js",
  "js/loading-states.js": "js/loading-states.e009d00d.js"
}
```

### 4. Template Integration

Templates use the `hashed_url()` helper function:

```html
<!-- Before -->
<link rel="stylesheet" href="/static/css/output.css">

<!-- After -->
<link rel="stylesheet" href="{{ hashed_url('css/output.css') }}">

<!-- Renders as -->
<link rel="stylesheet" href="/static/css/output.a09f3865.css">
```

### 5. Flask Integration

The Flask app (`app.py`) provides:
- `_load_asset_manifest()` - Loads manifest.json on startup
- `inject_hashed_assets()` - Context processor that exposes `hashed_url()` to templates
- Automatic fallback to unhashed filenames if manifest is missing

## Benefits

1. **Long-term Caching**: Hashed files can be cached indefinitely (1 year)
2. **Automatic Invalidation**: Hash changes when content changes
3. **No Manual Versioning**: Content-based hashing is automatic
4. **Development Friendly**: Falls back to unhashed files if manifest is missing

## Cache Headers

Static files are served with appropriate cache headers:

```python
# Hashed files (8-char hash in filename)
Cache-Control: public, max-age=31536000  # 1 year

# Non-hashed files
Cache-Control: public, max-age=3600  # 1 hour
```

## Development Workflow

### Making CSS Changes

1. Edit `static/css/input.css` or Tailwind classes in templates
2. Run `npm run build:css` (or `npm run watch:css` for auto-rebuild)
3. Run `npm run hash:assets` to update hashed filenames
4. Refresh browser - new hash forces cache invalidation

### Making JS Changes

1. Edit JavaScript files in `static/js/`
2. Run `npm run build` to rebuild and rehash
3. Refresh browser - new hash forces cache invalidation

### Quick Rebuild

```bash
# Full rebuild (recommended)
npm run build

# Or individual steps
npm run build:css && npm run hash:assets
```

## Testing

The implementation includes comprehensive tests:

### Unit Tests (`tests/test_cache_busting.py`)
- Manifest file exists and has correct format
- Hashed files exist on disk
- Hashed content matches original files
- `hashed_url()` helper works correctly

### Integration Tests (`tests/test_cache_busting_integration.py`)
- Templates render with hashed URLs
- Flask serves hashed files correctly

Run tests:
```bash
pytest tests/test_cache_busting.py tests/test_cache_busting_integration.py -v
```

## Files Modified

### Created
- `scripts/hash-assets.js` - Hash generation script
- `static/manifest.json` - Filename mapping (generated)
- `tests/test_cache_busting.py` - Unit tests
- `tests/test_cache_busting_integration.py` - Integration tests
- `docs/CACHE_BUSTING.md` - This documentation

### Modified
- `package.json` - Added `hash:assets` script to build pipeline
- `app.py` - Added manifest loading and `hashed_url()` helper
- `templates/base.html` - Uses `hashed_url()` for CSS/JS
- `templates/login.html` - Uses `hashed_url()` for JS
- `templates/index.html` - Uses `hashed_url()` for JS
- `templates/verify.html` - Uses `hashed_url()` for JS
- `README.md` - Added frontend build documentation

## Troubleshooting

### Manifest not found
If you see unhashed URLs in production:
1. Run `npm run build` before deployment
2. Ensure `static/manifest.json` is included in deployment
3. Check Flask logs for manifest loading errors

### Old files cached
If browsers still load old versions:
1. Verify `npm run hash:assets` was run after file changes
2. Check that the hash in manifest.json changed
3. Hard refresh browser (Ctrl+Shift+R / Cmd+Shift+R)

### Build fails
If `npm run hash:assets` fails:
1. Ensure Node.js is installed
2. Run `npm install` to install dependencies
3. Check that source files exist in `static/css/` and `static/js/`

## Production Deployment

1. Run `npm run build` as part of deployment process
2. Ensure `static/manifest.json` is deployed with the app
3. Configure web server to serve static files with long cache headers
4. Consider using a CDN for static assets

## Related Requirements

- **Requirement 23.4**: Cache-Control Headers - Content-based filenames for cache busting
- **Requirement 13**: Tailwind CSS Build Pipeline - Integration with CSS build process
- **Requirement 14**: JavaScript Extraction - Separate JS files for caching
