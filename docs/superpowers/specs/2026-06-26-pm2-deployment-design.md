# PM2 Deployment Design

## Goal

Add repo-managed PM2 support for running the Headsup bot on a separate Ubuntu
server without hardcoded machine-specific paths.

## Scope

- Add a portable `ecosystem.config.js` at the repository root.
- Update `README.md` with Ubuntu-oriented PM2 setup and lifecycle commands.

## Approach Options

### Recommended

Commit a PM2 ecosystem file that runs the project-local Python interpreter from
`.venv` and resolves paths relative to the repository checkout.

Trade-offs:

- Portable across servers and checkout locations.
- Keeps runtime configuration in version control.
- Requires the deployment process to create `.venv` in the repo.

### Alternative 1

Run `python3 -m headsup` from PM2 and rely on a system interpreter.

Trade-offs:

- Slightly simpler PM2 config.
- More fragile because dependency resolution depends on host setup.

### Alternative 2

Add a shell wrapper script that activates the virtual environment before
launching the bot.

Trade-offs:

- Explicit startup flow.
- Adds indirection without solving a real problem for this repo.

## Chosen Design

### PM2 Configuration

Add `ecosystem.config.js` with:

- `cwd: __dirname`
- `script: ".venv/bin/python"`
- `args: "-m headsup"`
- `interpreter: "none"`
- `env.PYTHONUNBUFFERED = "1"`

This keeps the config compatible with Ubuntu and any other environment where
the repository is checked out and bootstrapped locally.

### Documentation

Add a `PM2` section to `README.md` covering:

- creating the virtual environment
- installing dependencies
- configuring `.env`
- starting with `pm2 start ecosystem.config.js`
- persisting with `pm2 save`
- enabling startup with `pm2 startup`

The instructions stay repo-relative so they do not assume a fixed server path.

## Error Handling

- If `.venv/bin/python` does not exist, PM2 startup will fail immediately,
  which is acceptable because the README documents the bootstrap step.
- `PYTHONUNBUFFERED=1` ensures PM2 log streaming remains readable.

## Testing

- Add a documentation-level check by validating the config file syntax with
  Node.js.
- Re-run the existing Python test suite to catch unrelated regressions.
