"""Brand constants the domain layer needs when it renders a document.

The PRIIPs KID is produced server-side as a PDF, so the few colours that
document uses have to live in the domain rather than in the web client. They
are the only presentation values the API owns: everything else a user sees is
styled by the frontend.
"""

from __future__ import annotations

# Forvis Mazars primary navy, used for KID headings and rules.
PRIMARY = "#0A2647"

# Summary Risk Indicator scale, 1 (lowest risk) to 7 (highest) — the
# green-to-red ramp prescribed by the PRIIPs RTS for the SRI band.
SRI_COLORS: dict[int, str] = {
    1: "#1A9850",
    2: "#66BD63",
    3: "#A6D96A",
    4: "#FEE08B",
    5: "#FDAE61",
    6: "#F46D43",
    7: "#D73027",
}
