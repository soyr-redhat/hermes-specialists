# hermes-specialists

configure, build, and deploy specialist [hermes](https://github.com/NousResearch/hermes-agent) agents for enterprise and multi-tenant serving.

one model, many specialists. each specialist gets its own system prompt, skills, and context, packaged into a container and deployed as a pod.

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

## how it works

1. create a specialist (name, endpoint, model)
2. edit `specialists/<name>/system-prompt.md` to define behavior
3. drop SKILL.md files into `specialists/<name>/skills/`
4. build and deploy to openshift
