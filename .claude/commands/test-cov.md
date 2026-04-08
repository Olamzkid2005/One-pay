# Run with Coverage

Run tests with code coverage report:

```bash
cd /Users/mac/Documents/One-pay && .venv/bin/python -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
```

After running, open `htmlcov/index.html` in a browser to view detailed coverage.

Report:
- Overall coverage percentage
- Files with lowest coverage
- Any uncovered critical paths
