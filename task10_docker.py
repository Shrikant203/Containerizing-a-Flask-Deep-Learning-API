#!/usr/bin/env python3
"""
task10_docker.py - runs the complete Docker workflow for Task 10 (Containerizing a Flask
Deep Learning API) and records the REAL output of every command.

Steps: build the baseline and the optimized image, compare sizes, run the container locally,
verify the API (curl + test_api.py), inspect the container, compare with the baseline, clean up.

Usage:
    1. Start Docker Desktop and wait for "Engine running".
    2. Run from the project folder (the one containing Dockerfile and app.py):
           python3 task10_docker.py
Outputs:
    docker_command_log.txt   plain-text log of every command, output and exit code
    docker_results.json      structured results (used to build the report)
    api_test_results.json    results of test_api.py against the running container
    image_size_comparison.txt  baseline vs optimized image size
Host ports used: 8000 (optimized container) and 8001 (baseline container); the container
itself listens on 5000. Port 5000 is avoided on the host because macOS uses it for AirPlay.
"""
import json
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

SAMPLE = '{"pixels": [0.0, 1.0, 11.0, 15.0, 16.0, 9.0, 0.0, 0.0, 0.0, 3.0, 16.0, 10.0, 10.0, 16.0, 1.0, 0.0, 0.0, 0.0, 2.0, 1.0, 14.0, 11.0, 0.0, 0.0, 0.0, 0.0, 0.0, 14.0, 16.0, 7.0, 0.0, 0.0, 0.0, 0.0, 0.0, 13.0, 16.0, 16.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 16.0, 8.0, 0.0, 0.0, 0.0, 6.0, 8.0, 13.0, 15.0, 5.0, 0.0, 0.0, 0.0, 15.0, 16.0, 12.0, 5.0, 0.0, 0.0]}'
WAIT = ("for i in $(seq 1 40); do s=$(docker inspect --format '{{.State.Health.Status}}' %s); "
        "echo \"check $i: $s\"; [ \"$s\" = healthy ] && break; sleep 2; done; [ \"$s\" = healthy ]")
F = "table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}"

A = "1. Verify Docker"
B = "2. Build the images and compare their size"
C = "3. Run the container locally"
D = "4. Verify API functionality"
E = "5. Inspect the container and check the optimizations"
G = "6. Compare with the baseline container"
H = "7. Cleanup"

STEPS = [
    (A, "Docker version", "docker --version && docker version --format 'Client: {{.Client.Version}} | Server: {{.Server.Version}}'"),
    (A, "Engine information", "docker info --format 'Containers: {{.Containers}} | Images: {{.Images}} | Storage driver: {{.Driver}} | OS: {{.OperatingSystem}}'"),
    (B, "Build the baseline image (un-optimized Dockerfile)", "docker build -f Dockerfile.baseline -t flask-dl-api:baseline ."),
    (B, "Build the optimized image (multi-stage Dockerfile)", "docker build -t flask-dl-api:1.0 ."),
    (B, "List the images", "docker images flask-dl-api --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.Size}}'"),
    (B, "Image size of the baseline in bytes", "docker image inspect flask-dl-api:baseline --format '{{.Size}}'"),
    (B, "Image size of the optimized image in bytes", "docker image inspect flask-dl-api:1.0 --format '{{.Size}}'"),
    (B, "Layer history of the optimized image", "docker history flask-dl-api:1.0"),
    (C, "Start the container (host port 8000 -> container port 5000)", "docker run -d --name flask-dl-api -p 8000:5000 flask-dl-api:1.0"),
    (C, "Wait until the HEALTHCHECK reports healthy", WAIT % "flask-dl-api"),
    (C, "List the running container", "docker ps --filter name=flask-dl-api --format '" + F + "'"),
    (D, "GET /health", "curl -s http://localhost:8000/health"),
    (D, "GET /model-info", "curl -s http://localhost:8000/model-info"),
    (D, "POST /predict with a sample image of the digit 3", "curl -s -X POST -H 'Content-Type: application/json' -d '" + SAMPLE + "' http://localhost:8000/predict"),
    (D, "POST /predict with invalid input (expect HTTP 400)", "curl -s -w '\\nHTTP status: %{http_code}\\n' -X POST -H 'Content-Type: application/json' -d '{\"pixels\":[1,2,3]}' http://localhost:8000/predict"),
    (D, "Full API test suite (test_api.py)", "python3 test_api.py --url http://localhost:8000 --out api_test_results.json"),
    (E, "User inside the container (should not be root)", "docker exec flask-dl-api id"),
    (E, "Container configuration and health", "docker inspect flask-dl-api --format 'User={{.Config.User}} | Health={{.State.Health.Status}} | Image={{.Config.Image}}'"),
    (E, "Training-only dependency is absent from the image", "docker exec flask-dl-api python -c \"import importlib.util as u; print('scikit-learn installed:', u.find_spec('sklearn') is not None); print('numpy installed:', u.find_spec('numpy') is not None)\""),
    (E, "Files inside the image", "docker exec flask-dl-api ls -la /app /app/model"),
    (E, "Container logs (gunicorn access log)", "docker logs --tail 12 flask-dl-api"),
    (E, "Resource usage", "docker stats --no-stream flask-dl-api"),
    (E, "Restart the container and check that the API recovers", "docker restart flask-dl-api && " + WAIT % "flask-dl-api" + " && curl -s http://localhost:8000/health"),
    (G, "Start the baseline container (host port 8001)", "docker run -d --name flask-dl-api-baseline -p 8001:5000 flask-dl-api:baseline && sleep 4 && docker ps --filter name=flask-dl-api-baseline --format '" + F + "'"),
    (G, "Baseline API responds", "curl -s http://localhost:8001/health"),
    (G, "User inside the baseline container", "docker exec flask-dl-api-baseline id"),
    (G, "Resource usage of both containers", "docker stats --no-stream flask-dl-api flask-dl-api-baseline"),
    (H, "Remove the containers (images are kept)", "docker rm -f flask-dl-api flask-dl-api-baseline && docker ps -a --format 'table {{.Names}}\\t{{.Status}}'"),
]


