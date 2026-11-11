"""Stage 4: RFM scoring, rule-based segments and a K-means cross-check.

Frequency and monetary value are per active month of tenure (transactions_per_month,
avg_monthly_net_spend), so a customer who joined recently isn't marked low-value
just because they've had less time to spend.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

import config

RFM_COLUMNS = {"recency": "recency_days", "frequency": "transactions_per_month",
               "monetary": "avg_monthly_net_spend"}


def _quintile(s: pd.Series, ascending: bool) -> pd.Series:
    """Scores 1-5; ranking first so ties can't collapse the bins."""
    ranked = s.rank(method="first", ascending=ascending)
    return pd.qcut(ranked, 5, labels=[1, 2, 3, 4, 5]).astype(int)


# Recency uses fixed day bands, not quintiles: in a card base most customers transact
# daily, so recency is heavily tied (91% at 1 day in this data) and quintiles would
# split tied customers arbitrarily.
RECENCY_BANDS = [(1, 5), (7, 4), (30, 3), (90, 2)]  # (max days, score); older -> 1


def _recency_score(days: pd.Series) -> pd.Series:
    score = pd.Series(1, index=days.index)
    for max_days, s in reversed(RECENCY_BANDS):
        score = score.mask(days <= max_days, s)
    return score.astype(int)


def rfm_scores(profile: pd.DataFrame) -> pd.DataFrame:
    rfm = profile[["user_id", *RFM_COLUMNS.values()]].copy()
    rfm["R"] = _recency_score(rfm["recency_days"])
    rfm["F"] = _quintile(rfm["transactions_per_month"], ascending=True)
    rfm["M"] = _quintile(rfm["avg_monthly_net_spend"], ascending=True)
    rfm["FM"] = ((rfm["F"] + rfm["M"]) / 2).round().astype(int)
    rfm["RFM_score"] = rfm["R"] + rfm["F"] + rfm["M"]
    rfm["segment"] = np.select(
        [
            (rfm["R"] >= 4) & (rfm["FM"] >= 4),
            (rfm["R"] >= 3) & (rfm["FM"] >= 3),
            (rfm["R"] >= 4) & (rfm["FM"] <= 2),
            (rfm["R"] <= 2) & (rfm["FM"] >= 4),
            (rfm["R"] <= 2) & (rfm["FM"] >= 3),
        ],
        ["Champions", "Loyal", "Promising", "Can't Lose", "At Risk"],
        default="Hibernating",
    )
    return rfm


SEGMENT_ORDER = ["Champions", "Loyal", "Promising", "Can't Lose", "At Risk", "Hibernating"]


def _scaled(rfm: pd.DataFrame) -> np.ndarray:
    # log1p tames the long right tail of spend and frequency before scaling
    x = rfm[list(RFM_COLUMNS.values())].clip(lower=0)
    return StandardScaler().fit_transform(np.log1p(x))


def choose_k(rfm: pd.DataFrame, k_range=range(2, 9)) -> pd.DataFrame:
    x = _scaled(rfm)
    rows = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=config.RANDOM_STATE, n_init=10).fit(x)
        rows.append({"k": k, "inertia": km.inertia_, "silhouette": silhouette_score(x, km.labels_)})
    return pd.DataFrame(rows)


def kmeans_clusters(rfm: pd.DataFrame, k: int) -> pd.Series:
    """Cluster labels renumbered so that cluster 1 has the highest mean RFM score."""
    labels = KMeans(n_clusters=k, random_state=config.RANDOM_STATE, n_init=10).fit_predict(_scaled(rfm))
    order = (pd.Series(rfm["RFM_score"].to_numpy()).groupby(labels).mean()
             .sort_values(ascending=False).index)
    remap = {old: new for new, old in enumerate(order, start=1)}
    return pd.Series(labels, index=rfm.index).map(remap).rename("cluster")
