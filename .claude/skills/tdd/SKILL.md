---
inclusion: auto
---

# TDD (Test-Driven Development) Skill

Use test-driven development to implement features or fix bugs.

## When to Use
- User wants test-first development
- User mentions "TDD", "red-green-refactor", or "test-first"
- User wants to add new feature with tests
- Fixing bug - write failing test first

## TDD Workflow
1. **Red**: Write a failing test for the new behavior
2. **Green**: Write minimal code to make test pass
3. **Refactor**: Improve code while keeping tests passing

## Run Tests Continuously
```bash
# Watch mode (reruns on file changes)
pytest tests/ -v --watch
```

## Example TDD Session
```python
# 1. Write failing test
def test_new_feature_returns_correct_format():
    result = service.new_feature()
    assert result["status"] == "success"

# 2. Run to see failure
pytest tests/ -k test_new_feature -v

# 3. Implement minimal code
def new_feature():
    return {"status": "success"}

# 4. Run to see pass
pytest tests/ -k test_new_feature -v

# 5. Refactor and add more tests
```

## OnePay Testing Guidelines
- Tests in `tests/unit/` for isolated tests
- Tests in `tests/integration/` for full flows
- Use `pytest-mock` for mocking
- Use `hypothesis` for property-based testing
- Mock mode available for KoraPay testing
