module.exports = {
  apps: [
    {
      name: "blue-heron-book",
      cwd: __dirname,
      script: "runner.py",
      interpreter: "python",
      autorestart: true,
      max_restarts: 1000,
      min_uptime: "10s",
      restart_delay: 5000,
      watch: false,
      kill_timeout: 30000,
      out_file: "logs/pm2-out.log",
      error_file: "logs/pm2-error.log",
      merge_logs: true,
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
      },
    },
  ],
};
