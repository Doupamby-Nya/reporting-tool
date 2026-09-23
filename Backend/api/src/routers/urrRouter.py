"""Routes for U 1.1.

Monthly financial information on undertakings for collective investment (Circular CSSF 15/627).

The handlers are the ones every workbook-driven regime shares; this module
binds them to U 1.1 and gives it a router of its own.
"""

from __future__ import annotations

from routers.workbookRoutes import build_workbook_router

urrRouter = build_workbook_router("urr", "U 1.1")
