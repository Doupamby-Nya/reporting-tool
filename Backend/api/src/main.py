from fastapi import APIRouter, FastAPI

from middlewares.originsMiddleware import originsMiddleware
from routers.aifmdRouter import aifmdRouter
from routers.bclRouter import bclRouter
from routers.fatcaRouter import fatcaRouter
from routers.esefRouter import esefRouter
from routers.fundsRouter import fundsRouter
from routers.o41Router import o41Router
from routers.priipsRouter import priipsRouter
from routers.saqRouter import saqRouter
from routers.urrRouter import urrRouter
from routers.referenceRouter import referenceRouter
from routers.workflowRouter import workflowRouter
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

# The writable directories the API needs for drafts, documents and the audit
# trail, created once at import so the first request never has to.
ensure_runtime_dirs()

# Create a parent API router with the global prefix
# All routes will be under /api/v1
api_router = APIRouter(prefix="/api/v1", tags=["Regulatory Reporting"])

# Include logic routers
  # shared reference data: modules, regulatory library, clients
api_router.include_router(referenceRouter)
  # document lifecycle, audit trail and saved drafts
api_router.include_router(workflowRouter)
  # BCL statistical reports
api_router.include_router(bclRouter)
  # AIFMD Annex IV reporting
api_router.include_router(aifmdRouter)
  # FATCA and CRS reporting
api_router.include_router(fatcaRouter)
  # one router per regime, each under its own prefix
api_router.include_router(urrRouter, prefix="/urr")
api_router.include_router(o41Router, prefix="/o41")
api_router.include_router(esefRouter, prefix="/esef")
api_router.include_router(saqRouter, prefix="/saq")
  # PRIIPs KID: its own calculation chain, document and configuration
api_router.include_router(priipsRouter, prefix="/priips")
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
