"""Gestion des templates de configuration : template PRIIPs KID (JSON/YAML),
parametres RTS et preferences applicatives.

Le template PRIIPs KID standardise la structure du document reglementaire
(sections, libelles, textes-types) telle que definie par le Reglement PRIIPs
(UE) 1286/2014 et ses RTS (UE) 2017/653 modifies par (UE) 2021/2268 :
identification produit, nature du produit, risques et rendement potentiel,
couts, duree de detention recommandee, reclamations, informations
complementaires. Les champs entre doubles accolades ``{{ }}`` sont remplaces
automatiquement par les donnees du fonds et les resultats du moteur de
calcul lors de la generation d'un KID (cf. ``domain.priips.kid_generator``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from domain.shared.io_utils import ensure_dir_resilient, write_bytes_resilient, write_text_resilient
from domain.priips.priips_engine import DEFAULT_RTS_PARAMETERS

from utils.paths import RESOURCES_DIR, org_config_dir
CONFIG_DIR = RESOURCES_DIR / "config"
TEMPLATES_DIR = RESOURCES_DIR / "templates"
RTS_PARAMETERS_JSON = CONFIG_DIR / "rts_parameters.json"


def _app_settings_json() -> Path:
    """The settings are the organisation's own: its name and logo go on
    every KID it produces."""
    return org_config_dir() / "app_settings.json"


DEFAULT_KID_TEMPLATE: dict[str, Any] = {
    "template_name": "Standard PRIIPs KID — UCITS / AIF",
    "template_version": "2021/2268 (amending RTS)",
    "language": "en",
    "legal_basis": [
        "Regulation (EU) No 1286/2014 (PRIIPs)",
        "Delegated Regulation (EU) 2017/653",
        "Amending Delegated Regulation (EU) 2021/2268",
    ],
    "document_title": "Key Information Document",
    # Visual identity: "layout" picks one of three structurally distinct PDF
    # page designs (see domain.priips.kid_generator.render_kid_pdf) — "classic" (plain
    # page, flat headings), "banner" (coloured masthead + banded section
    # headings + continuous SRI gauge) or "sidebar" (true two-column page
    # with a coloured identification rail). theme_color/table_header_bg/
    # table_border_color/title_alignment further customise that layout's
    # palette without changing its structure.
    "layout": "classic",
    "theme_color": None,
    "table_header_bg": None,
    "table_border_color": None,
    "title_alignment": "left",
    "sections": [
        {
            "id": "purpose",
            "order": 1,
            "title": "Purpose",
            "body": (
                "This document provides you with key information about this investment product. "
                "It is not marketing material. The information is required by law to help you understand the "
                "nature, risks, costs, potential gains and losses of this product and to help you compare it "
                "with other products."
            ),
            "fields": [],
        },
        {
            "id": "identification",
            "order": 2,
            "title": "Product identification",
            "body": "",
            "fields": [
                {"key": "product_name", "label": "Product name", "source": "{{ fund_name }} — {{ share_class }}"},
                {"key": "isin", "label": "ISIN code", "source": "{{ isin }}"},
                {"key": "manufacturer", "label": "Manufacturer (ManCo)", "source": "{{ manco }}"},
                {"key": "promoter", "label": "Promoter", "source": "{{ promoter }}"},
                {"key": "regulator", "label": "Competent authority", "source": "Commission de Surveillance du Secteur Financier (CSSF)"},
                {"key": "production_date", "label": "Date of production of the document", "source": "{{ generation_date }}"},
                {"key": "contact", "label": "For more information", "source": "{{ manco }} — {{ contact_placeholder }}"},
            ],
        },
        {
            "id": "what_is_it",
            "order": 3,
            "title": "What is this product?",
            "body": "",
            "fields": [
                {"key": "legal_form", "label": "Type", "source": "{{ legal_form }} under Luxembourg law, {{ regime }} regime"},
                {"key": "term", "label": "Term", "source": "No maturity date. Recommended holding period: {{ rhp_years }} years."},
                {"key": "objectives", "label": "Objectives", "source": "{{ objective_text }}"},
                {"key": "benchmark", "label": "Benchmark", "source": "{{ benchmark }}"},
                {"key": "target_investor", "label": "Intended retail investor", "source": "{{ investor_profile_text }}"},
            ],
        },
        {
            "id": "risk_and_return",
            "order": 4,
            "title": "What are the risks and what could I get in return?",
            "body": (
                "The summary risk indicator is a guide to the level of risk of this product compared to other "
                "products. It shows how likely it is that the product will lose money because of movements in "
                "the markets or because we are not able to pay you."
            ),
            "fields": [
                {"key": "sri", "label": "Summary risk indicator (1 to 7)", "source": "{{ sri_class }}"},
                {"key": "mrm", "label": "Market risk measure (MRM)", "source": "{{ mrm_class }}"},
                {"key": "crm", "label": "Credit risk measure (CRM)", "source": "{{ crm_class }}"},
                {"key": "max_loss_note", "label": "Maximum possible loss", "source": "It is possible that you will not receive the expected amounts and that you could lose some or all of your investment."},
            ],
            "performance_scenarios_note": (
                "The figures shown include all the costs of the product itself. The figures do not take into "
                "account your personal tax situation, which may also affect how much you get back. What you will "
                "get from this product depends on future market performance, which is uncertain and cannot be "
                "accurately predicted."
            ),
        },
        {
            "id": "insolvency",
            "order": 5,
            "title": "What happens if {{ manco }} is unable to pay out?",
            "body": (
                "The product is a legal entity separate from the manufacturer; assets are held with an "
                "independent depositary in accordance with applicable regulation. In the event of the failure of "
                "the manufacturer or the manager, this should not result in a financial loss directly caused by "
                "that failure."
            ),
            "fields": [],
        },
        {
            "id": "costs",
            "order": 6,
            "title": "What are the costs?",
            "body": (
                "The Reduction In Yield (RIY) shows what impact the total costs you pay will have on the "
                "investment return you might get. The total costs take into account one-off, ongoing and "
                "incidental costs."
            ),
            "fields": [
                {"key": "one_off_costs", "label": "One-off costs (entry/exit)", "source": "{{ one_off_pct_total }} %"},
                {"key": "ongoing_costs", "label": "Annual ongoing costs", "source": "{{ ongoing_pct_annual }} %"},
                {"key": "incidental_costs", "label": "Incidental costs (performance fee)", "source": "{{ incidental_pct_annual }} %"},
            ],
        },
        {
            "id": "holding_period",
            "order": 7,
            "title": "How long should I hold it and can I take money out early?",
            "body": "Recommended holding period: {{ rhp_years }} years. This product has no minimum holding period but is designed for a medium/long-term investment.",
            "fields": [],
        },
        {
            "id": "complaints",
            "order": 8,
            "title": "How can I complain?",
            "body": (
                "Any complaint regarding the product or the conduct of the manufacturer or the distributor may "
                "be sent in writing to {{ manco }}, or to the distributor who advised you. Full contact details "
                "are available on request."
            ),
            "fields": [],
        },
        {
            "id": "other_information",
            "order": 9,
            "title": "Other relevant information",
            "body": (
                "Additional information (prospectus, latest annual and semi-annual reports, net asset values) is "
                "available free of charge, in French and/or English, from {{ manco }} and on its website. This "
                "product may be subject to country-specific information depending on the country of distribution."
            ),
            "fields": [],
        },
    ],
    "cost_over_time_horizons": ["1 year", "1/2 RHP", "RHP"],
    "performance_scenarios": ["stress", "unfavourable", "moderate", "favourable"],
    "output_formats": ["PDF", "HTML", "XML (indicative structure)", "JSON"],
}


DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "organisation_name": "Forvis Mazars Luxembourg",
    "product_line": "Forvis Mazars Regulatory Reporting Platform",
    "default_currency": "EUR",
    "four_eyes_review_required": True,
    "contact_placeholder": "kid-support@example-manco.lu",
    "output_folder": "data/runtime/generated_kids",
    "logo_filename": None,
}

LOGO_ALLOWED_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _ensure_dir() -> None:
    ensure_dir_resilient(CONFIG_DIR)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _ensure_dir()
    write_text_resilient(path, json.dumps(data, ensure_ascii=False, indent=2))


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    _ensure_dir()
    write_text_resilient(path, yaml.dump(data, allow_unicode=True, sort_keys=False, width=100))


def ensure_default_files() -> None:
    """Cree les fichiers de configuration par defaut s'ils n'existent pas encore."""
    _ensure_dir()
    ensure_dir_resilient(TEMPLATES_DIR)
    
    std_json = TEMPLATES_DIR / "standard.json"
    std_yaml = TEMPLATES_DIR / "standard.yaml"
    
    if not std_json.exists():
        _write_json(std_json, DEFAULT_KID_TEMPLATE)
    if not std_yaml.exists():
        _write_yaml(std_yaml, DEFAULT_KID_TEMPLATE)
    if not RTS_PARAMETERS_JSON.exists():
        _write_json(RTS_PARAMETERS_JSON, DEFAULT_RTS_PARAMETERS)


# --- Template PRIIPs KID -----------------------------------------------------

def list_templates() -> list[str]:
    ensure_default_files()
    templates = []
    for f in TEMPLATES_DIR.glob("*.yaml"):
        templates.append(f.stem)
    return sorted(list(set(templates)))


def load_kid_template(template_name: str = "standard") -> dict[str, Any]:
    ensure_default_files()
    path = TEMPLATES_DIR / f"{template_name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    
    path = TEMPLATES_DIR / f"{template_name}.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8"))
        
    return DEFAULT_KID_TEMPLATE


def load_kid_template_text(template_name: str = "standard", fmt: str = "json") -> str:
    ensure_default_files()
    path = TEMPLATES_DIR / f"{template_name}.{fmt}"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def save_kid_template_from_text(template_name: str, text: str, fmt: str = "json") -> dict[str, Any]:
    """Validate then save the template in both formats (single source of truth)."""
    data = json.loads(text) if fmt == "json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("The template must be an object / dictionary.")
    
    _write_json(TEMPLATES_DIR / f"{template_name}.json", data)
    _write_yaml(TEMPLATES_DIR / f"{template_name}.yaml", data)
    return data


def reset_kid_template(template_name: str = "standard") -> dict[str, Any]:
    _write_json(TEMPLATES_DIR / f"{template_name}.json", DEFAULT_KID_TEMPLATE)
    _write_yaml(TEMPLATES_DIR / f"{template_name}.yaml", DEFAULT_KID_TEMPLATE)
    return DEFAULT_KID_TEMPLATE


# --- Parametres RTS -----------------------------------------------------------

def load_rts_parameters() -> dict[str, Any]:
    ensure_default_files()
    return json.loads(RTS_PARAMETERS_JSON.read_text(encoding="utf-8"))


def save_rts_parameters(data: dict[str, Any]) -> None:
    _write_json(RTS_PARAMETERS_JSON, data)


def reset_rts_parameters() -> dict[str, Any]:
    _write_json(RTS_PARAMETERS_JSON, DEFAULT_RTS_PARAMETERS)
    return DEFAULT_RTS_PARAMETERS


# --- Preferences applicatives ---------------------------------------------

def load_app_settings() -> dict[str, Any]:
    ensure_default_files()
    path = _app_settings_json()
    if not path.exists():
        return dict(DEFAULT_APP_SETTINGS)
    return json.loads(path.read_text(encoding="utf-8"))


def save_app_settings(data: dict[str, Any]) -> None:
    path = _app_settings_json()
    ensure_dir_resilient(path.parent)
    write_text_resilient(path, json.dumps(data, ensure_ascii=False, indent=2))


# --- Logo de l'entreprise ---------------------------------------------------

def save_logo(file_bytes: bytes, original_filename: str) -> str:
    """Enregistre le logo televerse et retourne son nom de fichier."""
    ext = Path(original_filename).suffix.lower()
    if ext not in LOGO_ALLOWED_EXTENSIONS:
        raise ValueError("Format non supporte : utilisez un fichier PNG ou JPG.")
    remove_logo()
    ensure_dir_resilient(org_config_dir())
    filename = f"logo{ext}"
    write_bytes_resilient(org_config_dir() / filename, file_bytes)
    settings = load_app_settings()
    settings["logo_filename"] = filename
    save_app_settings(settings)
    return filename


def remove_logo() -> None:
    settings = load_app_settings()
    for ext in LOGO_ALLOWED_EXTENSIONS:
        candidate = org_config_dir() / f"logo{ext}"
        if candidate.exists():
            candidate.unlink()
    if settings.get("logo_filename"):
        settings["logo_filename"] = None
        save_app_settings(settings)


def get_logo_bytes() -> tuple[bytes, str] | None:
    """Retourne (contenu, type MIME) du logo courant, ou None si absent."""
    settings = load_app_settings()
    filename = settings.get("logo_filename")
    if not filename:
        return None
    path = org_config_dir() / filename
    if not path.exists():
        return None
    ext = path.suffix.lower()
    return path.read_bytes(), LOGO_ALLOWED_EXTENSIONS.get(ext, "application/octet-stream")
