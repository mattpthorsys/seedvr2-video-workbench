# SeedVR2 Video Workbench

Free, local, Dockerised video restoration and upscaling workbench for Windows 11, WSL2, Docker Desktop, and NVIDIA GPU passthrough.

The app is structured as:

- Angular + TypeScript frontend
- Python FastAPI backend API
- Python worker process
- SQLite database under `/data/app.db`
- FFmpeg/FFprobe command boundaries
- SeedVR2 adapter boundary with a mock runner for the MVP
- Docker Compose with `backend`, `frontend`, and GPU-capable `worker`

## Current Status

This first pass is a working MVP scaffold. The GUI, API, job database, job state machine, progress/log views, ETA estimates, performance history tables, GPU stats probe, tests, Docker files, and SeedVR2 adapter are present.

What is real:

- REST API endpoints under `/api`
- SQLite schema and auto-init
- input file listing from `/data/input`
- browser file picker uploads into `/data/input`
- FFprobe metadata parsing when FFprobe can read the source
- job creation, cancellation flags, progress, logs, stages, ETA history
- historical performance profiles after completed mock jobs
- NVIDIA stats collection when `nvidia-smi` is available
- GPU-first defaults with NVIDIA NVENC selected automatically when visible
- SeedVR2 model inventory and smoke-test endpoints
- SeedVR2 model download status and background downloads from official ByteDance Hugging Face repositories
- FFmpeg preprocessing and encode command builders
- SeedVR2 real-runner branch for FFmpeg preprocess, SeedVR2 upscale, and audio-preserving encode/mux when `MOCK_PIPELINE=false`

What is mocked:

- The worker currently simulates pipeline stages by default with `MOCK_PIPELINE=true`.
- Real SeedVR2 inference still needs the actual ByteDance SeedVR repository mounted and the worker image/environment to include SeedVR dependencies such as PyTorch, torchrun, flash-attn, and apex.
- The model smoke test can run real inference only after SeedVR2 entrypoints and model files are present.
- VapourSynth/QTGMC is documented as optional and detected, but not fully wired into the v1 runner.

## Requirements

- Windows 11
- WSL2 enabled
- Docker Desktop with WSL2 integration
- NVIDIA GPU driver with container support
- NVIDIA Container Toolkit support in Docker
- An NVIDIA GPU with enough VRAM for the selected SeedVR2 model and options

Target hardware for the initial defaults: NVIDIA RTX 5060 Ti 16 GB.

## Start With Docker

From this folder:

```powershell
copy .env.example .env
docker compose build
docker compose up
```

This is not hosted anywhere by default. It runs locally on your machine through Docker.

Open the GUI:

```text
http://localhost:4200
```

Backend API health:

```text
http://localhost:8000/api/health
```

If Docker Desktop or GPU passthrough is still installing, wait for Docker to finish starting and rerun the same commands.

## Input And Output Folders

Put source videos here:

```text
./data/input
```

Outputs are written here:

```text
./data/output
```

Work files, logs, and the SQLite database live under:

```text
./data/work
./data/logs
./data/app.db
```

Models should be mounted or copied under:

```text
./models
```

The SeedVR repository should be mounted or cloned under:

```text
./seedvr
```

The GUI New Job page also has a file picker. Picked files are copied into `./data/input` before probing and queueing.

The New Job file dialog can browse configured roots. Docker defaults are:

```text
/data
/models
/external
```

The `./external` folder is mounted into both the backend and worker containers. To browse another host folder, add a bind mount in `docker-compose.yml` and include the container path in `BROWSE_ROOTS`. For Docker, keep the root list colon-separated inside the container, for example:

```env
BROWSE_ROOTS=/data:/models:/external:/media/archive
```

For local Windows backend development without Docker, use Windows paths and a semicolon-separated list, for example:

```powershell
$env:BROWSE_ROOTS="C:\Users\mpalm\Videos;D:\Archive"
```

## SeedVR2 Configuration

The default `.env.example` values are:

```env
SEEDVR2_CLI_PATH=/opt/seedvr2/inference_cli.py
SEEDVR2_REPO_DIR=/opt/seedvr
SEEDVR2_MODEL_DIR=/models/seedvr2
MOCK_PIPELINE=true
```

The app can download official ByteDance model snapshots into `./models/seedvr2/3B` and `./models/seedvr2/7B` from:

```text
ByteDance-Seed/SeedVR2-3B
ByteDance-Seed/SeedVR2-7B
```

The download controls are on the New Job page. The backend reports status at `GET /api/models/downloads` and starts a download with `POST /api/models/downloads`.

To connect the real SeedVR2 runner:

1. Clone or mount `https://github.com/ByteDance-Seed/SeedVR` into `./seedvr`.
2. Use the New Job page to download models, or manually place model files under `./models/seedvr2`.
3. Build a worker image/environment with the SeedVR Python dependencies.
4. Set `MOCK_PIPELINE=false` once `torchrun`, SeedVR entrypoints, GPU access, and models are ready.

