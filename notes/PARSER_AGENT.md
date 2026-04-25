# ClawEase Parser Agent

## One line

`clawease-intent` is the product-side parser agent for ClawEase.

It is not a general assistant.
It exists only to turn one Chinese elder utterance into one structured JSON object.

## What it should do

1. Understand what the elder actually wants.
2. Extract the action and key details.
3. Mark risk and ambiguity explicitly.
4. Ask for clarification when a family role or pronoun is too vague.

## What it should not do

- bootstrap talk
- onboarding
- self-introduction
- workspace chatter
- markdown explanations
- tool use
- free-form conversation

## Files

- Workspace: [AGENTS.md](E:\aNB\Ease-claw\openclaw\clawease-intent-workspace\AGENTS.md)
- Fixed override: [clawease-intent-system-prompt.txt](E:\aNB\Ease-claw\openclaw\clawease-intent-system-prompt.txt)
- Install script: [install_clawease_parser_agent.ps1](E:\aNB\Ease-claw\scripts\install_clawease_parser_agent.ps1)

## Local install

```powershell
.\scripts\install_clawease_parser_agent.ps1
```

This updates `C:\Users\ZHUyi\.openclaw\openclaw.json` and refreshes the `clawease-intent` agent entry with:

- fixed workspace
- fixed model
- fixed `systemPromptOverride`

## Cloud deploy

Your current cloud gateway only exposes `main`, not `clawease-intent`.

So for cloud rollout, the gateway config must include the same agent entry.

After that, set:

```powershell
$env:OPENCLAW_CLOUD_AGENT_ID='clawease-intent'
```

Then `scripts/openclaw_cloud_intent.mjs` can route to the parser agent directly.

## Current limitation

Until the cloud gateway adds `clawease-intent`, the product still talks to `main` and uses request-level guardrails to suppress bootstrap chatter.
