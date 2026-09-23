"""Assemblage du document PRIIPs KID a partir du template configure, des
donnees du fonds et des resultats du moteur de calcul, et rendu au format
PDF (mise en page proche d'un vrai KID reglementaire)."""

from __future__ import annotations

import html
import io
import re
from datetime import date
from typing import Any

from domain.priips.priips_engine import PriipsCalculation

TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _render_tokens(text: str, context: dict[str, Any]) -> str:
    if not text:
        return text

    def repl(m: re.Match) -> str:
        key = m.group(1)
        return str(context.get(key, m.group(0)))

    return TOKEN_RE.sub(repl, text)


def build_context(fund: dict[str, Any], calc: PriipsCalculation, app_settings: dict[str, Any]) -> dict[str, Any]:
    ctx = dict(fund)
    ctx.update({
        "generation_date": date.today().strftime("%d/%m/%Y"),
        "sri_class": calc.sri["sri_class"],
        "mrm_class": calc.sri["mrm_class"],
        "crm_class": calc.sri["crm_class"] if calc.sri["crm_class"] is not None else "N/A",
        "one_off_pct_total": calc.costs["one_off_pct_total"],
        "ongoing_pct_annual": calc.costs["ongoing_pct_annual"],
        "incidental_pct_annual": calc.costs["incidental_pct_annual"],
        "contact_placeholder": app_settings.get("contact_placeholder", ""),
    })
    return ctx


def build_kid(fund: dict[str, Any], calc: PriipsCalculation, template: dict[str, Any], app_settings: dict[str, Any]) -> dict[str, Any]:
    context = build_context(fund, calc, app_settings)
    rendered_sections = []
    for section in sorted(template["sections"], key=lambda s: s.get("order", 0)):
        rendered_sections.append({
            "id": section["id"],
            "title": _render_tokens(section["title"], context),
            "body": _render_tokens(section.get("body", ""), context),
            "fields": [
                {"label": f["label"], "value": _render_tokens(f["source"], context)}
                for f in section.get("fields", [])
            ],
            "performance_scenarios_note": _render_tokens(section.get("performance_scenarios_note", ""), context),
        })

    return {
        "fund_id": fund["fund_id"],
        "product_name": f"{fund['fund_name']} — {fund['share_class']}",
        "isin": fund["isin"],
        "generation_date": context["generation_date"],
        "template_name": template.get("template_name"),
        "template_version": template.get("template_version"),
        "layout": template.get("layout"),
        "theme_color": template.get("theme_color"),
        "table_header_bg": template.get("table_header_bg"),
        "table_border_color": template.get("table_border_color"),
        "title_alignment": template.get("title_alignment"),
        "sections": rendered_sections,
        "sri": calc.sri,
        "costs": calc.costs,
        "scenarios": calc.scenarios,
        "context": context,
    }


# ---------------------------------------------------------------------------
# Rendu PDF — document officiel
# ---------------------------------------------------------------------------
#
# Three genuinely distinct page layouts, selected per-template via the
# "layout" key ("classic" / "banner" / "sidebar") — not just a change of
# accent colour, but a different structural arrangement (masthead vs banded
# masthead vs a true two-column page), so templates stay visually
# distinguishable from one another beyond their palette.

def render_kid_pdf(kid: dict[str, Any], organisation_name: str, logo_bytes: bytes | None = None) -> bytes:
    """Genere le document PRIIPs KID au format PDF (mise en page proche d'un
    KID reglementaire reel : identification, risques, couts, scenarios)."""
    layout = str(kid.get("layout") or "classic").strip().lower()
    if layout == "banner":
        return _render_kid_pdf_banner(kid, organisation_name, logo_bytes)
    if layout == "sidebar":
        return _render_kid_pdf_sidebar(kid, organisation_name, logo_bytes)
    return _render_kid_pdf_classic(kid, organisation_name, logo_bytes)


