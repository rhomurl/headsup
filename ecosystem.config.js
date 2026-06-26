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
