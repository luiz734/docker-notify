#!/usr/bin/env python3
import json
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

COMPOSE_NAMES = ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml")

def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def local_digests(image):
    rc, out = run(["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"])
    if rc != 0:
        return None  # image not present locally
    return {d.split("@")[1] for d in (json.loads(out) or [])}


def remote_digest(image):
    rc, out = run(["docker", "buildx", "imagetools", "inspect", image,
                   "--format", "{{.Manifest.Digest}}"])
    return out if rc == 0 and out.startswith("sha256:") else None


def update_status(images):
    states = set()
    for img in images:
        if "@sha256:" in img:
            continue  # pinned by digest, nothing to compare
        local = local_digests(img)
        remote = remote_digest(img)
        if remote is None:
            states.add("?")
        elif local is None:
            states.add("not pulled")
        elif remote not in local:
            states.add("yes")
    for s in ("yes", "not pulled", "?"):
        if s in states:
            return s
    return "no"


def running_status(d, total):
    rc, out = run(["docker", "compose", "ps", "-q", "--status", "running"], cwd=d)
    n = len(out.splitlines()) if rc == 0 and out else 0
    if total == 0 or n == 0:
        return "no"
    return "yes" if n >= total else f"partial ({n}/{total})"


def check(d):
    rc, out = run(["docker", "compose", "config", "--format", "json"], cwd=d)
    if rc != 0:
        return d.name, "error", "error"
    services = json.loads(out).get("services", {})
    images = {s["image"] for s in services.values() if "image" in s}
    return d.name, update_status(images), running_status(d, len(services))


def build_report():
    root = Path(os.environ["DOCKER_ROOT"])
    dirs = sorted(d for d in root.iterdir()
                  if d.is_dir() and any((d / n).is_file() for n in COMPOSE_NAMES))
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(check, dirs))

    w = max([len(r[0]) for r in rows] + [len("service")])
    lines = [f"{'service':<{w}}  {'update':<10}  running",
             f"{'-' * w}  {'-' * 10}  {'-' * 12}"]
    lines += [f"{n:<{w}}  {u:<10}  {r}" for n, u, r in rows]
    return "\n".join(lines)