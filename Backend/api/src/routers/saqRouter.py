"""Routes for SAQ.

The self-assessment questionnaire of Circular CSSF 21/790.

The handlers are the ones every workbook-driven regime shares; this module
binds them to SAQ and gives it a router of its own.
"""

from __future__ import annotations

from routers.workbookRoutes import build_workbook_router

saqRouter = build_workbook_router("saq", "SAQ")
