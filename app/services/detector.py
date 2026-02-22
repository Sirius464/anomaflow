"""
AnomaFlow v2.0 — Service de détection d'anomalies
Corrections & améliorations v2 :
  - Détection de fréquence par fenêtre glissante d'1 heure (vraie logique)
  - Détection des heures non standards (ex: 22h–6h UTC)
  - Détection des montants quasi-ronds (tolérance configurable ±2 %)
  - Déduplication par transaction_id pour éviter les doublons
  - Score de risque global agrégé
  - IsolationForest (ML) si ML_ENABLED=true
  - Typage strict et docstrings
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────

AnomalyDict = dict[str, Any]

# ── Constantes ────────────────────────────────────────────────────────────────

SEVERITY_HIGH   = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW    = "LOW"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_quasi_round(amount: float) -> float | None:
    """
    Retourne le montant rond cible si `amount` en est proche
    (dans la tolérance ±ROUND_AMOUNT_TOLERANCE), sinon None.
    """
    tol = settings.ROUND_AMOUNT_TOLERANCE
    for target in settings.SUSPICIOUS_ROUND_AMOUNTS:
        if target == 0:
            continue
        if abs(amount - target) / target <= tol:
            return target
    return None


def _is_off_hours(ts: pd.Timestamp) -> bool:
    """
    Retourne True si l'heure UTC de la transaction est hors des
    heures ouvrées configurées.
    """
    h_start = settings.SUSPICIOUS_HOUR_START   # ex: 22
    h_end   = settings.SUSPICIOUS_HOUR_END     # ex:  6
    hour = ts.hour
    if h_start > h_end:                        # plage chevauchant minuit
        return hour >= h_start or hour < h_end
    return h_end <= hour < h_start             # plage intra-journée (rare)


def _make_anomaly(
    row: pd.Series,
    anomaly_type: str,
    reason: str,
    severity: str,
    confidence: float,
) -> AnomalyDict:
    """Construit un dictionnaire d'anomalie normalisé."""
    ts = row.get("timestamp")
    ts_str = str(ts) if pd.notna(ts) else ""
    return {
        "transaction_id":  str(row["transaction_id"]),
        "user_id":         str(row["user_id"]),
        "amount":          float(row["amount"]),
        "timestamp":       ts_str,
        "anomaly_type":    anomaly_type,
        "reason":          reason,
        "severity":        severity,
        "confidence_score": round(min(1.0, max(0.0, confidence)), 4),
    }


# ── Règles de détection ───────────────────────────────────────────────────────

def _detect_unusual_amounts(df: pd.DataFrame) -> list[AnomalyDict]:
    """Détecte les montants statistiquement aberrants (z-score)."""
    mean   = df["amount"].mean()
    std    = df["amount"].std()
    if std == 0:
        return []

    threshold = mean + settings.ANOMALY_THRESHOLD_MULTIPLIER * std
    anomalies = []

    flagged = df[df["amount"] > threshold]
    for _, row in flagged.iterrows():
        excess = row["amount"] - threshold
        confidence = min(1.0, excess / mean) if mean > 0 else 0.5
        anomalies.append(
            _make_anomaly(
                row,
                anomaly_type="unusual_amount",
                reason=f"Montant {row['amount']:.2f}€ dépasse le seuil de {threshold:.2f}€ (µ={mean:.2f}€, σ={std:.2f}€)",
                severity=SEVERITY_HIGH,
                confidence=confidence,
            )
        )
    return anomalies


def _detect_quasi_round_amounts(df: pd.DataFrame) -> list[AnomalyDict]:
    """
    Détecte les montants proches d'un arrondi suspect (±ROUND_AMOUNT_TOLERANCE %).
    Corrige l'égalité stricte de la v1 qui manquait 999.99€ ou 500.01€.
    """
    anomalies = []
    for _, row in df.iterrows():
        target = _is_quasi_round(row["amount"])
        if target is not None:
            anomalies.append(
                _make_anomaly(
                    row,
                    anomaly_type="round_amount",
                    reason=f"Montant {row['amount']:.2f}€ proche du seuil suspect de {target:.0f}€",
                    severity=SEVERITY_MEDIUM,
                    confidence=0.65,
                )
            )
    return anomalies