The adapter is in `backend/app/pipeline/seedvr2.py`.

## Model And GPU Tests

The New Job page can inspect the GPU, configured SeedVR2 CLI path, and model folders. It can also run a small model check:

- Dry Run Command creates a tiny test clip and verifies that a SeedVR2 command can be built.
- Run Live Smoke Test runs the configured SeedVR2 CLI against that clip and checks that output is produced.

The same readiness data is available at:

```text
GET http://localhost:8000/api/models
POST http://localhost:8000/api/models/test
```

The backend and worker both request GPU access in Docker Compose. With the RTX 5060 Ti visible to Docker, the app defaults to NVIDIA/NVENC paths when `PREFER_GPU=true`.

## Windows 11, WSL2, Docker, NVIDIA Notes

Docker Desktop must be using the WSL2 backend. After installing or updating Docker/NVIDIA drivers, restart Docker Desktop before testing GPU passthrough.

A quick GPU container test is included:

```powershell
.\scripts\check-docker-gpu.ps1
```

That command downloads an NVIDIA CUDA base image if it is not already present.

## API Endpoints

Implemented endpoints:

```text
GET    /api/health
GET    /api/settings
POST   /api/probe
GET    /api/files/input
POST   /api/files/input/upload
GET    /api/files/roots
GET    /api/files/browse
GET    /api/models
GET    /api/models/downloads
POST   /api/models/downloads
POST   /api/models/test
GET    /api/jobs
POST   /api/jobs
GET    /api/jobs/{id}
POST   /api/jobs/{id}/cancel
GET    /api/jobs/{id}/logs
GET    /api/jobs/{id}/eta
GET    /api/stats
GET    /api/stats/performance-profiles
```

## ETA System

The ETA module estimates each stage independently. Before enough local history exists, it uses conservative built-in throughput defaults and labels confidence as low.

After jobs complete, stage throughput is persisted in `job_stage_stats` and aggregated into `performance_profiles`. Future estimates search historical profiles by stage, source/target dimensions, preset, model, precision, batch size, temporal overlap, encoder, and GPU name. During running jobs, the worker smooths live ETA updates with an exponential moving average.

## Local Backend Development

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATA_DIR="..\data"
$env:DATABASE_URL="sqlite:///..\data\app.db"
$env:RUN_IN_PROCESS_WORKER="true"
uvicorn app.main:app --reload --port 8000
```

## Local Frontend Development

```powershell
cd frontend
npm install
npm start
```

Open:

```text
http://localhost:4200
```

## Tests

Focused local check from the project root:

```powershell
.\scripts\quick-check.ps1
```

If local script execution is blocked by Windows policy, run the same check with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\quick-check.ps1
```

That compiles backend/worker Python and only runs mapped backend tests for files changed since `HEAD`. Use the fuller local path when you want broader coverage:

```powershell
.\scripts\quick-check.ps1 -Full -Frontend
```

Backend tests only:

```powershell
cd backend
pytest
```

Full Docker-based test run from the project root:

```powershell
.\scripts\run-tests.ps1
```

To only validate the Docker Compose test profile without building images:

```powershell
.\scripts\quick-check.ps1 -Docker
```

Or run the same checks manually:

```powershell
docker compose --profile test build backend-tests frontend-tests
docker compose --profile test run --rm backend-tests
docker compose --profile test run --rm frontend-tests
```

Covered areas:

- ETA with no history
- ETA with matching historical profile
- live ETA smoothing
- FFprobe JSON parsing
- job state transitions
- performance stats aggregation
- audio/output container command construction
- model readiness reporting
- model download status
- real-pipeline branch orchestration

## Troubleshooting

- Docker command is not found: finish installing Docker Desktop and restart the terminal.
- GPU is unavailable in the app: confirm `nvidia-smi` works on Windows and in a Docker CUDA container.
- `/api/models/downloads` returns 404: rebuild and restart the backend container with `docker compose build backend && docker compose up`; the frontend button exists but the older backend image does not have the download endpoint.
- `/api/probe` fails: confirm the file is inside `./data/input` and FFprobe supports the format.
- Jobs remain queued: confirm the `worker` service is running, or set `RUN_IN_PROCESS_WORKER=true` for local backend-only development.
- SeedVR2 setup error: keep `MOCK_PIPELINE=true` until the real SeedVR repo is mounted, dependencies are installed, `torchrun` is available, and model files are present.

## Known Limitations

- The default runner simulates processing stages.
- Real SeedVR2 command execution depends on a SeedVR-capable worker image; the base worker image does not install PyTorch/flash-attn/apex.
- QTGMC/VapourSynth support is a planned advanced path.
- Uploads are intentionally not stored in the database; the app works from mounted folders.

## Next Recommended Steps

1. Build a CUDA/PyTorch worker image that satisfies ByteDance SeedVR dependencies.
2. Validate real SeedVR2 command execution on a short clip.
3. Add SeedVR2 progress parser support for live upscale stage progress.
4. Add frontend affordances for opening output paths on Windows/WSL.
