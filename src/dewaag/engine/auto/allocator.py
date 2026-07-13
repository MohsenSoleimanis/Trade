"""L4 — The meta-brain (signal allocator).

The intelligent core. It does NOT predict prices — that is the fool's
errand every honest system refuses. It answers a solvable question:
given today's weather, WHOSE vote on the committee deserves weight, and
how confident should we be?

v1 (this file) is a transparent, regime-conditional ensemble: each
strategy's evidence-based prior is tilted by how well it fits the current
regime. Every number is inspectable — no black box.

    THE ML SLOT (v2, labeled and reserved): once the autonomy loop (L8) has
    graded enough of the system's OWN past decisions, a LightGBM meta-model
    replaces the fixed regime-fit table below with a learned one — "in THIS
    regime, these strategies actually worked." Same interface, so nothing
    downstream changes. Meta-labeling (López de Prado): the model decides
    whether to trust a signal, not what the price will do. It must beat this
    transparent baseline out-of-sample to earn its place — exactly as the
    signal engine's composite must be beaten to justify ML there.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dewaag.engine.auto.strategies import STRATEGIES, committee_scores


def _regime_fit(strat, tags: set[str]) -> float:
    """How much to trust this strategy in this weather. 1.0 = neutral."""
    fit = 1.0
    fit += 0.45 * len(strat.favored & tags)      # thrives here -> louder
    fit -= 0.40 * len(strat.disfavored & tags)   # struggles here -> quieter
    return max(0.1, fit)


def allocate(signals_df: pd.DataFrame, regime: dict) -> dict:
    """Blend the committee into one conviction per stock.

    Returns {weights, blended, table} where
      weights  : strategy key -> effective weight used today (for the UI)
      blended  : symbol -> {score 0..100, confidence 0..1, fired[list]}
      table    : per-strategy {prior, fit, weight} — the allocator's reasoning
    """
    tags = set(regime.get("tags", []))
    votes = committee_scores(signals_df)          # symbol x strategy, 0..100

    table = {}
    eff_weight = {}
    for strat in STRATEGIES:
        fit = _regime_fit(strat, tags)
        w = strat.prior * fit
        eff_weight[strat.key] = w
        table[strat.key] = {"name": strat.name, "prior": round(strat.prior, 2),
                            "fit": round(fit, 2), "weight": round(w, 3),
                            "favored": sorted(strat.favored & tags)}
    tot = sum(eff_weight.values()) or 1.0
    eff_norm = {k: v / tot for k, v in eff_weight.items()}

    blended: dict[str, dict] = {}
    for sym, row in votes.iterrows():
        num = den = 0.0
        contrib = []
        for key, w in eff_norm.items():
            v = row.get(key)
            if pd.isna(v):
                continue
            num += w * float(v)
            den += w
            contrib.append((key, float(v), w))
        if den == 0:
            continue
        score = num / den

        # confidence = how much the loudest voices AGREE, scaled by coverage.
        # a name only one strategy likes is a weaker call than one five agree on.
        top = sorted(contrib, key=lambda c: -c[2])[:5]
        top_scores = np.array([c[1] for c in top])
        agreement = 1.0 - float(np.std(top_scores)) / 50.0          # 0..1
        coverage = min(1.0, len(contrib) / 6.0)
        confidence = max(0.0, min(1.0, 0.5 * max(0.0, agreement) + 0.5 * coverage))

        fired = [c[0] for c in sorted(contrib, key=lambda c: -(c[1] * c[2]))[:3] if c[1] >= 60]
        blended[sym] = {"score": round(score, 1),
                        "confidence": round(confidence, 2),
                        "fired": fired}

    return {"weights": {k: round(v, 3) for k, v in eff_norm.items()},
            "blended": blended, "table": table,
            "method": "v1 transparent regime-conditional ensemble (ML meta-learner is the reserved v2 slot)"}
