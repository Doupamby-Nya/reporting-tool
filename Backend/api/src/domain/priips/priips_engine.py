"""Moteur de calcul PRIIPs simplifie : SRI, couts (RIY) et scenarios de performance.

IMPORTANT — Portee de la maquette
----------------------------------
Ce moteur implemente une methodologie SIMPLIFIEE et PARAMETRABLE, construite
dans l'esprit du Reglement PRIIPs (UE) 2017/653 et de ses RTS (bandes de
volatilite pour l'indicateur de risque de marche, structure des couts en
trois blocs, scenarios de performance a plusieurs horizons). Elle vise a
demontrer la chaine de bout en bout (ingestion -> moteur -> generation ->
controle) sur des donnees realistes, PAS a se substituer a une validation
actuarielle/reglementaire. Les parametres (bandes, quantiles, ponderations)
sont modifiables depuis l'onglet Configuration et doivent etre recalibres
par l'equipe reglementaire avant toute mise en production.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Parametres par defaut (repris si data/config/rts_parameters.json est absent)
# ---------------------------------------------------------------------------

DEFAULT_RTS_PARAMETERS: dict[str, Any] = {
    "mrm_volatility_bands_pct": [
        {"class": 1, "max_vol_pct": 0.5},
        {"class": 2, "max_vol_pct": 5.0},
        {"class": 3, "max_vol_pct": 12.0},
        {"class": 4, "max_vol_pct": 20.0},
        {"class": 5, "max_vol_pct": 30.0},
        {"class": 6, "max_vol_pct": 80.0},
        {"class": 7, "max_vol_pct": None},
    ],
    "credit_risk_relevant_asset_classes": [
        "Investment Grade Corporate Bonds",
        "High Yield Bonds",
        "Short-Term Money Market",
        "European Private Debt",
    ],
    "scenario_quantiles": {
        "stress_z": -2.33,
        "unfavourable_z": -1.28,
        "moderate_z": 0.0,
        "favourable_z": 1.28,
    },
    "stress_extra_vol_mult": 1.0,
    "reference_investment_amount": 10000,
    "methodology_note": (
        "Simplified/indicative methodology for demonstration purposes — "
        "to be calibrated with the Mazars regulatory team before production use."
    ),
}


def _mrm_bands(params: dict[str, Any]) -> list[tuple[int, float | None]]:
    return [(b["class"], b["max_vol_pct"]) for b in params["mrm_volatility_bands_pct"]]


def compute_mrm(sigma_pct: float, params: dict[str, Any]) -> int:
    """Classe de risque de marche (1-7) a partir de la volatilite annualisee."""
    for cls, max_vol in _mrm_bands(params):
        if max_vol is None or sigma_pct < max_vol:
            return cls
    return 7


def compute_crm(credit_quality_step: int, duration_years: float) -> int:
    """Classe de risque de credit (1-6), regle simplifiee et monotone.

    CQS 0 (souverain/AAA-AA) -> risque minimal ; CQS croissant et duration
    longue (>5 ans) majorent la classe. Regle indicative, non la matrice
    officielle de l'Annexe II des RTS.
    """
    base = 1 + round(credit_quality_step * 0.85)
    if duration_years and duration_years > 5:
        base += 1
    return max(1, min(6, int(base)))


def compute_sri(fund: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    mrm = compute_mrm(float(fund["sigma_pct"]), params)
    credit_relevant = fund.get("asset_class") in params.get("credit_risk_relevant_asset_classes", [])
    crm = None
    sri = mrm
    if credit_relevant and float(fund.get("credit_quality_step", 0) or 0) >= 0:
        crm = compute_crm(int(fund.get("credit_quality_step", 0) or 0), float(fund.get("duration_years", 0) or 0))
        sri = max(mrm, crm)
    sri = max(1, min(7, int(sri)))
    return {
        "mrm_class": mrm,
        "crm_class": crm,
        "sri_class": sri,
        "credit_risk_material": bool(crm is not None),
    }


# ---------------------------------------------------------------------------
# Couts (structure a trois blocs + Reduction en Rendement / RIY)
# ---------------------------------------------------------------------------

def compute_costs(fund: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    amount = params.get("reference_investment_amount", 10000)
    rhp = max(1, int(fund["rhp_years"]))
    horizons = sorted({1, max(1, rhp // 2), rhp})

    one_off_pct = float(fund["entry_cost_pct"]) + float(fund["exit_cost_pct"])
    ongoing_pct = float(fund["mgmt_fee_pct"]) + float(fund["other_ongoing_pct"]) + float(fund["transaction_cost_pct"])
    incidental_pct = float(fund.get("perf_fee_pct", 0) or 0) * 0.30  # approx. esperance annualisee de la commission de perf.

    rows = []
    for t in horizons:
        one_off_amortized = one_off_pct / t
        riy_pct = one_off_amortized + ongoing_pct + incidental_pct
        riy_amount = amount * (riy_pct / 100.0)  # impact annualise moyen
        cumulative_amount = riy_amount * t
        rows.append({
            "horizon_years": t,
            "horizon_label": "1 year" if t == 1 else f"{t} years" + (" (RHP)" if t == rhp else " (1/2 RHP)" if t == max(1, rhp // 2) and t != rhp else ""),
            "one_off_amortized_pct": round(one_off_amortized, 3),
            "ongoing_pct": round(ongoing_pct, 3),
            "incidental_pct": round(incidental_pct, 3),
            "riy_pct": round(riy_pct, 3),
            "riy_amount_annual": round(riy_amount, 2),
            "riy_amount_cumulative": round(cumulative_amount, 2),
        })

    return {
        "reference_amount": amount,
        "rhp_years": rhp,
        "one_off_pct_total": round(one_off_pct, 3),
        "ongoing_pct_annual": round(ongoing_pct, 3),
        "incidental_pct_annual": round(incidental_pct, 3),
        "by_horizon": rows,
    }


# ---------------------------------------------------------------------------
# Scenarios de performance (approche parametrique log-normale)
# ---------------------------------------------------------------------------

def _lognormal_value(amount: float, mu: float, sigma: float, t: float, z: float) -> float:
    drift = (mu - 0.5 * sigma ** 2) * t
    shock = sigma * math.sqrt(max(t, 1e-9)) * z
    return amount * math.exp(drift + shock)


def compute_scenarios(fund: dict[str, Any], params: dict[str, Any], costs: dict[str, Any]) -> dict[str, Any]:
    amount = params.get("reference_investment_amount", 10000)
    rhp = max(1, int(fund["rhp_years"]))
    horizons = sorted({1, rhp})
    mu = float(fund["mu_pct"]) / 100.0
    sigma = float(fund["sigma_pct"]) / 100.0
    stress_mult = float(fund.get("stress_sigma_mult", 1.5) or 1.5) * params.get("stress_extra_vol_mult", 1.0)
    q = params["scenario_quantiles"]

    riy_by_h = {r["horizon_years"]: r["riy_pct"] / 100.0 for r in costs["by_horizon"]}

    def net_mu(t: int) -> float:
        riy = riy_by_h.get(t, riy_by_h[max(riy_by_h)])
        return mu - riy

    scenarios = []
    for t in horizons:
        nmu = net_mu(t)
        stress_val = _lognormal_value(amount, mu, sigma * stress_mult, t, q["stress_z"])
        unfav_val = _lognormal_value(amount, nmu, sigma, t, q["unfavourable_z"])
        mod_val = _lognormal_value(amount, nmu, sigma, t, q["moderate_z"])
        fav_val = _lognormal_value(amount, nmu, sigma, t, q["favourable_z"])

        def ann_return(v: float) -> float:
            return ((v / amount) ** (1 / t) - 1) * 100.0

        scenarios.append({
            "horizon_years": t,
            "horizon_label": "1 year" if t == 1 else f"{t} years (RHP)",
            "stress": {"amount": round(stress_val, 2), "return_pct": round(ann_return(stress_val), 2)},
            "unfavourable": {"amount": round(unfav_val, 2), "return_pct": round(ann_return(unfav_val), 2)},
            "moderate": {"amount": round(mod_val, 2), "return_pct": round(ann_return(mod_val), 2)},
            "favourable": {"amount": round(fav_val, 2), "return_pct": round(ann_return(fav_val), 2)},
        })

    return {"reference_amount": amount, "rhp_years": rhp, "by_horizon": scenarios}


@dataclass
class PriipsCalculation:
    fund: dict[str, Any]
    sri: dict[str, Any] = field(default_factory=dict)
    costs: dict[str, Any] = field(default_factory=dict)
    scenarios: dict[str, Any] = field(default_factory=dict)


def run_full_calculation(fund: dict[str, Any], params: dict[str, Any] | None = None) -> PriipsCalculation:
    params = params or DEFAULT_RTS_PARAMETERS
    sri = compute_sri(fund, params)
    costs = compute_costs(fund, params)
    scenarios = compute_scenarios(fund, params, costs)
    return PriipsCalculation(fund=fund, sri=sri, costs=costs, scenarios=scenarios)
