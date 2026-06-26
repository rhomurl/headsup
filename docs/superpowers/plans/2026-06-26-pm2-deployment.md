# PM2 Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a portable PM2 ecosystem file and Ubuntu-friendly deployment documentation for running Headsup from a repo-local virtual environment.

**Architecture:** Keep PM2 configuration in a single repo-root ecosystem file that resolves relative to the checkout and launches the package entrypoint via `.venv/bin/python`. Document the server bootstrap and PM2 lifecycle in `README.md` so deployment stays path-independent and version-controlled.

**Tech Stack:** Python 3.11+, PM2, Node.js runtime for PM2 config parsing, pytest, Markdown documentation

## Global Constraints

- Add a portable `ecosystem.config.js` at the repository root.
- Update `README.md` with Ubuntu-oriented PM2 setup and lifecycle commands.
- Use `cwd: __dirname` instead of machine-specific absolute paths.
- Use `script: ".venv/bin/python"` and `args: "-m headsup"`.
- Set `interpreter: "none"` and `env.PYTHONUNBUFFERED = "1"`.
- Keep instructions repo-relative so they work regardless of server checkout path.

---

### Task 1: Add Portable PM2 Ecosystem File

**Files:**
- Create: `ecosystem.config.js`

**Interfaces:**
- Consumes: existing package entrypoint `python -m headsup`
- Produces: PM2 app definition `module.exports = { apps: [...] }`

- [ ] **Step 1: Create the PM2 ecosystem file**

```js
module.exports = {
  apps: [
    {
      name: "headsup",
      cwd: __dirname,
      script: ".venv/bin/python",
      args: "-m headsup",
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
```

- [ ] **Step 2: Run a syntax check on the ecosystem file**

Run: `node -e "const cfg = require('./ecosystem.config.js'); if (!cfg.apps?.[0]) throw new Error('missing pm2 app'); console.log(cfg.apps[0].name, cfg.apps[0].script, cfg.apps[0].cwd === process.cwd());"`
Expected: prints `headsup .venv/bin/python true`

- [ ] **Step 3: Commit the ecosystem file**

```bash
git add ecosystem.config.js
git commit -m "add pm2 ecosystem config"
```

### Task 2: Document Ubuntu PM2 Deployment

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: PM2 config file `ecosystem.config.js`, existing quick-start instructions
- Produces: README section describing Ubuntu bootstrap and PM2 lifecycle commands

- [ ] **Step 1: Update the README with PM2 deployment instructions**

```md
## PM2 (Ubuntu server)

After cloning the repo on your server:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env and set BOT_TOKEN and any other needed values

pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

Useful commands:

```bash
pm2 logs headsup
pm2 restart headsup
pm2 stop headsup
pm2 status
```
```

- [ ] **Step 2: Verify the README contains the new PM2 section**

Run: `rg -n "^## PM2 \\(Ubuntu server\\)|^pm2 start ecosystem.config.js$|^pm2 logs headsup$" README.md`
Expected: matches the new PM2 heading and commands

- [ ] **Step 3: Commit the README update**

```bash
git add README.md
git commit -m "document pm2 deployment"
```

### Task 3: Validate Repo State And Publish

**Files:**
- Modify: none
- Test: `tests/`

**Interfaces:**
- Consumes: `ecosystem.config.js`, updated `README.md`, existing pytest suite
- Produces: validated branch ready for PR and merge

- [ ] **Step 1: Run the Python test suite**

Run: `pytest`
Expected: all tests pass

- [ ] **Step 2: Inspect the final diff**

Run: `git diff -- ecosystem.config.js README.md docs/superpowers/specs/2026-06-26-pm2-deployment-design.md docs/superpowers/plans/2026-06-26-pm2-deployment.md`
Expected: only the PM2 config, README, spec, and plan changes appear

- [ ] **Step 3: Create and switch to the publish branch**

```bash
git checkout -b codex/pm2-deployment
```

- [ ] **Step 4: Stage and commit the full scoped change**

```bash
git add ecosystem.config.js README.md docs/superpowers/specs/2026-06-26-pm2-deployment-design.md docs/superpowers/plans/2026-06-26-pm2-deployment.md
git commit -m "add pm2 deployment support"
```

- [ ] **Step 5: Push and open the PR**

```bash
git push -u origin codex/pm2-deployment
gh pr create --draft --fill --head codex/pm2-deployment
```

- [ ] **Step 6: Merge the PR after validation**

```bash
gh pr merge --squash --delete-branch
```
