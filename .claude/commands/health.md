# Check Health

Check the health of the OnePay application and its dependencies:

1. Run the health endpoint:
```bash
curl -s http://localhost:5000/health 2>/dev/null || echo "Server not running"
```

2. Check database connectivity:
```bash
cd /Users/mac/Documents/One-pay && .venv/bin/python -c "from database import engine; print('DB OK' if engine.connect())"
```

3. Check environment configuration:
```bash
cd /Users/mac/Documents/One-pay && .venv/bin/python -c "from config import Config; print(f'APP_ENV={Config.APP_ENV}', f'DEBUG={Config.DEBUG}')"
```

Report status of each component.
