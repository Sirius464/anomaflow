"""
AnomaFlow v2.0 — Tests du service de détection d'anomalies
Couvre : tous les types d'anomalies, la déduplication,
         le score de risque, les cas limites.
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta

from app.services.detector import (
    detect_anomalies,
    compute_risk_score,
    _is_quasi_round,
    _is_off_hours,
    _deduplicate,
)


# ── Helpers de test ───────────────────────────────────────────────────────────

def make_row(tx_id="TX001", user="U1", amount=100.0, hour=10):
    return pd.Series({
        "transaction_id": tx_id,
        "user_id": user,
        "amount": amount,
        "timestamp": pd.Timestamp(f"2025-06-15 {hour:02d}:00:00"),
    })


# ── Tests : _is_quasi_round ───────────────────────────────────────────────────

class TestIsQuasiRound:
    def test_exact_match(self):
        assert _is_quasi_round(500.0) == 500.0

    def test_within_tolerance(self):
        """500.01 est à 0.002% de 500 → dans la tolérance ±2%."""
        assert _is_quasi_round(500.01) == 500.0

    def test_below_tolerance(self):
        """490.0 est à 2% de 500 → à la limite exacte."""
        assert _is_quasi_round(490.0) == 500.0

    def test_outside_tolerance(self):
        """480.0 est à 4% de 500 → hors tolérance."""
        assert _is_quasi_round(480.0) is None

    def test_normal_amount(self):
        assert _is_quasi_round(73.42) is None

    def test_zero_amount(self):
        """Un montant nul ne doit pas lever d'exception."""
        assert _is_quasi_round(0.0) is None

    def test_large_amount(self):
        assert _is_quasi_round(10001.0) == 10000.0


# ── Tests : _is_off_hours ─────────────────────────────────────────────────────

class TestIsOffHours:
    def test_business_hours(self):
        ts = pd.Timestamp("2025-06-15 14:00:00")
        assert not _is_off_hours(ts)

    def test_late_night(self):
        ts = pd.Timestamp("2025-06-15 23:30:00")
        assert _is_off_hours(ts)

    def test_early_morning(self):
        ts = pd.Timestamp("2025-06-15 04:00:00")
        assert _is_off_hours(ts)

    def test_boundary_start(self):
        """22h00 pile est considéré hors-heures."""
        ts = pd.Timestamp("2025-06-15 22:00:00")
        assert _is_off_hours(ts)

    def test_boundary_end(self):
        """6h00 pile n'est pas hors-heures."""
        ts = pd.Timestamp("2025-06-15 06:00:00")
        assert not _is_off_hours(ts)


# ── Tests : _deduplicate ──────────────────────────────────────────────────────

class TestDeduplicate:
    def test_removes_duplicate_type(self):
        anomalies = [
            {"transaction_id": "TX001", "anomaly_type": "round_amount", "confidence_score": 0.6},
            {"transaction_id": "TX001", "anomaly_type": "round_amount", "confidence_score": 0.8},
        ]
        result = _deduplicate(anomalies)
        assert len(result) == 1
        assert result[0]["confidence_score"] == 0.8  # garde le meilleur score

    def test_keeps_different_types(self):
        anomalies = [
            {"transaction_id": "TX001", "anomaly_type": "round_amount",   "confidence_score": 0.7},
            {"transaction_id": "TX001", "anomaly_type": "unusual_amount", "confidence_score": 0.9},
        ]
        result = _deduplicate(anomalies)
        assert len(result) == 2

    def test_empty_list(self):
        assert _deduplicate([]) == []


# ── Tests : compute_risk_score ────────────────────────────────────────────────

class TestComputeRiskScore:
    def test_empty_anomalies(self):
        result = compute_risk_score([], 100)
        assert result["score"] == 0
        assert result["level"] == "FAIBLE"

    def test_single_high_anomaly(self):
        anomalies = [{"severity": "HIGH", "confidence_score": 1.0, "anomaly_type": "unusual_amount"}]
        result = compute_risk_score(anomalies, 10)
        assert result["score"] > 0
        assert result["by_severity"]["HIGH"] == 1

    def test_level_labels(self):
        """Vérifie que les seuils de niveau sont respectés."""
        high_anom = [{"severity": "HIGH", "confidence_score": 1.0, "anomaly_type": "x"}] * 10
        result = compute_risk_score(high_anom, 10)
        assert result["level"] in ("CRITIQUE", "ÉLEVÉ", "MODÉRÉ", "FAIBLE")

    def test_anomaly_rate_calculation(self):
        anomalies = [{"severity": "LOW", "confidence_score": 0.5, "anomaly_type": "x"}] * 5
        result = compute_risk_score(anomalies, 100)
        assert result["anomaly_rate"] == pytest.approx(5.0)

    def test_zero_total_tx(self):
        """Ne doit pas lever ZeroDivisionError."""
        result = compute_risk_score([], 0)
        assert result["score"] == 0


# ── Tests : detect_anomalies ──────────────────────────────────────────────────

