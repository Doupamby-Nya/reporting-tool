"""Routes for O 4.1.

Balance-sheet statistics under Circular IML 97/136, filed as EDIFACT.

The handlers are the ones every workbook-driven regime shares; this module
binds them to O 4.1 and gives it a router of its own.
"""

from __future__ import annotations

from routers.workbookRoutes import build_workbook_router

o41Router = build_workbook_router("o41", "O 4.1")
