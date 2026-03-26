---
inclusion: always
---

# Using Superpowers Skills Framework

This project uses the Superpowers skills framework - a systematic software development methodology for AI coding assistants.

## Core Principle

When working on ANY task, check if a relevant skill applies BEFORE taking action. Skills provide proven workflows that prevent common mistakes and ensure quality.

## Available Skills

The following skills are available as steering files in `.kiro/steering/`:

1. **brainstorming** - Design and spec creation before implementation
2. **test-driven-development** - TDD workflow (RED-GREEN-REFACTOR)
3. **systematic-debugging** - 4-phase root cause analysis
4. **writing-plans** - Breaking work into detailed implementation tasks
5. **requesting-code-review** - Pre-review checklist and quality gates
6. **verification-before-completion** - Ensuring fixes actually work

## When to Use Skills

- **Starting new features?** → Use brainstorming skill
- **Implementing code?** → Use test-driven-development skill
- **Fixing bugs?** → Use systematic-debugging skill
- **Planning work?** → Use writing-plans skill
- **Before committing?** → Use requesting-code-review skill

## Red Flags (Stop and Check for Skills)

These thoughts mean you should check for a relevant skill:

- "This is just a simple question" → Questions are tasks, check for skills
- "Let me explore the codebase first" → Skills tell you HOW to explore
- "I'll just do this one thing first" → Check BEFORE doing anything
- "This doesn't need a formal skill" → If a skill exists, use it
- "The skill is overkill" → Simple things become complex, use it

## Instruction Priority

1. **User's explicit instructions** - highest priority
2. **Superpowers skills** - override default behavior
3. **Default system prompt** - lowest priority

User instructions always take precedence over skills.

## Philosophy

- **Test-Driven Development** - Write tests first, always
- **Systematic over ad-hoc** - Process over guessing
- **Complexity reduction** - Simplicity as primary goal
- **Evidence over claims** - Verify before declaring success
