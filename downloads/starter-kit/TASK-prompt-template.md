# Copilot Agent Task Prompt Template
> Use this structure when giving tasks to GitHub Copilot Agent Mode or Copilot Chat.
>
> Structure: Role → Context → Task → Constraints → Output → Verification
>
> How to use: copy the template below, fill it in for your current PLAN task,
> then supply it as the current assignment in Copilot Chat. Keep one-off task
> authorization separate from persistent repository instructions.

---

## Template

```
You are a [role — e.g., "senior Java developer following Clean Architecture principles"].

## Context
[Describe the current state of the codebase / what already exists.]
- Tech stack: [language, framework, key libraries]
- Relevant files: [list the files the agent should read before starting]
- This task is part of: [approved PRD version · approved PLAN version and step ID]
- Authorized by: [human owner · decision reference · permitted scope]

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

## Autonomy and Stop Conditions
- Continue only within the authorized scope and available permissions.
- Stop and report missing context, permissions, verification tools or an ambiguous policy.
- Do not invent a decision, bypass access controls, broaden scope or claim an unrun check passed.
- Return the issue to the human owner for a PRD, PLAN or TASK decision as appropriate.
- This assignment does not authorize merge, publication or deployment.

## Verification
Before finishing, confirm:
- [ ] Code compiles without errors
- [ ] All tests pass
- [ ] No new dependencies added without approval
- [ ] Acceptance criteria from PLAN task [TASK-ID] are met

Return the reviewed revision, changed files and actual evidence: check/command,
environment, observed result and artifact or log reference. List failed and
unexecuted checks, remaining limitations and the decision needed from the human.
```

---

## Filled example

Constructed assignment, not a tested implementation or a real approval record.

```
You are a senior Spring Boot developer following Clean Architecture principles.

## Context
- Tech stack: Java 21, Spring Boot 3.x, Maven, PostgreSQL
- Relevant files: src/main/java/com/example/user/UserService.java, UserRepository.java
- This task is part of: example approved PRD v1.2 · example approved PLAN v1.0, TASK-003
- Authorization: the example human owner permits only this endpoint and its tests
- ASSUMPTION: existing authentication and admin-authorization helpers are available; verify before changing code

## Task
Implement a REST endpoint POST /api/v1/users that:
1. Requires an authenticated administrator using the existing authorization helper
2. Accepts only name and email; validates required name and email format
3. Creates only a USER account; rejects a supplied role field without persistence
4. Returns 201 Created with a response DTO containing only id, name and email, never the persistence entity
5. Returns the established unauthenticated/forbidden error response without creating a record for denied callers

## Constraints
- DO NOT modify the UserRepository interface or add another persistence implementation
- DO NOT add new Maven dependencies
- Follow the existing validation pattern used in OrderService.java

## Expected Output
- UserController.java: new POST /api/v1/users endpoint
- CreateUserRequest.java: new DTO with Bean Validation annotations
- UserResponse.java: response DTO with the exact allowed fields
- UserControllerTest.java: checks for valid admin creation, unauthenticated/non-admin denial, rejected role, invalid email, missing name and response field allowlist

## Autonomy and Stop Conditions
- Stop if the existing authorization or repository contract cannot satisfy this assignment.
- Ask the human to revise the PLAN or TASK instead of inventing a policy or bypass.
- No merge or deployment authorization.

## Verification
- [ ] mvn test passes
- [ ] POST /api/v1/users returns 201 for valid input
- [ ] POST /api/v1/users returns 400 with error detail for invalid input
- [ ] No new Maven dependencies introduced
- [ ] Unauthenticated/non-admin callers and supplied role fields create no records
- [ ] The response contains only id, name and email

Return actual commands, environment, results and revision; list unexecuted checks
and limitations. A confident summary is not evidence of passing tests.
```

---

## Tips for better Copilot output

**Be specific about files.** Reference existing files by name — Copilot uses them as style and pattern context.

**State what NOT to do.** Constraints make prohibited changes explicit, but do not enforce themselves. Verify dependencies, interfaces and conventions in the returned diff and results.

**One task at a time.** Giving Copilot a single, well-defined task produces better output than a multi-feature prompt. Keep tasks small enough to verify completely before moving on.

**Reset context between tasks.** Open a fresh Copilot Chat for each task. Accumulated conversation context from previous tasks can degrade output quality.

---

*Part of the AI Driven Development Methodology — aiarchitectmastery.com*