def _table_base_style(header_bg: Any, border_color: Any) -> Any:
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _fields_table(section: dict[str, Any], table_style: Any, total_width_cm: float) -> Any:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Table
    if not section["fields"]:
        return None
    cell_style = ParagraphStyle("FieldCell", fontName="Helvetica", fontSize=8.3, leading=10.5)
    rows = [["Field", "Value"]] + [
        [Paragraph(html.escape(f["label"]), cell_style), Paragraph(html.escape(str(f["value"])), cell_style)]
        for f in section["fields"]
    ]
    t = Table(rows, colWidths=[total_width_cm * 0.34 * cm, total_width_cm * 0.66 * cm])
    t.setStyle(table_style)
    return t


def _scenario_table(kid: dict[str, Any], table_style: Any, total_width_cm: float) -> Any:
    from reportlab.lib.units import cm
    from reportlab.platypus import Table
    scen_header = ["Scenario"] + [h["horizon_label"] for h in kid["scenarios"]["by_horizon"]]
    scen_rows = [scen_header]
    for key, label in (("stress", "Stress"), ("unfavourable", "Unfavourable"), ("moderate", "Moderate"), ("favourable", "Favourable")):
        row = [label]
        for h in kid["scenarios"]["by_horizon"]:
            v = h[key]
            row.append(f"EUR {v['amount']:,.0f} ({v['return_pct']:+.1f} %/yr)".replace(",", " "))
        scen_rows.append(row)
    first_col = 3.2
    other_col = (total_width_cm - first_col) / max(1, len(scen_header) - 1)
    t = Table(scen_rows, colWidths=[first_col * cm] + [other_col * cm] * (len(scen_header) - 1))
    t.setStyle(table_style)
    return t


def _cost_flowables(kid: dict[str, Any], table_style: Any, total_width_cm: float) -> list[Any]:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table
    costs = kid["costs"]
    cell_style = ParagraphStyle("CostCell", fontName="Helvetica", fontSize=8.3, leading=10.5)
    comp_rows = [
        ["Cost type", "% per year (indicative)"],
        [Paragraph("One-off costs (entry/exit, amortised over the RHP)", cell_style), f"{costs['one_off_pct_total']:.2f} %"],
        [Paragraph("Ongoing costs (management, other ongoing costs, transaction)", cell_style), f"{costs['ongoing_pct_annual']:.2f} %"],
        [Paragraph("Incidental costs (performance fee)", cell_style), f"{costs['incidental_pct_annual']:.2f} %"],
    ]
    comp_table = Table(comp_rows, colWidths=[(total_width_cm - 5) * cm, 5 * cm])
    comp_table.setStyle(table_style)

    third = total_width_cm / 3
    cost_rows = [["Horizon", "Annualised RIY", "Cumulative impact (EUR)"]] + [
        [r["horizon_label"], f"{r['riy_pct']:.2f} %", f"{r['riy_amount_cumulative']:,.0f}".replace(",", " ")]
        for r in costs["by_horizon"]
    ]
    cost_table = Table(cost_rows, colWidths=[third * cm] * 3)
    cost_table.setStyle(table_style)
    return [comp_table, Spacer(1, 6), cost_table]


