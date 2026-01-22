# Architectural Decision Records (ADRs)

This directory contains records of architectural decisions made for the EchoNet project.

## About ADRs

Architectural Decision Records (ADRs) capture important architectural decisions along with their context and consequences. They help:

- **Document why** decisions were made (not just what was decided)
- **Preserve context** for future developers
- **Track evolution** of the system over time
- **Enable informed changes** by understanding previous trade-offs

## Format

Each ADR follows this structure:

1. **Title** - Short, descriptive name
2. **Status** - Proposed, Accepted, Deprecated, Superseded
3. **Context** - What problem are we solving?
4. **Decision** - What did we decide?
5. **Rationale** - Why did we decide this?
6. **Alternatives** - What else did we consider?
7. **Consequences** - What are the positive/negative outcomes?
8. **Implementation** - How is this implemented?

## Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](./001-automatic-active-mode-reset.md) | Automatic Reset from Active to Trigger Mode | Accepted | 2026-01-21 |

## Creating New ADRs

When making significant architectural decisions:

1. **Copy the template** from an existing ADR
2. **Number sequentially** (002, 003, etc.)
3. **Write clearly** - future you will thank you
4. **Include context** - explain the problem, not just the solution
5. **Consider alternatives** - show what you evaluated
6. **Document consequences** - both positive and negative

## When to Create an ADR

Create an ADR when you make decisions about:

- **System architecture** - Major structural changes
- **Technology choices** - Frameworks, libraries, tools
- **Integration patterns** - How systems communicate
- **Data models** - Significant schema or state changes
- **Security** - Authentication, authorization, data protection
- **Performance** - Caching strategies, optimization approaches
- **Deployment** - Infrastructure, scaling, monitoring

## When NOT to Create an ADR

Don't create ADRs for:

- Implementation details (use code comments)
- Bug fixes (use commit messages)
- Minor refactoring (use PR descriptions)
- Temporary workarounds (use TODO comments)

## Related Documentation

- [ASR Worker Architecture](../ASR_WORKER.md)
- [State Management](../../STATE_MANAGEMENT.md)
- [Testing Strategy](../TESTING.md)
