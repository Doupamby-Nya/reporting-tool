import os

# Loads Backend/api/.env before the values below are read; without it
# CORS_ORIGINS has no effect and the API answers every origin.
from utils.config import load_env  # noqa: F401  (imported for its side effect)

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

CORS_ORIGINS= os.getenv("CORS_ORIGINS", "*")
# Parse origins from environment variable
if CORS_ORIGINS and CORS_ORIGINS != "*":
    origins = [origin.strip() for origin in CORS_ORIGINS.split(',')]
else:
    # Default origins for development and common production scenarios
    # When allow_credentials=True, we cannot use "*", so we need specific origins
    origins = "*"

ALLOWED_METHODS   = os.getenv('HTTP_METHODS', "*")
methods  = ALLOWED_METHODS.split(',') if ALLOWED_METHODS else ["*"]
 
originsMiddleware = [
    Middleware(
        CORSMiddleware,
        allow_origins = origins,  # Use specific origins (required when allow_credentials=True)
        allow_credentials = True,
        allow_methods = methods,
        allow_headers = ['*'],
    ) 
]