# Adding a skill

Every skill is one folder under `skills/`. Adding one touches nothing else in the repo except the catalogue listings.

## Steps

1. **Copy the template** and name the folder in lowercase kebab-case. Describe what it does, not how: `scroll-motion-graphics`, not `gsap-helper`.

   ```bash
   cp -r template skills/my-skill-name
   ```

2. **Write `SKILL.md`.** The `name` must match the folder. The `description` is how an agent decides to use the skill, so say *when* to use it, and keep it under 1024 characters.

3. **Add it to the catalogue,** in two places:
   - `.claude-plugin/marketplace.json`: one entry in `plugins`.
   - `README.md`: one row in the Skills table with a preview image in `docs/previews/`, and the badge count.

4. **Check it:**

   ```bash
   python scripts/validate_skills.py
   ```

   The same check runs on every push.

## What makes a skill good enough for this repo

- **Test it blind.** Give a fresh agent with no context only the skill and a one-line request. Fix whatever confuses it. This finds problems nothing else does.
- **Use a router, not a wall of text.** Keep `SKILL.md` short: when to use it, the steps, hard rules. Long detail goes in `references/`, with a line saying when to load each file.
- **Make the steps verifiable.** Give the agent commands that check the work, and say what "done" means. Include a real sample so it can see the target.
- **Say what is unverified.** Never claim a result you did not measure.
- **Avoid sample text that gets copied.** If examples can leak into the output, block that with a check.

## Rules

- **No secrets:** no API keys, tokens or `.env` files. Keys come from environment variables.
- **No personal data or machine paths.**
- **Third-party material:** record its licence in `THIRD_PARTY_NOTICES.md`. Only bundle what its licence allows. Never bundle GPL, AGPL or non-commercial code or models in an MIT skill.
- **Keep it small:** no `node_modules`, virtual environments or build output, and no single file over 25 MB.
- **Versions:** bump `version` in the skill's frontmatter when behaviour changes.

## Publishing to imutechz.in

The website serves a copy of each skill from its own repo. After a change is merged here, mirror the skill folder into `frontend/public/skills/<skill-name>` in the website repo, and add a listing in its `lib/skill.js`.
