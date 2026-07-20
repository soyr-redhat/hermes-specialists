# hermes-specialists

configure, build, and deploy specialist [hermes](https://github.com/NousResearch/hermes-agent) agents for enterprise and multi-tenant serving.

one model, many specialists. each specialist gets its own system prompt, skills, and context - packaged into a container and deployed as a pod.

## install

```bash
pip install -e .
```

## usage

```bash
hs
```

```
               -###########*.
            -###*====+====+####
          =####*=========+==+####
         ######==*#**========#####+
        ####***===============#####*
       ##======##*============*#####-
       ##*=======*####===========*###
      *####+==========+============##
      *######*=====================##
      -#####+   #================+###
       *    *      ##*+=======+#####*
                             *######
                       -.    ######
                            ##
                          *

  hermes specialists
  enterprise & multi-tenant agent serving

  2 specialists  ·  endpoint: https://maas.example.com/v1  ·  gemma4

  ────────────────────────────────────────
  > manage specialists
    manage skills
    configure vllm endpoints
    build & deploy containers
    view configuration
    ─────────────
    help & troubleshooting
```

## quick start

### 1. create a specialist

```bash
hs  # -> manage specialists -> create new
```

this creates the directory structure:

```
specialists/
  my-bot/
    specialist.yaml       # name, endpoint, model
    system-prompt.md      # who the agent is
    skills/
      my-skill/
        SKILL.md          # skill instructions
```

### 2. write a system prompt

```markdown
# my-bot

you are my-bot, a helpful coding assistant who specializes in python.
```

### 3. add skills

just drop a folder with a `SKILL.md` into `skills/` - auto-discovered at build time.

```markdown
---
description: review pull requests
trigger: when the user asks for a code review
---

review the code for bugs, style issues, and security concerns.
provide clear, actionable feedback.
```

### 4. deploy

```bash
hs  # -> build & deploy -> deploy all to openshift
```

builds container images with podman, pushes to your registry, and applies the deployment manifest. each specialist gets its own pod with a persistent volume.

## navigation

- **arrow keys** - move up/down
- **enter** - select
- **left arrow** - go back
- **ctrl+c** - exit
