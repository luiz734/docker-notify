"""`setup` subcommand: asks for settings and generates everything under system/.
Nothing outside the repo is touched; install.sh copies the result into place."""
import getpass
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from string import Template

from . import check, mail

NAME = "docker-notify"
REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "system"

SERVICE = Template("""\
[Unit]
Description=Docker update report
StartLimitIntervalSec=30min
StartLimitBurst=3

[Service]
Type=oneshot
WorkingDirectory=$repo
EnvironmentFile=%E/$name/env
ExecStart=$python -m docker_notify mail
Restart=on-failure
RestartSec=2min
""")

TIMER = Template("""\
[Unit]
Description=Docker update report schedule

[Timer]
OnCalendar=$schedule
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
""")


def works(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def confirm(question, default=False):
    if not sys.stdin.isatty():
        return default
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not answer else answer.startswith("y")


def ask(var, prompt, default="", secret=False):
    """Use $var if it is set (e.g. loaded by direnv), otherwise prompt."""
    if os.environ.get(var):
        print(f"{prompt}: using ${var} from environment")
        return os.environ[var]
    if not sys.stdin.isatty():
        if default:
            return default
        sys.exit(f"${var} is not set and there is no terminal to ask")
    text = f"{prompt} [{default}]: " if default else f"{prompt}: "
    while True:
        value = (getpass.getpass(text) if secret else input(text)).strip() or default
        if value:
            return value


def check_requirements():
    needed = {
        "docker compose plugin": ("docker", "compose", "version"),
        "docker buildx plugin": ("docker", "buildx", "version"),
        "docker access (is your user in the docker group?)": ("docker", "info"),
        "systemd-analyze": ("systemd-analyze", "--version"),
    }
    missing = [name for name, cmd in needed.items() if not works(*cmd)]
    if missing:
        sys.exit("missing requirements:\n  " + "\n  ".join(missing))
    for p in (REPO, Path(sys.executable)):
        if re.search(r"[\s%$]", str(p)):
            sys.exit(f"unsupported character in path: {p}")


def collect():
    guess = Path.home() / "docker"
    root = Path(ask("DOCKER_ROOT", "Directory containing your compose folders",
                    str(guess) if guess.is_dir() else "")).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"{root} is not a directory")
    found = sum(any((d / n).is_file() for n in check.COMPOSE_NAMES)
                for d in root.iterdir() if d.is_dir())
    print(f"  found {found} compose project(s)")
    if not found and not confirm("No compose projects found there. Continue anyway?"):
        sys.exit("aborted")

    host = ask("SMTP_HOST", "SMTP host", "smtp.gmail.com")
    port = ask("SMTP_PORT", "SMTP port (587 = STARTTLS, 465 = SSL)", "587")
    user = ask("SMTP_USER", "SMTP username (full email address)")
    password = ask("SMTP_PASS", "SMTP password / app password", secret=True)
    if host == "smtp.gmail.com":
        password = password.replace(" ", "")  # Google shows app passwords in groups of four
    sender = ask("SMTP_FROM", "Send from", user)
    return {
        "DOCKER_ROOT": str(root),
        "SMTP_HOST": host,
        "SMTP_PORT": port,
        "SMTP_USER": user,
        "SMTP_PASS": password,
        "SMTP_FROM": sender,
        "SMTP_TO": ask("SMTP_TO", "Send report to", sender),
    }


def ask_schedule():
    while True:
        schedule = ask("NOTIFY_SCHEDULE", "When to run (systemd OnCalendar)", "Mon *-*-* 08:00:00")
        if works("systemd-analyze", "calendar", schedule):
            return schedule
        print(f"  '{schedule}' is not a valid OnCalendar expression")
        os.environ.pop("NOTIFY_SCHEDULE", None)


def test_mail(cfg):
    os.environ.update(cfg)
    try:
        mail.send(f"docker-notify test - {socket.gethostname()}",
                  "Setup test. If you can read this, mail works.")
        print("  sent, check your inbox")
    except Exception as e:
        print(f"  failed: {e}")
        if not confirm("Continue anyway?"):
            sys.exit(1)


def env_line(key, value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"\n'


def generate(cfg, schedule):
    OUT.mkdir(mode=0o700, exist_ok=True)
    OUT.chmod(0o700)
    env = OUT / "env"
    env.write_text("".join(env_line(k, v) for k, v in cfg.items()))
    env.chmod(0o600)
    (OUT / f"{NAME}.service").write_text(
        SERVICE.substitute(repo=REPO, python=sys.executable, name=NAME))
    (OUT / f"{NAME}.timer").write_text(TIMER.substitute(schedule=schedule))


def run():
    check_requirements()
    cfg = collect()
    schedule = ask_schedule()
    if confirm("Send a test email now?", default=True):
        test_mail(cfg)
    generate(cfg, schedule)
    print(f"\nGenerated files in {OUT}\nNext: ./install.sh")