def _render_kid_pdf_classic(kid: dict[str, Any], organisation_name: str, logo_bytes: bytes | None = None) -> bytes:
    """'Classic' layout (the original/standard design): plain white page,
    left-aligned title, flat coloured section headings, numbered SRI scale
    with a highlighted box."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from domain.shared.brand import PRIMARY, SRI_COLORS

    primary_hex = kid.get("theme_color") or PRIMARY
    primary_color = colors.HexColor(primary_hex)
    table_header_bg = colors.HexColor(kid.get("table_header_bg") or "#F1F5F9")
    table_border_color = colors.HexColor(kid.get("table_border_color") or "#CCCCCC")
    title_align = 1 if kid.get("title_alignment") == "center" else 0

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title=f"KID — {kid['product_name']}",
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle("KidTitle", parent=styles["Title"], alignment=title_align, textColor=primary_color, fontSize=16, spaceAfter=2)
    style_meta = ParagraphStyle("KidMeta", parent=styles["Normal"], textColor=colors.HexColor("#555555"), fontSize=9, spaceAfter=10)
    style_h3 = ParagraphStyle("KidH3", parent=styles["Heading3"], textColor=primary_color, fontSize=11.5, spaceBefore=12, spaceAfter=4)
    style_body = ParagraphStyle("KidBody", parent=styles["Normal"], fontSize=9.3, leading=13)
    style_footer = ParagraphStyle("KidFooter", parent=styles["Normal"], fontSize=7.5, textColor=colors.HexColor("#888888"))

    table_base_style = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, table_border_color),
        ("BACKGROUND", (0, 0), (-1, 0), table_header_bg),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    story: list[Any] = []

    if logo_bytes:
        try:
            img = Image(io.BytesIO(logo_bytes))
            img.drawHeight = 1.1 * cm
            img.drawWidth = img.drawHeight * (img.imageWidth / img.imageHeight)
            story.append(img)
            story.append(Spacer(1, 6))
        except Exception:
            pass

    story.append(Paragraph(html.escape(kid["product_name"]), style_title))
    story.append(Paragraph(
        f"ISIN {html.escape(kid['isin'])} — document produced on {kid['generation_date']} — {html.escape(organisation_name)}",
        style_meta,
    ))

    for section in kid["sections"]:
        story.append(Paragraph(html.escape(section["title"]), style_h3))
        if section["body"]:
            story.append(Paragraph(html.escape(section["body"]).replace("\n", "<br/>"), style_body))

        if section["fields"]:
            rows = [["Field", "Value"]] + [[f["label"], str(f["value"])] for f in section["fields"]]
            t = Table(rows, colWidths=[5.5 * cm, 10.5 * cm])
            t.setStyle(table_base_style)
            story.append(Spacer(1, 4))
            story.append(t)

        if section["id"] == "risk_and_return":
            sri = kid["sri"]["sri_class"]
            scale_cells = [[Paragraph(str(c), ParagraphStyle("sri", parent=style_body, alignment=1, textColor=colors.white if c == sri else colors.HexColor("#333333"))) for c in range(1, 8)]]
            scale = Table(scale_cells, colWidths=[2.28 * cm] * 7, rowHeights=[0.9 * cm])
            scale_style = [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
            for i, c in enumerate(range(1, 8)):
                scale_style.append(("BACKGROUND", (i, 0), (i, 0), colors.HexColor(SRI_COLORS[c])))
                if c == sri:
                    scale_style.append(("BOX", (i, 0), (i, 0), 2, colors.HexColor("#0A2647")))
            scale.setStyle(TableStyle(scale_style))
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"Summary risk indicator: class {sri} / 7", style_body))
            story.append(Spacer(1, 4))
            story.append(scale)

            story.append(Spacer(1, 10))
            story.append(Paragraph(section.get("performance_scenarios_note", ""), ParagraphStyle("note", parent=style_body, fontSize=7.8, textColor=colors.HexColor("#666666"))))
            scen_header = ["Scenario"] + [h["horizon_label"] for h in kid["scenarios"]["by_horizon"]]
            scen_rows = [scen_header]
            for key, label in (("stress", "Stress"), ("unfavourable", "Unfavourable"), ("moderate", "Moderate"), ("favourable", "Favourable")):
                row = [label]
                for h in kid["scenarios"]["by_horizon"]:
                    v = h[key]
                    row.append(f"EUR {v['amount']:,.0f} ({v['return_pct']:+.1f} %/yr)".replace(",", " "))
                scen_rows.append(row)
            scen_table = Table(scen_rows, colWidths=[3.2 * cm] + [(16 * cm - 3.2 * cm) / max(1, len(scen_header) - 1)] * (len(scen_header) - 1))
            scen_table.setStyle(table_base_style)
            story.append(Spacer(1, 4))
            story.append(scen_table)

        if section["id"] == "costs":
            costs = kid["costs"]
            comp_rows = [
                ["Cost type", "% per year (indicative)"],
                ["One-off costs (entry/exit, amortised over the RHP)", f"{costs['one_off_pct_total']:.2f} %"],
                ["Ongoing costs (management, other ongoing costs, transaction)", f"{costs['ongoing_pct_annual']:.2f} %"],
                ["Incidental costs (performance fee)", f"{costs['incidental_pct_annual']:.2f} %"],
            ]
            comp_table = Table(comp_rows, colWidths=[11 * cm, 5 * cm])
            comp_table.setStyle(table_base_style)
            story.append(Spacer(1, 4))
            story.append(comp_table)

            cost_rows = [["Horizon", "Annualised RIY", "Cumulative impact (EUR)"]] + [
                [r["horizon_label"], f"{r['riy_pct']:.2f} %", f"{r['riy_amount_cumulative']:,.0f}".replace(",", " ")]
                for r in costs["by_horizon"]
            ]
            cost_table = Table(cost_rows, colWidths=[5.5 * cm, 5.5 * cm, 5 * cm])
            cost_table.setStyle(table_base_style)
            story.append(Spacer(1, 6))
            story.append(cost_table)

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Automatically generated by the PRIIPs KID module ({html.escape(organisation_name)}) — "
        f"template “{html.escape(str(kid['template_name']))}” ({html.escape(str(kid['template_version']))}). "
        "Simplified calculation methodology for demonstration purposes.",
        style_footer,
    ))

    doc.build(story)
    return buffer.getvalue()


def _render_kid_pdf_banner(kid: dict[str, Any], organisation_name: str, logo_bytes: bytes | None = None) -> bytes:
    """'Banner' layout: a full-width coloured masthead (logo + title in
    reversed-out white text) and section headings rendered as filled colour
    bars rather than plain text, plus a continuous SRI gauge bar (no grid
    lines, an emphasis box around the selected class) — a corporate
    letterhead look, structurally distinct from the classic layout."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from domain.shared.brand import PRIMARY, SRI_COLORS

    primary_hex = kid.get("theme_color") or PRIMARY
    primary_color = colors.HexColor(primary_hex)
    table_header_bg = colors.HexColor(kid.get("table_header_bg") or "#F1F5F9")
    table_border_color = colors.HexColor(kid.get("table_border_color") or "#CCCCCC")
    align = 1 if kid.get("title_alignment") == "center" else 0
    table_style = _table_base_style(table_header_bg, table_border_color)

    margin = 1.6
    content_width_cm = 21.0 - 2 * margin

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=margin * cm, rightMargin=margin * cm, topMargin=1.2 * cm, bottomMargin=1.6 * cm,
        title=f"KID — {kid['product_name']}",
    )

    style_title = ParagraphStyle("BnTitle", fontName="Helvetica-Bold", fontSize=15.5, textColor=colors.white, leading=18, alignment=align)
    style_meta = ParagraphStyle("BnMeta", fontName="Helvetica", fontSize=8.3, textColor=colors.HexColor("#DCE7F5"), spaceBefore=3, alignment=align)
    style_heading = ParagraphStyle("BnHeading", fontName="Helvetica-Bold", fontSize=10.5, textColor=colors.white, leading=13)
    style_body = ParagraphStyle("BnBody", fontName="Helvetica", fontSize=9.3, leading=13)
    style_footer = ParagraphStyle("BnFooter", fontName="Helvetica", fontSize=7.5, textColor=colors.HexColor("#888888"))

    story: list[Any] = []

    title_block = [
        Paragraph(html.escape(kid["product_name"]), style_title),
        Paragraph(
            f"ISIN {html.escape(kid['isin'])} — produced on {kid['generation_date']} — {html.escape(organisation_name)}",
            style_meta,
        ),
    ]
    if logo_bytes:
        try:
            img = Image(io.BytesIO(logo_bytes))
            img.drawHeight = 1.3 * cm
            img.drawWidth = img.drawHeight * (img.imageWidth / img.imageHeight)
            masthead = Table([[img, title_block]], colWidths=[2.6 * cm, (content_width_cm - 2.6) * cm])
        except Exception:
            masthead = Table([[title_block]], colWidths=[content_width_cm * cm])
    else:
        masthead = Table([[title_block]], colWidths=[content_width_cm * cm])
    masthead.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, -1), 12),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(masthead)
    story.append(Spacer(1, 12))

    def _heading_bar(text: str) -> Any:
        t = Table([[Paragraph(html.escape(text), style_heading)]], colWidths=[content_width_cm * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), primary_color),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    for section in kid["sections"]:
        story.append(_heading_bar(section["title"]))
        story.append(Spacer(1, 5))
        if section["body"]:
            story.append(Paragraph(html.escape(section["body"]).replace("\n", "<br/>"), style_body))

        ft = _fields_table(section, table_style, content_width_cm)
        if ft is not None:
            story.append(Spacer(1, 4))
            story.append(ft)

        if section["id"] == "risk_and_return":
            sri = kid["sri"]["sri_class"]
            col_w = content_width_cm / 7
            gauge = Table([[str(c) for c in range(1, 8)]], colWidths=[col_w * cm] * 7, rowHeights=[0.9 * cm])
            gauge_style = [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
            for i, c in enumerate(range(1, 8)):
                gauge_style.append(("BACKGROUND", (i, 0), (i, 0), colors.HexColor(SRI_COLORS[c])))
                gauge_style.append(("TEXTCOLOR", (i, 0), (i, 0), colors.white))
                if c == sri:
                    gauge_style.append(("BOX", (i, 0), (i, 0), 2.2, colors.white))
                    gauge_style.append(("FONTSIZE", (i, 0), (i, 0), 13))
            gauge.setStyle(TableStyle(gauge_style))

            story.append(Spacer(1, 8))
            story.append(Paragraph(f"Summary risk indicator: class {sri} / 7", style_body))
            story.append(Spacer(1, 4))
            story.append(gauge)
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                section.get("performance_scenarios_note", ""),
                ParagraphStyle("BnNote", parent=style_body, fontSize=7.8, textColor=colors.HexColor("#666666")),
            ))
            story.append(Spacer(1, 4))
            story.append(_scenario_table(kid, table_style, content_width_cm))

        if section["id"] == "costs":
            story.append(Spacer(1, 4))
            story.extend(_cost_flowables(kid, table_style, content_width_cm))

        story.append(Spacer(1, 10))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Automatically generated by the PRIIPs KID module ({html.escape(organisation_name)}) — "
        f"template “{html.escape(str(kid['template_name']))}” ({html.escape(str(kid['template_version']))}). "
        "Simplified calculation methodology for demonstration purposes.",
        style_footer,
    ))

    doc.build(story)
    return buffer.getvalue()


