"""
FastAPI entry point.

Run locally with:
    uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.routes import account, admin, assistant, auth, explorer, health, simulation, workflow as workflow_routes, workspace, research, workflows as workflow_journeys
from app.routes.errors import register_error_handlers
from app.middleware import RequestGuard

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm the configuration path before the first client asks for it.

    The dashboard's first request is `GET /api/config`, and on a hosted free instance it lands
    during cold start. Everything that endpoint touches - the crop table, the assumption
    description (which recomputes the FAO-56 worked examples), simulation constants and the
    scenario-history settings - used to be built lazily on that first request, so the one request
    that decides whether the UI shows live control ranges was also the slowest one in the process.
    Building it here moves that cost into startup, where Render's health check already waits for it,
    and leaves the endpoint with a dictionary to serialise.

    Deliberately best-effort: a warm-up failure must not stop the app from starting, because the
    endpoint itself still works on demand and /api/ready reports the real state.
    """
    import logging

    try:
        from app.routes.simulation import simulation_config

        simulation_config()
        app.state.config_warmed = True
    except Exception as error:  # noqa: BLE001 - startup must survive a warm-up failure
        logging.getLogger(__name__).warning("config warm-up failed: %s", error)
        app.state.config_warmed = False
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend for the Space Agriculture & Life Support Simulator. "
        "Transparent mathematical habitat scenarios and separate artifact-backed "
        "NASA and external-data learning experiments. Not validated for spacecraft operations."
    ),
    # Docs live under the API prefix so they stay reachable when only /api/*
    # is routed to this app (e.g. behind the Vercel rewrite in vercel.json).
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

app.add_middleware(RequestGuard)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(account.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(simulation.router, prefix=settings.api_prefix)
app.include_router(workspace.router, prefix=settings.api_prefix)
app.include_router(research.router, prefix=settings.api_prefix)
app.include_router(assistant.router, prefix=settings.api_prefix)
app.include_router(workflow_routes.router, prefix=settings.api_prefix)
app.include_router(workflow_journeys.router, prefix=settings.api_prefix)
app.include_router(explorer.router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"message": f"{settings.app_name} is running", "docs": f"{settings.api_prefix}/docs"}