def run_cmd(cmd, timeout=1500):
    t0 = datetime.now()
    try:
        p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else "")
        rc = p.returncode
    except subprocess.TimeoutExpired:
        out, rc = "Command timed out.", 124
    return {"command": cmd, "output": out.rstrip(), "returncode": rc, "time": t0.strftime("%Y-%m-%d %H:%M:%S")}


def main():
    if run_cmd("docker info", 60)["returncode"] != 0:
        sys.exit("Docker is not running. Start Docker Desktop, wait for 'Engine running', then run again.")
    for f in ("Dockerfile", "Dockerfile.baseline", "app.py", "requirements.txt", "model/model.npz", "test_api.py"):
        if not os.path.exists(f):
            sys.exit(f"Missing file: {f}. Run this script from the project folder.")
    results = []
    for i, (section, title, cmd) in enumerate(STEPS, 1):
        r = run_cmd(cmd)
        r.update({"section": section, "title": title})
        results.append(r)
        print(f"\n### [{i}/{len(STEPS)}] {title}\n$ {cmd}\n{r['output']}\n(exit code {r['returncode']})")

    # image size comparison
    def size(title):
        r = next(x for x in results if x["title"] == title)
        digits = "".join(ch for ch in r["output"].split("\n")[0] if ch.isdigit())
        return int(digits) if digits else None
    sb, so = size("Image size of the baseline in bytes"), size("Image size of the optimized image in bytes")
    if sb and so:
        txt = (f"baseline  (python:3.12, single stage, root)      : {sb:>13,} bytes = {sb / 1e6:8.1f} MB\n"
               f"optimized (python:3.12-slim, multi-stage, user)   : {so:>13,} bytes = {so / 1e6:8.1f} MB\n"
               f"reduction                                         : {(sb - so) / sb * 100:6.1f} %  ({(sb - so) / 1e6:.1f} MB smaller)\n")
        open("image_size_comparison.txt", "w").write(txt)
        print("\n" + txt)

    json.dump(results, open("docker_results.json", "w"), indent=2)
    with open("docker_command_log.txt", "w") as f:
        f.write(f"Task 10 Docker command log - generated {datetime.now():%Y-%m-%d %H:%M:%S}\n" + "=" * 78 + "\n")
        for i, r in enumerate(results, 1):
            f.write(f"\n[{i}] {r['section']} - {r['title']}  ({r['time']})\n$ {r['command']}\n{r['output']}\n"
                    f"(exit code {r['returncode']})\n" + "-" * 78 + "\n")
    ok = sum(1 for r in results if r["returncode"] == 0)
    print(f"\nDone: {ok}/{len(results)} commands succeeded. Log: docker_command_log.txt, results: docker_results.json")


if __name__ == "__main__":
    main()
