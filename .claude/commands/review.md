# Code Review

Review the current git changes (staged and unstaged) for this project. Check for:
- Security vulnerabilities (SQL injection, XSS, CSRF, secrets in code)
- Performance issues (N+1 queries, missing indexes, inefficient caching)
- Error handling gaps (missing try/except, unhandled edge cases)
- Code quality (duplication, overly complex logic, missing type hints)
- Test coverage for changed code
- Breaking changes to existing APIs

Output a structured review with:
1. **Critical issues** (must fix before merge)
2. **Suggestions** (improvements to consider)
3. **Approved patterns** (things done well)

Focus on the files that were actually changed, not the entire codebase.