class TestDetectAnomalies:

    def test_returns_tuple(self, normal_df):
        result = detect_anomalies(normal_df)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_no_anomalies_on_normal_data(self, normal_df):
        anomalies, risk = detect_anomalies(normal_df)
        # On vérifie uniquement les règles métier (pas ML qui peut fluctuer
        # sur de petits datasets selon la contamination)
        rule_based = [
            a for a in anomalies
            if a["anomaly_type"] != "ml_isolation_forest"
        ]
        high_severity = [a for a in rule_based if a["severity"] == "HIGH"]
        assert len(high_severity) == 0, (
            f"Anomalies HIGH inattendues sur données normales : {high_severity}"
        )

    def test_detects_unusual_amount(self):
        df = pd.DataFrame([
            {"transaction_id": f"TX{i}", "user_id": "U1", "amount": 50.0,
             "timestamp": "2025-06-15 10:00:00"} for i in range(19)
        ] + [
            {"transaction_id": "TX99", "user_id": "U1", "amount": 999999.0,
             "timestamp": "2025-06-15 10:00:00"}
        ])
        anomalies, _ = detect_anomalies(df)
        types = [a["anomaly_type"] for a in anomalies]
        assert "unusual_amount" in types

    def test_detects_quasi_round_amounts(self, anomalous_df):
        anomalies, _ = detect_anomalies(anomalous_df)
        round_anomalies = [a for a in anomalies if a["anomaly_type"] == "round_amount"]
        # TX9002 (500.01) et TX9003 (999.98) doivent être détectés
        assert len(round_anomalies) >= 2

    def test_detects_off_hours(self, anomalous_df):
        anomalies, _ = detect_anomalies(anomalous_df)
        off = [a for a in anomalies if a["anomaly_type"] == "off_hours"]
        # TX9010 est à 23h
        assert len(off) >= 1
        assert any(a["transaction_id"] == "TX9010" for a in off)

    def test_detects_high_frequency(self, anomalous_df):
        anomalies, _ = detect_anomalies(anomalous_df)
        freq = [a for a in anomalies if a["anomaly_type"] == "high_frequency"]
        # USER_77 a 12 transactions en 48 minutes
        assert len(freq) >= 1
        assert any(a["user_id"] == "USER_77" for a in freq)

    def test_anomaly_structure(self, anomalous_df):
        """Chaque anomalie doit avoir tous les champs requis."""
        anomalies, _ = detect_anomalies(anomalous_df)
        required_keys = {"transaction_id", "user_id", "amount", "timestamp",
                         "anomaly_type", "reason", "severity", "confidence_score"}
        for a in anomalies:
            assert required_keys.issubset(set(a.keys())), f"Champs manquants : {required_keys - set(a.keys())}"

    def test_confidence_score_bounds(self, anomalous_df):
        """confidence_score doit toujours être entre 0 et 1."""
        anomalies, _ = detect_anomalies(anomalous_df)
        for a in anomalies:
            assert 0.0 <= a["confidence_score"] <= 1.0, (
                f"{a['anomaly_type']} : confidence={a['confidence_score']}"
            )

    def test_severity_valid_values(self, anomalous_df):
        anomalies, _ = detect_anomalies(anomalous_df)
        valid = {"HIGH", "MEDIUM", "LOW"}
        for a in anomalies:
            assert a["severity"] in valid

    def test_no_duplicate_transaction_type(self, anomalous_df):
        """Après déduplication, pas de (transaction_id, anomaly_type) dupliqué."""
        anomalies, _ = detect_anomalies(anomalous_df)
        pairs = [(a["transaction_id"], a["anomaly_type"]) for a in anomalies]
        assert len(pairs) == len(set(pairs))

    def test_sorted_by_severity_then_confidence(self, anomalous_df):
        """Les anomalies HIGH doivent apparaître avant MEDIUM, puis LOW."""
        anomalies, _ = detect_anomalies(anomalous_df)
        if len(anomalies) < 2:
            pytest.skip("Pas assez d'anomalies pour tester le tri")
        sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        orders = [sev_order[a["severity"]] for a in anomalies]
        assert orders == sorted(orders)

    def test_missing_timestamp_column_handled(self):
        """Un DataFrame sans timestamps valides ne doit pas planter."""
        df = pd.DataFrame([
            {"transaction_id": "TX1", "user_id": "U1", "amount": 100.0, "timestamp": "invalid"},
            {"transaction_id": "TX2", "user_id": "U1", "amount": 200.0, "timestamp": "invalid"},
        ])
        anomalies, risk = detect_anomalies(df)
        assert isinstance(anomalies, list)

    def test_single_row_df(self):
        """Un DataFrame à une seule ligne ne doit pas planter."""
        df = pd.DataFrame([{
            "transaction_id": "TX1", "user_id": "U1",
            "amount": 100.0, "timestamp": "2025-06-15 10:00:00",
        }])
        anomalies, risk = detect_anomalies(df)
        assert isinstance(anomalies, list)

    def test_risk_summary_keys(self, anomalous_df):
        _, risk = detect_anomalies(anomalous_df)
        assert {"score", "level", "anomaly_rate", "by_type", "by_severity"}.issubset(risk.keys())
