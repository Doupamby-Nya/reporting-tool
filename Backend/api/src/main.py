from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from database.db import init_db

from middlewares.originsMiddleware import originsMiddleware
from routers.activityRouter import activityRouter
from routers.adminRouter import adminRouter
from routers.aifmdRouter import aifmdRouter
from routers.authRouter import authRouter
from routers.bclRouter import bclRouter
from routers.fatcaRouter import fatcaRouter
from routers.esefRouter import esefRouter
from routers.fundsRouter import fundsRouter
from routers.o41Router import o41Router
from routers.priipsRouter import priipsRouter
from routers.saqRouter import saqRouter
from routers.urrRouter import urrRouter
from routers.referenceRouter import referenceRouter
from routers.dependencies import require_module
from routers.workflowRouter import workflowRouter
from services import activityService
from utils.paths import ensure_runtime_dirs

app = FastAPI(
    title="Forvis Mazars Regulatory Reporting Platform — API",
    description=(
        "Regulatory reporting for third-party management companies. One endpoint family per regime — "
        "PRIIPs KID, FATCA/CRS, U 1.1, O 4.1, ESEF, AIFMD Annex IV, SAQ and the BCL statistical reports — "
        "each validating a filing against the regulator's own rules and schemas before returning it."
    ),
    version="1.0.0",
    middleware=originsMiddleware)



@app.exception_handler(RequestValidationError)
def request_validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """A body that does not match its model is refused with 422, in the same
    envelope as every other refusal, so the client shows the reason rather
    than "Request failed with status code 422"."""
    problems = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'][1:]) or 'body'}: {error['msg']}"
        for error in exc.errors())
    return JSONResponse(status_code=422, content={"success": False, "message": f"Invalid request — {problems}"})


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """401 and 403 from the access checks, in the same envelope as the rest."""
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={"success": False, "message": str(exc.detail)})


@app.middleware("http")
async def record_activity(request: Request, call_next):
    """Every successful request a signed-in user makes is offered to the
    activity record, which keeps the ones that stand for work. The user is
    the one the access check resolved (request.state.user); a route may name
    what it acted on in request.state.activity_subject."""
    response = await call_next(request)
    user = getattr(request.state, "user", None)
    if user is not None and response.status_code < 400:
        await run_in_threadpool(
            activityService.capture, user, request.method, request.url.path,
            dict(request.query_params), response.status_code,
            getattr(request.state, "activity_subject", None))
    return response


# The writable root and the account database, created once at import so the
# first request never has to.
ensure_runtime_dirs()
init_db()

# Create a parent API router with the global prefix
# All routes will be under /api/v1
api_router = APIRouter(prefix="/api/v1", tags=["Regulatory Reporting"])

def module(key: str) -> list:
    """A module's routes answer only users who can use that module."""
    return [Depends(require_module(key))]


# Include logic routers
  # signing in, and the platform administration
api_router.include_router(authRouter)
api_router.include_router(adminRouter)
  # usage dashboards: a user's own activity, an organisation's for its administrators
api_router.include_router(activityRouter)
  # shared reference data: modules, regulatory library, clients
api_router.include_router(referenceRouter)
  # document lifecycle, audit trail and saved drafts
api_router.include_router(workflowRouter)
  # BCL statistical reports
api_router.include_router(bclRouter, dependencies=module("bcl"))
  # AIFMD Annex IV reporting
api_router.include_router(aifmdRouter, dependencies=module("aifmd"))
  # FATCA and CRS reporting
api_router.include_router(fatcaRouter, dependencies=module("fatca"))
  # one router per regime, each under its own prefix
api_router.include_router(urrRouter, prefix="/urr", dependencies=module("urr"))
api_router.include_router(o41Router, prefix="/o41", dependencies=module("o41"))
api_router.include_router(esefRouter, prefix="/esef", dependencies=module("esef"))
api_router.include_router(saqRouter, prefix="/saq", dependencies=module("saq"))
  # PRIIPs KID: its own calculation chain, document and configuration
api_router.include_router(priipsRouter, prefix="/priips", dependencies=module("priips"))
  # the registry of funds and share classes under mandate
api_router.include_router(fundsRouter)

# Include the parent router in the app
app.include_router(api_router, responses={404: {"description": "Not found"}})


# Healthcheck & Liveness check, to check the health of the app
@app.get("/healthcheck", tags=["Health Check"])
@app.get("/liveness", tags=["Liveness"])
def health_check():
    """
    Health check endpoint to verify if the API is running.
    """
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