def _detect_high_frequency(df: pd.DataFrame) -> list[AnomalyDict]:
    """
    Détecte les utilisateurs avec un nombre excessif de transactions
    sur une fenêtre glissante d'1 heure.
    Corrige la v1 qui comptait le total du fichier entier.
    """
    anomalies: list[AnomalyDict] = []

    # On ne peut analyser la fréquence que si les timestamps sont valides
    if df["timestamp"].isna().all():
        logger.warning("Aucun timestamp valide — détection de fréquence ignorée")
        return anomalies

    df_ts = df.dropna(subset=["timestamp"]).copy()
    df_ts = df_ts.sort_values("timestamp")
    limit = settings.MAX_TRANSACTIONS_PER_HOUR

    for user_id, group in df_ts.groupby("user_id"):
        times = group["timestamp"].tolist()
        # Fenêtre glissante O(n²) acceptable pour des fichiers CSV ≤ 50k lignes
        for i, current_time in enumerate(times):
            window_end   = current_time
            window_start = current_time - timedelta(hours=1)
            count_in_window = sum(
                1 for t in times[max(0, i - limit * 2): i + 1]
                if window_start <= t <= window_end
            )
            if count_in_window > limit:
                row = group.iloc[i]
                anomalies.append(
                    _make_anomaly(
                        row,
                        anomaly_type="high_frequency",
                        reason=(
                            f"Utilisateur {user_id} : {count_in_window} transactions "
                            f"en 1h (limite : {limit})"
                        ),
                        severity=SEVERITY_HIGH,
                        confidence=min(1.0, count_in_window / limit),
                    )
                )
                break  # Une seule anomalie par fenêtre par utilisateur

    return anomalies


def _detect_off_hours(df: pd.DataFrame) -> list[AnomalyDict]:
    """Détecte les transactions effectuées en dehors des heures ouvrées."""
    anomalies = []
    h_start = settings.SUSPICIOUS_HOUR_START
    h_end   = settings.SUSPICIOUS_HOUR_END

    valid = df.dropna(subset=["timestamp"])
    for _, row in valid.iterrows():
        if _is_off_hours(row["timestamp"]):
            anomalies.append(
                _make_anomaly(
                    row,
                    anomaly_type="off_hours",
                    reason=(
                        f"Transaction à {row['timestamp'].strftime('%H:%M')} UTC "
                        f"(hors-heures configurées : {h_start}h–{h_end}h)"
                    ),
                    severity=SEVERITY_LOW,
                    confidence=0.5,
                )
            )
    return anomalies


def _detect_with_isolation_forest(df: pd.DataFrame) -> list[AnomalyDict]:
    """
    Détection ML multivariée via IsolationForest.
    Actif uniquement si ML_ENABLED=true et scikit-learn disponible.
    Features : montant, heure, fréquence utilisateur (normalisées).
    """
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        logger.warning("scikit-learn non disponible — détection ML désactivée")
        return []

    if len(df) < 10:
        return []

    features = pd.DataFrame()
    features["amount"] = df["amount"]

    if not df["timestamp"].isna().all():
        features["hour"]    = df["timestamp"].dt.hour.fillna(12)
        features["weekday"] = df["timestamp"].dt.weekday.fillna(0)
    else:
        features["hour"]    = 12
        features["weekday"] = 0

    user_freq = df["user_id"].map(df["user_id"].value_counts())
    features["user_freq"] = user_freq.fillna(1)

    X = StandardScaler().fit_transform(features.values)

    model = IsolationForest(
        contamination=settings.ML_CONTAMINATION,
        random_state=42,
        n_estimators=100,
    )
    predictions = model.fit_predict(X)
    scores      = model.score_samples(X)           # Plus négatif = plus anormal
    norm_scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)

    anomalies = []
    for idx, (pred, score) in enumerate(zip(predictions, norm_scores)):
        if pred == -1:
            row = df.iloc[idx]
            confidence = float(1.0 - score)
            anomalies.append(
                _make_anomaly(
                    row,
                    anomaly_type="ml_isolation_forest",
                    reason=f"Comportement multivarié anormal détecté par IsolationForest (score={confidence:.2f})",
                    severity=SEVERITY_MEDIUM if confidence < 0.8 else SEVERITY_HIGH,
                    confidence=confidence,
                )
            )
    return anomalies


