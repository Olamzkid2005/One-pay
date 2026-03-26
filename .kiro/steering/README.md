# Superpowers Skills Framework - Integrated

This directory contains the Superpowers skills framework adapted for Kiro IDE. These steering files provide systematic software development workflows that help prevent common mistakes and ensure quality.

## Available Skills

### Core Skills (Always Active)

1. **00-using-superpowers.md** - Framework overview and skill usage guidelines
2. **01-brainstorming.md** - Design and spec creation before implementation
3. **02-test-driven-development.md** - TDD workflow (RED-GREEN-REFACTOR)
4. **03-systematic-debugging.md** - 4-phase root cause analysis for bugs
5. **04-verification-before-completion.md** - Evidence-based completion verification
6. **05-writing-plans.md** - Breaking work into detailed implementation tasks
7. **06-requesting-code-review.md** - Pre-review checklist and quality gates

## Quick Reference

### When to Use Each Skill

| Situation | Use This Skill |
|-----------|---------------|
| Starting new feature | 01-brainstorming |
| Implementing code | 02-test-driven-development |
| Fixing bugs | 03-systematic-debugging |
| About to claim "done" | 04-verification-before-completion |
| Planning multi-step work | 05-writing-plans |
| Before merging/committing | 06-requesting-code-review |

## Philosophy

- **Test-Driven Development** - Write tests first, always
- **Systematic over ad-hoc** - Process over guessing
- **Complexity reduction** - Simplicity as primary goal
- **Evidence over claims** - Verify before declaring success

## How It Works

These steering files are automatically included in your Kiro context. The AI assistant will follow these workflows when working on your project, ensuring:

- Designs are validated before implementation
- Tests are written before code
- Bugs are debugged systematically
- Work is verified before completion
- Code is reviewed before merging

## Customization

You can:
- Add project-specific steering files
- Modify existing skills (edit the .md files)
- Disable skills by changing `inclusion: always` to `inclusion: manual`

## Source

Adapted from [obra/superpowers](https://github.com/obra/superpowers) - An agentic skills framework & software development methodology.

## License

MIT License (inherited from superpowers project)
