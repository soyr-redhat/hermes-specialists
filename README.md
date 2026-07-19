# hermes-specialists

a user-friendly interface for enterprise and multi-tenant agent serving. configure, build, and deploy specialist [hermes](https://github.com/NousResearch/hermes-agent) agents — each tailored to a specific task, repo, or domain — backed by a shared model endpoint (vllm, ollama, etc.) and deployed to openshift or kubernetes.

the idea is simple: one fat model, many specialists. each specialist gets its own personality, toolset, skills, and context, packaged into a container image and deployed as a pod. adding a new specialist is a config problem, not an infrastructure problem.

## install

```bash
pip install -e .
```

## usage

```bash
hermes-specialists
# or
hs
```

## what it does

- **dashboard** — view and manage all configured specialists
- **endpoints** — configure vllm endpoints (global or per-specialist)
- **editor** — create specialists with custom system prompts, toolsets, skills, and repo context
- **build & deploy** — generate container images and deploy to openshift with one action