# ── Déduplication ─────────────────────────────────────────────────────────────

def _deduplicate(anomalies: list[AnomalyDict]) -> list[AnomalyDict]:
    """
    Supprime les doublons : si une transaction est signalée plusieurs fois
    pour le même type, on ne garde que la copie avec le score le plus élevé.
    """
    seen: dict[tuple, AnomalyDict] = {}
    for a in anomalies:
        key = (a["transaction_id"], a["anomaly_type"])
        if key not in seen or a["confidence_score"] > seen[key]["confidence_score"]:
            seen[key] = a
    return list(seen.values())


# ── Score de risque global ────────────────────────────────────────────────────

def compute_risk_score(anomalies: list[AnomalyDict], total_tx: int) -> dict[str, Any]:
    """
    Calcule un score de risque global (0–100) et des statistiques
    de synthèse pour le rapport IA.
    """
    if not anomalies or total_tx == 0:
        return {"score": 0, "level": "FAIBLE", "anomaly_rate": 0.0, "by_type": {}, "by_severity": {}}

    severity_weights = {SEVERITY_HIGH: 3, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 1}
    weighted_sum = sum(
        severity_weights.get(a["severity"], 1) * a["confidence_score"]
        for a in anomalies
    )
    max_possible = len(anomalies) * 3.0
    raw_score = (weighted_sum / max_possible) * 100 if max_possible > 0 else 0

    # Pénalité sur le taux d'anomalies
    rate = len(anomalies) / total_tx
    score = min(100, raw_score * (1 + rate))

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for a in anomalies:
        by_type[a["anomaly_type"]] = by_type.get(a["anomaly_type"], 0) + 1
        by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1

    level = (
        "CRITIQUE" if score >= 75 else
        "ÉLEVÉ"    if score >= 50 else
        "MODÉRÉ"   if score >= 25 else
        "FAIBLE"
    )

    return {
        "score":        round(score, 1),
        "level":        level,
        "anomaly_rate": round(rate * 100, 2),
        "by_type":      by_type,
        "by_severity":  by_severity,
    }


# ── Point d'entrée public ─────────────────────────────────────────────────────

def detect_anomalies(df: pd.DataFrame) -> tuple[list[AnomalyDict], dict[str, Any]]:
    """
    Orchestre toutes les règles de détection et retourne :
      - La liste des anomalies dédupliquées
      - Le score de risque global

    Args:
        df: DataFrame pandas avec les colonnes
            [transaction_id, user_id, amount, timestamp]

    Returns:
        (anomalies, risk_summary)
    """
    # ── Préparation du DataFrame ──────────────────────────────────────────────
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["amount"]    = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    all_anomalies: list[AnomalyDict] = []

    # ── Règles statistiques & métier ──────────────────────────────────────────
    all_anomalies.extend(_detect_unusual_amounts(df))
    all_anomalies.extend(_detect_quasi_round_amounts(df))
    all_anomalies.extend(_detect_high_frequency(df))
    all_anomalies.extend(_detect_off_hours(df))

    # ── Détection ML (optionnelle) ────────────────────────────────────────────
    if settings.ML_ENABLED:
        ml_results = _detect_with_isolation_forest(df)
        logger.info("IsolationForest : %d anomalies détectées", len(ml_results))
        all_anomalies.extend(ml_results)

    # ── Déduplication & tri ───────────────────────────────────────────────────
    anomalies = _deduplicate(all_anomalies)
    anomalies.sort(
        key=lambda a: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(a["severity"], 3),
            -a["confidence_score"],
        )
    )

    # ── Limiter le nombre de résultats ────────────────────────────────────────
    total_found = len(anomalies)
    anomalies = anomalies[: settings.MAX_ANOMALIES_RETURNED]
    if total_found > settings.MAX_ANOMALIES_RETURNED:
        logger.warning(
            "%d anomalies détectées, %d retournées (limite MAX_ANOMALIES_RETURNED=%d)",
            total_found, len(anomalies), settings.MAX_ANOMALIES_RETURNED,
        )

    risk_summary = compute_risk_score(anomalies, len(df))

    logger.info(
        "Analyse terminée : %d transactions, %d anomalies, risque=%s (%.1f/100)",
        len(df), len(anomalies), risk_summary["level"], risk_summary["score"],
    )

    return anomalies, risk_summary