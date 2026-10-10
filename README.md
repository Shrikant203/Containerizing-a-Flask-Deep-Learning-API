# Containerizing a Flask Deep Learning API

Packages a Flask-based deep-learning API (a neural-network digit classifier) into a Docker container for deployment.

## Objective

To package a Flask-based deep learning API into a Docker container for deployment.

## Approach

1. **Create a Dockerfile** - multi-stage `Dockerfile` (optimized) and `Dockerfile.baseline` (un-optimized reference)
2. **Build a Docker image** - `flask-dl-api:1.0` and `flask-dl-api:baseline`
3. **Run the container locally** - `docker run -d -p 8000:5000 flask-dl-api:1.0`
4. **Verify API functionality** - `curl` calls and the test suite `test_api.py`
5. **Optimize image size** - slim base, multi-stage build, no pip cache, no training dependencies, `.dockerignore`

## The deep-learning API

A small neural network (64 -> 64 ReLU -> 10 softmax, 4,810 parameters) trained from scratch in NumPy on the UCI handwritten-digits dataset (`train_model.py`). Test accuracy on 360 held-out images: **97.22 %**. The API needs only NumPy at inference time.

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | service description and endpoint list |
| GET | `/health` | liveness check (used by the Docker `HEALTHCHECK`) |
| GET | `/model-info` | architecture, parameters, accuracy |
| GET | `/samples` | one held-out example per digit with its true label |
| POST | `/predict` | `{"pixels": [64 numbers 0-16]}` or `{"instances": [[...], ...]}` (max 100) |

Invalid input returns a JSON error with HTTP 400 (wrong length, non-numeric, out of range, invalid JSON); unknown routes return JSON 404 and wrong methods JSON 405.

Example:

```bash
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"pixels":[0,1,11,15,16,9,0,0,0,3,16,10,10,16,1,0,0,0,2,1,14,11,0,0,0,0,0,14,16,7,0,0,0,0,0,13,16,16,5,0,0,0,0,0,2,16,8,0,0,0,6,8,13,15,5,0,0,0,15,16,12,5,0,0]}' \
  http://localhost:8000/predict
```

## Files

```
.
├── app.py                    # Flask API
├── train_model.py            # trains the model and writes model/model.npz
├── model/model.npz           # trained weights + metadata + sample images (about 25 KB)
├── requirements.txt          # pinned runtime dependencies (Flask, NumPy, gunicorn + their dependencies)
├── requirements-train.txt    # training-only dependencies (NOT installed in the image)
├── Dockerfile                # optimized multi-stage image
├── Dockerfile.baseline       # un-optimized reference image
├── .dockerignore
├── test_api.py               # black-box API tests (standard library only)
├── task10_docker.py          # runs the whole Docker workflow and logs the real output
├── local_verification.txt    # training + API test output from a local run (outside Docker)
└── README.md
```

## Optimization practices in the Dockerfile

| Practice | Why |
|----------|-----|
| `python:3.12-slim` base instead of `python:3.12` | much smaller Debian base |
| Multi-stage build | dependencies installed in a builder stage; the runtime stage contains only the installed packages, code and model |
| `pip install --no-cache-dir` | no pip cache stored in a layer |
| Pinned `requirements.txt`, copied before the code | reproducible builds and cached dependency layer |
| NumPy-only inference, scikit-learn kept out of the image | training dependencies are not needed to serve |
| `.dockerignore` | small build context; no logs, reports, screenshots or training scripts in the image |
| Non-root user (`appuser`, uid 10001) | security best practice |
| `HEALTHCHECK` on `/health` | Docker reports `healthy` / `unhealthy` |
| gunicorn instead of the Flask development server | production WSGI server |
| `PYTHONDONTWRITEBYTECODE`, `PYTHONUNBUFFERED` | no `.pyc` files, unbuffered logs |

The size benefit is measured, not assumed: `task10_docker.py` builds both images and writes `image_size_comparison.txt`.

## How to run

Requirements: Docker Desktop running (*Engine running*), Python 3, internet access (to pull the base images and Python packages), a bash-compatible terminal.

**Everything in one go (recommended, produces the logs for the report):**

```bash
python3 task10_docker.py
```

It writes `docker_command_log.txt`, `docker_results.json`, `api_test_results.json` and `image_size_comparison.txt`.

**Or manually:**

```bash
docker build -t flask-dl-api:1.0 .
docker run -d --name flask-dl-api -p 8000:5000 flask-dl-api:1.0
curl http://localhost:8000/health
python3 test_api.py --url http://localhost:8000
docker rm -f flask-dl-api
```

> The container listens on port 5000; it is published on host port **8000** because macOS uses host port 5000 for AirPlay Receiver.

**Without Docker (development):**

```bash
pip install -r requirements.txt
python train_model.py      # optional; needs requirements-train.txt, regenerates model/model.npz
gunicorn --bind 127.0.0.1:5000 app:app
```

## Local verification (outside Docker)

Before containerizing, the API was run with gunicorn from a clean virtual environment and tested with `test_api.py`: **13 of 13 checks passed** (all endpoints, 10 of 10 sample digits classified correctly, batch prediction, five kinds of invalid input, mean `/predict` latency about 0.9 ms). The full output is in `local_verification.txt`. Docker build and run results are recorded by `task10_docker.py` on the machine that runs Docker.
