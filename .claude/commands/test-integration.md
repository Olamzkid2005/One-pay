# Run Integration Tests

Run only integration tests:

```bash
cd /Users/mac/Documents/One-pay && .venv/bin/python -m pytest tests/integration/ -v --tb=short
```

Note: Integration tests may require external services (KoraPay API, etc.) to be configured. Report if tests are skipped due to missing configuration.
