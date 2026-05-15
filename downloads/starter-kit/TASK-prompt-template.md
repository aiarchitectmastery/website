# Copilot Agent Task Prompt Template
> Use this structure when giving tasks to GitHub Copilot Agent Mode or Copilot Chat.
>
> Structure: Role → Context → Task → Constraints → Output → Verification
>
> How to use: copy the template below, fill it in for your current PLAN task,
> then paste it into Copilot Chat or your .github/copilot-instructions.md file.

---

## Template

```
You are a [role — e.g., "senior Java developer following Clean Architecture principles"].

## Context
[Describe the current state of the codebase / what already exists.]
- Tech stack: [language, framework, key libraries]
- Relevant files: [list the files the agent should read before starting]
- This task is part of: [PRD version · PLAN task ID, e.g., TASK-003]

## Task
[Describe exactly what to build or change. Be specific and complete.]
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Constraints
- DO: [what the agent must do]
- DO NOT: [what the agent must avoid — e.g., modify public API, add new dependencies]
- Follow: [coding conventions, naming standards, patterns already in use in this codebase]

## Expected Output
- [File 1]: [what should be in it — class, method, endpoint, etc.]
- [File 2]: [what should be in it]
- Tests: [what tests should be written and what they must verify]

## Verification
Before finishing, confirm:
- [ ] Code compiles without errors
- [ ] All tests pass
- [ ] No new dependencies added without approval
- [ ] Acceptance criteria from PLAN task [TASK-ID] are met
```

---

## Filled example

```
You are a senior Spring Boot developer following Clean Architecture principles.

## Context
- Tech stack: Java 21, Spring Boot 3.x, Maven, PostgreSQL
- Relevant files: src/main/java/com/example/user/UserService.java, UserRepository.java
- This task is part of: PRD v1.2 · PLAN TASK-003

## Task
Implement a REST endpoint POST /api/v1/users that:
1. Accepts a CreateUserRequest DTO with fields: name, email, role
2. Validates input — name required, email format valid, role must be USER or ADMIN
3. Persists the user via UserRepository
4. Returns 201 Created with the created User entity as JSON

## Constraints
- DO NOT modify the UserRepository interface — create a new implementation if needed
- DO NOT add new Maven dependencies
- Follow the existing validation pattern used in OrderService.java

## Expected Output
- UserController.java: new POST /api/v1/users endpoint
- CreateUserRequest.java: new DTO with Bean Validation annotations
- UserControllerTest.java: unit tests covering valid input, invalid email, and missing name

## Verification
- [ ] mvn test passes
- [ ] POST /api/v1/users returns 201 for valid input
- [ ] POST /api/v1/users returns 400 with error detail for invalid input
- [ ] No new Maven dependencies introduced
```

---

## Tips for better Copilot output

**Be specific about files.** Reference existing files by name — Copilot uses them as style and pattern context.

**State what NOT to do.** Constraints prevent the most common AI drift: adding dependencies, changing interfaces, ignoring existing patterns.

**One task at a time.** Giving Copilot a single, well-defined task produces better output than a multi-feature prompt. Keep tasks small enough to verify completely before moving on.

**Reset context between tasks.** Open a fresh Copilot Chat for each task. Accumulated conversation context from previous tasks can degrade output quality.

---

*Part of the AI Driven Development Methodology — aiarchitectmastery.com*
