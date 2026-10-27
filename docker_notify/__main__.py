import argparse
import socket

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
        mail.send(f"Docker update report - {socket.gethostname()}", report)


if __name__ == "__main__":
    main()