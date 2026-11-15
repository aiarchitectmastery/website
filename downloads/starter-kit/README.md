# AI Driven Development Workflow Starter Pack
**by AI Architect Mastery · aiarchitectmastery.com**
*Version 3.1*
---

## What this is

Seven ready-to-use Markdown resources plus this README for the **AI Driven Development Methodology**. The Starter Pack uses the existing `starter-kit.zip` download URL.

The methodology has four phases:

```
PRD  →  PLAN  →  TASK  →  IMPLEMENTATION
```

| Phase | File | What it does |
|---|---|---|
| **PRD** | `PRD-template.md` | Define and approve what you want to build before implementation; AI may help draft |
| **PLAN** | `PLAN-template.md` | Break the PRD into structured tasks for agent execution |
| **TASK** | `TASK-prompt-template.md` | Give Copilot precise, context-rich instructions — one task at a time |
| **IMPLEMENTATION** | `IMPLEMENTATION-checklist.md` | Review what the agent built before it merges — a human checklist, not a fill-in template |
| **Task context** | `bounded-task-template.md` | Define five parts of a bounded task and request a read-only gap check before edits |
| **Session continuity** | `fresh-session-handoff.md` | Prepare a handoff, then verify it against current sources in a new conversation |
| **Guidance review** | `agent-guidance-review-prompts.md` | Analyze existing instructions, approve one bounded change and check procedure loading without removing safeguards |

The public [methodology reference](https://aiarchitectmastery.com/methodology/) explains the structure independently of any course purchase.

---

## How to use it — in 6 steps

**Step 1.** Copy the resources you need into your project repository. Keep project-specific context with the relevant work.

**Step 2.** Fill in `PRD-template.md` for your current feature or project. The human owner reviews and approves the intent, scope and acceptance criteria before implementation planning proceeds.

**Step 3.** Open Copilot Chat and say:
> *"Read this PRD and generate an implementation plan."*

**Step 4.** Review the output and structure it using `PLAN-template.md`. The human owner approves the approach before delegating TASKs.

**Step 5.** For each authorized task in the approved plan, use `TASK-prompt-template.md` to give Copilot bounded instructions. State when to stop and ask, and require actual check results and any unexecuted checks in the return.

**Step 6.** Before merging, work through `IMPLEMENTATION-checklist.md` for the TASK you just completed — scope, tests, conventions, security and edge cases.

> **Human checkpoints are mandatory.** Never merge AI-generated code without review. You are the architect — Copilot is the builder.

Record the human decision against the reviewed work and evidence. Acceptance does not by itself authorize release or deployment. These written instructions do not enforce runtime permissions.

For a focused task, use `bounded-task-template.md` to state the goal, current observation, relevant sources, constraints and acceptance criteria. Ask the agent to surface gaps read-only before edits.

When moving to a fresh conversation, use the two prompts in `fresh-session-handoff.md`. Review the handoff yourself and verify it against current sources before continuing; it is not proof that a check passed.

## Resources used in the P08, P09 and P10 videos

Start with the resource that matches your current task; you do not need to use
every file or install a multi-agent framework.

| Video | Downloaded resource | Start here |
|---|---|---|
| **P08 - Review Copilot agent guidance** | [agent-guidance-review-prompts.md](agent-guidance-review-prompts.md) | Run prompt 1 for analysis only. Review the proposal, then use prompt 2 to authorize one stage. Run the positive and negative controls in separate fresh conversations; use the same controls before and after where practical. |
| **P09 - Give a task the right context** | [bounded-task-template.md](bounded-task-template.md) | Fill in the goal, current observation, sources, constraints and acceptance criteria. Request the read-only gap check before approving edits. |
| **P10 - Move to a fresh conversation** | [fresh-session-handoff.md](fresh-session-handoff.md) | Use prompt 1 in the old conversation, review the note yourself, then use prompt 2 with the reviewed note and current sources in the new conversation. |

P08 is optional: it assumes your project already has guidance to review. Its
prompts adapt the video's workflow to your own project; they are not the
synthetic demo's fixture-specific prompts. Replace placeholders, respect the
active agent's tool restrictions, and do not treat shorter files or a plausible
answer as proof of performance or correct loading.

### Version 3.1

Added the P08 guidance-review prompts and this video-to-resource guide.
The P09 bounded task brief and P10 handoff prompts were already included in
version 3.0 and remain unchanged.

---

## The core principle

Most developers use AI tools reactively — accept a suggestion, fix it, try again. This kit makes your AI usage **proactive and structured**:

- The **PRD** tells the AI what success looks like
- The **PLAN** tells the AI what to build and in what order
- The **TASK prompt** tells the AI exactly how to build one piece — with constraints, context, and verification criteria
- The **IMPLEMENTATION checklist** tells you what to verify before anything ships

The goal is more consistent work and architectural control. Actual quality still depends on the task, environment, verification and human judgment.

---

## What's next

This kit now covers all four phases of the AI Driven Development Methodology. For guidance on using these resources and more advanced scenarios, visit:

- **[Agent Journey: Milestone 1](https://aiarchitectmastery.com/get-started/)** — Start your AI Driven Development practice
- **[GitHub Copilot GH-300 Certification Prep](https://www.udemy.com/course/github-copilot-gh-300-certification-prep/?referralCode=54F80FD551971153D6E5)** — Certification-focused course; check Udemy for the current syllabus, availability and price

---

*AI Architect Mastery — Human as architect. AI as builder.*
*Questions or feedback: info@aiarchitectmastery.com*
