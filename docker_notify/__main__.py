import argparse
import socket
from datetime import datetime
from . import check, configure, mail


def main():
    p = argparse.ArgumentParser(prog="docker_notify")
    p.add_argument("command", nargs="?", default="check",
                   choices=["check", "mail", "setup"])
    cmd = p.parse_args().command

    if cmd == "setup":
        configure.run()
        return
    report = check.build_report()
    if cmd == "check":
        print(report)
    else:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        mail.send(f"[Docker update report][{socket.gethostname()}][{stamp}]", report)



if __name__ == "__main__":
    main()