def _render_kid_pdf_sidebar(kid: dict[str, Any], organisation_name: str, logo_bytes: bytes | None = None) -> bytes:
    """'Sidebar' layout: a true two-column page on page 1 — a coloured left
    rail carrying the logo, product identification and a large SRI badge,
    with the regulatory sections flowing in the main column to the right.
    Falls back to a single full-width column (no sidebar, since the
    identification block has already been shown once) on any later page."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate, Frame, FrameBreak, Image, NextPageTemplate, PageTemplate,
        Paragraph, Spacer, Table, TableStyle,
    )

    from domain.shared.brand import PRIMARY, SRI_COLORS

    primary_hex = kid.get("theme_color") or PRIMARY
    primary_color = colors.HexColor(primary_hex)
    table_header_bg = colors.HexColor(kid.get("table_header_bg") or "#F1F5F9")
    table_border_color = colors.HexColor(kid.get("table_border_color") or "#CCCCCC")
    table_style = _table_base_style(table_header_bg, table_border_color)

    page_w, page_h = A4
    sidebar_w = 6.3 * cm
    gutter = 0.5 * cm
    margin = 1.4 * cm

    main_w_p1 = page_w - sidebar_w - gutter - margin
    main_width_cm = main_w_p1 / cm

    buffer = io.BytesIO()

    def _sidebar_bg(canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFillColor(primary_color)
        canvas.rect(0, 0, sidebar_w, page_h, stroke=0, fill=1)
        canvas.restoreState()

    def _later_rule(canvas, _doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(primary_color)
        canvas.setLineWidth(2)
        canvas.line(margin, page_h - 0.9 * cm, page_w - margin, page_h - 0.9 * cm)
        canvas.restoreState()

    sidebar_frame = Frame(0.5 * cm, 1 * cm, sidebar_w - 1 * cm, page_h - 2 * cm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="sidebar")
    main_frame_p1 = Frame(sidebar_w + gutter, margin, main_w_p1, page_h - 2 * margin, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main1")
    main_frame_later = Frame(margin, margin, page_w - 2 * margin, page_h - 2 * margin, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="mainlater")

    doc = BaseDocTemplate(buffer, pagesize=A4, title=f"KID — {kid['product_name']}")
    doc.addPageTemplates([
        PageTemplate(id="first", frames=[sidebar_frame, main_frame_p1], onPage=_sidebar_bg),
        PageTemplate(id="later", frames=[main_frame_later], onPage=_later_rule),
    ])

    style_sb_title = ParagraphStyle("SbTitle", fontName="Helvetica-Bold", fontSize=13, textColor=colors.white, leading=16)
    style_sb_label = ParagraphStyle("SbLabel", fontName="Helvetica-Bold", fontSize=7.3, textColor=colors.HexColor("#F1F5F9"), spaceBefore=8, spaceAfter=2)
    style_sb_value = ParagraphStyle("SbValue", fontName="Helvetica", fontSize=8.3, textColor=colors.white, leading=11)
    style_sri_big = ParagraphStyle("SriBig", fontName="Helvetica-Bold", fontSize=24, textColor=colors.white, alignment=1)
    style_sb_caption = ParagraphStyle("SbCaption", fontName="Helvetica", fontSize=7, textColor=colors.HexColor("#E2E8F0"), alignment=1, spaceBefore=3)
    style_heading = ParagraphStyle("SidebarHeading", fontName="Helvetica-Bold", fontSize=11, textColor=primary_color, spaceBefore=10, spaceAfter=4)
    style_body = ParagraphStyle("SidebarBody", fontName="Helvetica", fontSize=9.3, leading=13)
    style_footer = ParagraphStyle("SidebarFooter", fontName="Helvetica", fontSize=7.5, textColor=colors.HexColor("#888888"))

    story: list[Any] = [NextPageTemplate("later")]

    # --- Sidebar (page 1 only): logo, identification, SRI badge --------
    if logo_bytes:
        try:
            img = Image(io.BytesIO(logo_bytes))
            img.drawHeight = 1.4 * cm
            img.drawWidth = img.drawHeight * (img.imageWidth / img.imageHeight)
            story.append(img)
            story.append(Spacer(1, 10))
        except Exception:
            pass

    story.append(Paragraph(html.escape(kid["product_name"]), style_sb_title))

    id_section = next((s for s in kid["sections"] if s["id"] == "identification"), None)
    if id_section:
        for f in id_section["fields"]:
            story.append(Paragraph(html.escape(f["label"]).upper(), style_sb_label))
            story.append(Paragraph(html.escape(str(f["value"])), style_sb_value))

    sri = kid["sri"]["sri_class"]
    story.append(Spacer(1, 10))
    story.append(Paragraph("SUMMARY RISK INDICATOR", style_sb_label))
    badge = Table([[Paragraph(str(sri), style_sri_big)]], colWidths=[2.6 * cm], rowHeights=[2.6 * cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SRI_COLORS[sri])),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 2, colors.white),
    ]))
    story.append(badge)
    story.append(Paragraph(f"Risk class {sri} out of 7", style_sb_caption))

    story.append(FrameBreak())

    # --- Main column: all sections except identification (already shown) --
    for section in kid["sections"]:
        if section["id"] == "identification":
            continue
        story.append(Paragraph(html.escape(section["title"]), style_heading))
        if section["body"]:
            story.append(Paragraph(html.escape(section["body"]).replace("\n", "<br/>"), style_body))

        ft = _fields_table(section, table_style, main_width_cm)
        if ft is not None:
            story.append(Spacer(1, 4))
            story.append(ft)

        if section["id"] == "risk_and_return":
            story.append(Spacer(1, 8))
            story.append(Paragraph(
                section.get("performance_scenarios_note", ""),
                ParagraphStyle("SbNote", parent=style_body, fontSize=7.8, textColor=colors.HexColor("#666666")),
            ))
            story.append(Spacer(1, 4))
            story.append(_scenario_table(kid, table_style, main_width_cm))

        if section["id"] == "costs":
            story.append(Spacer(1, 4))
            story.extend(_cost_flowables(kid, table_style, main_width_cm))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        f"Automatically generated by the PRIIPs KID module ({html.escape(organisation_name)}) — "
        f"template “{html.escape(str(kid['template_name']))}” ({html.escape(str(kid['template_version']))}). "
        "Simplified calculation methodology for demonstration purposes.",
        style_footer,
    ))

    doc.build(story)
    return buffer.getvalue()
