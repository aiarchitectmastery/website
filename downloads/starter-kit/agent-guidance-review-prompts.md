# Agent Guidance Review Prompts

Use these prompts to review existing GitHub Copilot instructions without losing
responsibilities, permissions or mandatory checks. This is an optional resource
for projects that already have agent guidance, not a prerequisite for your first
bounded task.

The sequence is: analyze, review the proposal yourself, approve one bounded
change, inspect the diff, then verify behavior in fresh conversations.
These prompts do not enforce tool permissions or guarantee performance gains.
Use your environment's permission controls and review every proposed change.

## 1. Analyze and propose only

Open the project you are authorized to inspect. Paste this prompt into Copilot
Chat. Do not include secrets or private material you are not allowed to share.

```text
Analyze this GitHub Copilot environment's agent guidance and propose
optimizations. The goal is to reduce unnecessarily loaded context and
duplication without changing responsibilities, permissions or mandatory checks.

Analysis only: do not edit files, run commands, access the network, commit,
push or change external systems. Use permitted local read/search tools only.
Follow the environment's applicable instructions; stop if they conflict with
this request or required inspection is unavailable.

1. Locate applicable shared instructions, agent definitions, file-specific
instructions, skills, prompts and referenced documentation. Start with metadata
and references, then read details selectively. Do not assume particular paths,
customization formats or loading mechanisms.
2. Distinguish always-loaded content, active-role instructions, conditionally
attached instructions and on-demand procedures. Separate documented behavior,
observed loading evidence and assumptions. Previously read content may remain
in the conversation.
3. Identify duplication, contradictions, outdated guidance and procedures that
could use an existing on-demand mechanism. Do not create skills just to split
files or preload all skills and references.
4. Preserve role identity, tool restrictions, approval gates, security, secret
handling and mandatory checks in applicable shared or role-specific guidance.
A skill must not grant permissions. Surface conflicts; do not silently decide
which authority to follow.
5. Propose small named stages. For each, list exact files, what would move or
change, what must remain, benefits, risks, and a verification method. Include a
harmless positive test that needs the changed procedure and a negative control
that does not. Use the same tests and model before and after the change.
6. Report unavailable evidence and inspection limits. File length or word count
is not a measured token cost, latency reduction or quality improvement.

Return the current-state analysis and staged proposal. Do not implement.
Wait for my approval of one named stage.
```

Review the proposal against the actual files. Resolve conflicts and missing
information before proceeding. If practical, record both baseline tests below
before approving a change.

## 2. Authorize one reviewed stage

Replace every bracketed value. Use an agent permitted to edit the named files;
an approval prompt must not override a read-only agent's restrictions.

```text
I approve only stage [STAGE ID] from the reviewed proposal [REFERENCE].
The authorized files and changes are: [EXACT FILES AND CHANGES].
The responsibilities and safeguards that must remain are: [BOUNDARIES].

Recheck the current files and applicable instructions before editing. If they
conflict with the reviewed proposal, or a required change is outside this scope,
stop and report the issue. Preserve unrelated work and existing tool permissions.
Do not run commands, access the network, commit, push or change external systems.

Implement only this stage with permitted local editing tools. Update references
and loading triggers within the authorized scope. Show the diff if available,
or an exact change summary if it is not. Report checks actually performed,
unperformed checks and remaining risks. Stop before any further stage.
```

Inspect the diff yourself. Reload/restart the Copilot environment as appropriate
so the changed guidance is available. Use a fresh conversation for each control,
with the same agent, model, task and evidence criteria as the baseline.

## 3. Positive control: the procedure is needed

Choose a harmless read-only task, not a real release or production operation.
Replace the placeholders with the role, task and expected procedure from your
reviewed proposal. Run this separately for each affected agent.

```text
Read-only dry run for [AGENT ROLE] in a fresh conversation.
Task: [SMALL HARMLESS TASK THAT NEEDS THE CHANGED PROCEDURE].
Expected procedure or skill: [NAME OR PATH].

Use permitted local read/search tools only. Do not edit files, run commands,
call live APIs, access the network, commit, push, publish or change external
systems. Do not invent missing evidence or approval.

Follow applicable guidance and load only the procedure needed for this task,
using this environment's supported mechanism. Report:
- The shared and active-role instructions governing the response.
- Whether and when the expected procedure was loaded, citing observable file
  reads or runtime/tool events, not just your own assertion.
- Whether the required output and mandatory boundaries were preserved.
- Whether unrelated procedures were loaded and why.
- Missing, conflicting or stale guidance and any verification limits.

If loading events are not observable, say loading cannot be verified.
A correct-looking answer alone is not proof of loading.
```

## 4. Negative control: the procedure is not needed

Run this in another fresh conversation for the same agent. Replace the role
and procedure placeholders.

```text
Read-only dry run. Explain [AGENT ROLE]'s role and permission boundaries in
three bullets from its applicable guidance. This task does not require
[CHANGED PROCEDURE OR SKILL].

Do not perform the specialized task, read its evidence, edit files, run
commands, access the network, commit, push or change external systems.
Do not load a specialized procedure unless the task actually requires it.
If applicable instructions require an unexpected load, report that conflict.

Identify observable instruction or tool events used. If the environment does
not expose reliable loading evidence, say loading cannot be verified.
```

## How to interpret the checks

- **Positive control:** the needed procedure is observably loaded when needed,
  the required result is produced and mandatory boundaries remain intact.
- **Negative control:** the simple role question is answered without loading
  the specialized procedure unnecessarily.
- **Inconclusive:** no reliable loading evidence is available. Do not infer
  success from a plausible answer.
- **Performance:** compare equivalent tasks using available context/token/timing
  telemetry before and after. Shorter files and a single run do not establish
  faster or cheaper work.

Record failures and missing evidence, not just successful responses. A passing
control is limited evidence for that scenario, not proof every task is safe.
Human review decides whether to retain, revise or revert the bounded change.
