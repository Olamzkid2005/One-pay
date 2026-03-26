---
inclusion: always
---

# Requesting Code Review Skill

Use when completing tasks, implementing major features, or before merging to verify work meets requirements.

## Core Principle

**Review early, review often.**

## When to Request Review

**Mandatory:**
- After completing major feature
- Before merge to main
- After fixing complex bug

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After implementing multiple related tasks

## How to Request

**1. Identify what changed:**
```bash
git diff HEAD~1  # or git diff origin/main
```

**2. Self-review checklist:**

Before asking for review, check:
- [ ] All tests pass
- [ ] No console errors or warnings
- [ ] Code follows project conventions
- [ ] No commented-out code
- [ ] No debug statements left in
- [ ] Error handling in place
- [ ] Edge cases covered
- [ ] Documentation updated if needed

**3. Request review from user:**

Provide context:
- What was implemented
- What it should do (reference spec/plan)
- Any concerns or questions
- Test results

**4. Act on feedback:**
- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if reviewer is wrong (with reasoning)

## Integration with Workflows

**After Major Features:**
- Review before merge
- Catch issues before they compound

**Ad-Hoc Development:**
- Review before merge
- Review when stuck

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed Important issues
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification
