"""Routes for ESEF.

The annual financial report in Inline XBRL (Delegated Regulation (EU) 2019/815).

The handlers are the ones every workbook-driven regime shares; this module
binds them to ESEF and gives it a router of its own.
"""

from __future__ import annotations

from routers.workbookRoutes import build_workbook_router

esefRouter = build_workbook_router("esef", "ESEF")
