#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
ENV_FILE="$PROJECT_ROOT/.env"
INFERENCE_HEALTH="http://localhost:8001/health"
FRONTEND_URL="http://localhost:8081"
INFERENCE_LOG="/tmp/manga-inference.log"

info() { echo "• $*"; }
ok() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
fail() { echo "✗ $*"; exit 1; }

info "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || fail "Docker is required: https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 || fail "Docker Compose is required. Install Docker Desktop or Docker Engine with Compose."
command -v curl >/dev/null 2>&1 || fail "curl is required."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is required for host ML inference."
ok "Prerequisites found"

info "Checking Docker daemon..."
if ! docker info >/dev/null 2>&1; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    warn "Docker is installed but not running. Opening Docker Desktop..."
    open -a Docker || true
    for _ in {1..60}; do
      if docker info >/dev/null 2>&1; then
        ok "Docker daemon is ready"
        break
      fi
      sleep 2
    done
  fi
fi
docker info >/dev/null 2>&1 || fail "Docker daemon is not running. Start Docker and run this script again."
ok "Docker daemon is ready"

info "Preparing .env..."
if [[ ! -f "$ENV_FILE" ]]; then
  [[ -f "$PROJECT_ROOT/.env.example" ]] || fail ".env.example is missing"
  cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
  DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
  POSTGRES_USER=$(grep "^POSTGRES_USER=" "$ENV_FILE" | head -n1 | cut -d= -f2- || true)
  POSTGRES_DB=$(grep "^POSTGRES_DB=" "$ENV_FILE" | head -n1 | cut -d= -f2- || true)
  POSTGRES_USER=${POSTGRES_USER:-manga}
  POSTGRES_DB=${POSTGRES_DB:-manga_db}

  if grep -q "^POSTGRES_PASSWORD=" "$ENV_FILE"; then
    sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
  else
    echo "POSTGRES_PASSWORD=${DB_PASSWORD}" >> "$ENV_FILE"
  fi

  if ! grep -q "^DATABASE_URL=" "$ENV_FILE"; then
    {
      echo ""
      echo "# Auto-generated database URL"
      echo "DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${DB_PASSWORD}@db:5432/${POSTGRES_DB}"
    } >> "$ENV_FILE"
  fi

  chmod 600 "$ENV_FILE"
  ok "Created .env with a secure database password"
else
  ok ".env already exists"
fi

info "Downloading/checking model files..."
if bash "$SCRIPT_DIR/download-models.sh"; then
  ok "Model files ready"
else
  fail "Model download failed. Run bash scripts/download-models.sh and check the output."
fi

info "Starting host ML inference service..."
if curl -sf "$INFERENCE_HEALTH" >/dev/null 2>&1; then
  ok "Inference already healthy at $INFERENCE_HEALTH"
else
  if lsof -nP -iTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
    warn "Port 8001 is occupied, but the inference health check failed."
    echo "Stop the process using port 8001, then rerun this script:"
    echo "  lsof -nP -iTCP:8001 -sTCP:LISTEN"
    echo "  kill <PID>"
    exit 1
  fi

  : > "$INFERENCE_LOG"
  nohup bash "$SCRIPT_DIR/start-inference.sh" > "$INFERENCE_LOG" 2>&1 &

  READY=0
  for _ in {1..45}; do
    if curl -sf "$INFERENCE_HEALTH" >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 2
  done

  if [[ "$READY" -ne 1 ]]; then
    warn "Inference service did not become healthy. Recent log output:"
    tail -80 "$INFERENCE_LOG" || true
    exit 1
  fi
  ok "Inference healthy at $INFERENCE_HEALTH"
fi

info "Building Docker services..."
cd "$PROJECT_ROOT"
docker compose build --parallel
ok "Docker images built"

info "Starting Docker services..."
docker compose up -d
ok "Docker stack started"

info "Waiting for Docker services to become healthy..."
HEALTHY=0
for _ in {1..45}; do
  STATUS=$(docker compose ps --format json 2>/dev/null || true)
  DB_OK=$(echo "$STATUS" | python3 -c 'import sys,json; rows=[json.loads(l) for l in sys.stdin if l.strip()]; print(any(r.get("Service")=="db" and r.get("Health")=="healthy" for r in rows))' 2>/dev/null || echo "False")
  BACKEND_OK=$(echo "$STATUS" | python3 -c 'import sys,json; rows=[json.loads(l) for l in sys.stdin if l.strip()]; print(any(r.get("Service")=="backend" and r.get("Health")=="healthy" for r in rows))' 2>/dev/null || echo "False")
  if [[ "$DB_OK" == "True" && "$BACKEND_OK" == "True" ]]; then
    HEALTHY=1
    break
  fi
  sleep 2
done

if [[ "$HEALTHY" -eq 1 ]]; then
  ok "Docker services healthy"
else
  warn "Docker services are still starting or unhealthy. Check: docker compose ps"
fi

info "Checking frontend..."
for _ in {1..30}; do
  if curl -sf "$FRONTEND_URL" >/dev/null 2>&1; then
    ok "Frontend reachable"
    break
  fi
  sleep 2
done

if ! curl -sf "$FRONTEND_URL" >/dev/null 2>&1; then
  warn "Frontend did not respond yet. Check: docker compose logs -f frontend"
fi

echo ""
echo "Ready."
echo "App running: $FRONTEND_URL"
echo "Inference:   $INFERENCE_HEALTH"
echo "Logs:        docker compose logs -f"
echo "Inference log: $INFERENCE_LOG"

if [[ "$(uname -s)" == "Darwin" ]]; then
  open "$FRONTEND_URL" || true
fi
