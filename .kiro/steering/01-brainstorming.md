---
inclusion: always
---

# Brainstorming Skill - Design Before Implementation

Use this skill BEFORE any creative work: creating features, building components, adding functionality, or modifying behavior.

## Hard Gate

Do NOT write any code, scaffold any project, or take implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through this process. Even simple projects need design. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but you MUST present it and get approval.

## Process Checklist

1. **Explore project context** - check files, docs, recent commits
2. **Ask clarifying questions** - one at a time, understand purpose/constraints/success criteria
3. **Propose 2-3 approaches** - with trade-offs and your recommendation
4. **Present design** - in sections scaled to their complexity, get user approval after each section
5. **Write design doc** - save to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commit
6. **User reviews written spec** - ask user to review the spec file before proceeding
7. **Transition to implementation** - create implementation plan

## The Process

**Understanding the idea:**
- Check current project state first (files, docs, recent commits)
- Assess scope: if request describes multiple independent subsystems, flag immediately
- If project too large for single spec, help user decompose into sub-projects
- Ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible
- Focus on: purpose, constraints, success criteria

**Exploring approaches:**
- Propose 2-3 different approaches with trade-offs
- Present options conversationally with your recommendation
- Lead with your recommended option and explain why

**Presenting the design:**
- Present design once you understand what you're building
- Scale each section to its complexity (few sentences if straightforward, up to 200-300 words if nuanced)
- Ask after each section whether it looks right
- Cover: architecture, components, data flow, error handling, testing
- Be ready to clarify if something doesn't make sense

**Design for isolation and clarity:**
- Break system into smaller units with one clear purpose each
- Units should communicate through well-defined interfaces
- Each unit should be understandable and testable independently
- For each unit: what does it do, how do you use it, what does it depend on?

**Working in existing codebases:**
- Explore current structure before proposing changes
- Follow existing patterns
- Include targeted improvements where existing code has problems that affect the work
- Don't propose unrelated refactoring

## After the Design

**Documentation:**
- Write validated design (spec) to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Commit the design document to git

**User Review Gate:**
Ask user to review the written spec before proceeding:
> "Spec written and committed to `<path>`. Please review it and let me know if you want to make any changes before we start writing out the implementation plan."

Wait for user's response. If they request changes, make them. Only proceed once user approves.

**Implementation:**
- Create a detailed implementation plan
- Break work into bite-sized tasks (2-5 minutes each)

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design, get approval before moving on
- **Be flexible** - Go back and clarify when something doesn't make sense
