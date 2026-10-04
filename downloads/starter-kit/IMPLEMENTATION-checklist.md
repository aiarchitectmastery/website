# IMPLEMENTATION Checklist
> Use this checklist before merging any AI-generated code — for every TASK, every time.
> Unlike PRD/PLAN/TASK, this is not a fill-in-the-blank template for the agent to read.
> It's the human review habit: the check the architect runs before approving what the agent built.

---

## Task Being Reviewed

**Task reference:** [TASK-XXX title, from your PLAN]
**Reviewer:** [Your name]
**Date:** [YYYY-MM-DD]
**Reviewed revision and environment:** [commit/content version · runtime/test environment]
**Approved PRD / PLAN and task authorization:** [versioned references]

---

## 1. Scope Compliance

<!-- Does the change actually satisfy the TASK — and stay inside its scope? -->
- [ ] The change does what the TASK asked — nothing more, nothing less
- [ ] No unrelated files were modified
- [ ] No public API, interface, or contract changed without explicit approval

---

## 2. Tests

<!-- Do tests exist, and do they pass — not just "does it look right"? -->
- [ ] Tests exist for the new or changed behavior
- [ ] All tests pass locally — not just "looks right"
- [ ] Edge cases from the TASK's acceptance criteria are covered

---

## 3. Conventions

<!-- Does it follow the project's existing conventions and architecture? -->
- [ ] Code style matches the existing codebase (naming, structure, patterns)
- [ ] No new dependencies added without approval
- [ ] Follows the architectural decisions recorded in the PLAN

---

## 4. Security & Edge Cases

<!-- Have security, performance, and edge cases been considered, not just the happy path? -->
- [ ] No secrets, credentials, or sensitive data introduced
- [ ] Input validation and error handling cover realistic failure modes
- [ ] Performance-sensitive paths reviewed, not just functionally tested

---

## 5. Evidence and Human Decision

| Check or reviewed artifact | Actual result | Evidence reference |
|---|---|---|
| [command, diff or runtime observation] | [observed result, not expectation] | [log/artifact/revision] |

**Unexecuted checks and limitations:** [what remains unknown and why]
**Human verdict:** [ACCEPT / REVISE / REJECT / REASSIGN / RETURN]
**Rationale, reviewer and date:** [how the evidence supports the decision]
**If RETURN:** [PRD / PLAN / TASK, issue to resolve and dependent work to refresh]

Acceptance does not by itself authorize merge, release or deployment. Apply the
project's separate delivery permissions; never infer them from passing tests.

## The Non-Negotiable Rule

**Nothing merges without human review.** This is what keeps AI-generated code held to the same standard as human-generated code — production quality is not optional, regardless of how the code was written.

If a required check is incomplete, do not record acceptance. Request a scoped
revision when the agreed expectation is clear. If intent, approach or assignment
is inadequate, record RETURN to the relevant PRD, PLAN or TASK and refresh
dependent work before continuing.

---

*Implementation review · Based on TASK: [reference] · Last reviewed: [YYYY-MM-DD]*
*Part of the AI Driven Development Methodology — aiarchitectmastery.com*
