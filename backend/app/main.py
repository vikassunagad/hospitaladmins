"""Hospital Module - FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import DomainError
from app.routers import alerts, ambulances, auth, capacity, dashboard, emergencies, integration, patients

APP_DIR = Path(__file__).resolve().parent
log = logging.getLogger("hospital")


@asynccontextmanager
async def lifespan(_app):
    from app import models  # noqa: F401  (registers the tables)
    from app.seed_data import seed_all
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_all(db)  # safe to run on every start: it never creates duplicates
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan,
              description="Hospital-side module of the Central Emergency Control Room (college prototype, DEMO DATA).")


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError):
    parts = []
    for err in exc.errors():
        field = ".".join(str(x) for x in err["loc"] if x != "body")
        parts.append("%s: %s" % (field, err["msg"]) if field else err["msg"])
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts) or "Invalid input.",
                                                  "code": "INVALID_INPUT"})


@app.exception_handler(Exception)
async def unexpected_handler(_request: Request, exc: Exception):
    log.exception("Unexpected error", exc_info=exc)  # full details only in the server console
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again.",
                                                  "code": "SERVER_ERROR"})


@app.get("/api/health", tags=["System"])
def health():
    return {"status": "ok", "app": settings.APP_NAME, "mock_control_room": settings.MOCK_CONTROL_ROOM}


for module in (auth, dashboard, capacity, emergencies, patients, alerts, ambulances, integration):
    app.include_router(module.router)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

PAGES = {"login": "login.html", "dashboard": "dashboard.html", "capacity": "capacity.html",
         "emergencies": "emergencies.html", "emergency-details": "emergency-details.html",
         "patients": "patients.html", "alerts": "alerts.html", "ambulance": "ambulance-tracking.html",
         "profile": "profile.html", "integration-log": "integration-log.html"}


def _page(filename):
    def handler():
        return FileResponse(str(APP_DIR / "templates" / filename), headers={"Cache-Control": "no-cache"})
    return handler


for route, filename in PAGES.items():
    app.add_api_route("/" + route, _page(filename), methods=["GET"], include_in_schema=False)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/login")
