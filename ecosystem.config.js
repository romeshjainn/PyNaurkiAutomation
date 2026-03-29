module.exports = {
  apps: [
    {
      name: "debug-server",
      script: "python3",
      args: "-m http.server 9876 --directory /home/romeshjainn/PyNaurkiAutomation/debug",
      cwd: "/home/romeshjainn/PyNaurkiAutomation",
      interpreter: "none",
      autorestart: true,
      log_file: "/home/romeshjainn/PyNaurkiAutomation/logs/debug-server.log",
      out_file: "/home/romeshjainn/PyNaurkiAutomation/logs/debug-server-out.log",
      error_file: "/home/romeshjainn/PyNaurkiAutomation/logs/debug-server-err.log",
      time: true,
    },
    {
      name: "naukri-bot",
      script: "/home/romeshjainn/PyNaurkiAutomation/start_bot.sh",
      args: "",
      cwd: "/home/romeshjainn/PyNaurkiAutomation",
      interpreter: "none",
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: "10s",
      log_file: "/home/romeshjainn/PyNaurkiAutomation/logs/pm2.log",
      out_file: "/home/romeshjainn/PyNaurkiAutomation/logs/pm2-out.log",
      error_file: "/home/romeshjainn/PyNaurkiAutomation/logs/pm2-err.log",
      time: true,
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONPATH: "/home/romeshjainn/PyNaurkiAutomation",
        DISPLAY: ":99"
      }
    }
  ]
};
