#!/usr/bin/env python3
"""
AnomaFlow v2.0 — Générateur de CSV de test
==========================================
Produit un fichier CSV réaliste avec des anomalies connues
pour tester et démontrer toutes les règles de détection.

Usage :
    python generate_sample_csv.py
    python generate_sample_csv.py --rows 200 --output my_test.csv --seed 99
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate(rows: int, seed: int, output: Path) -> None:
    random.seed(seed)

    base_time  = datetime(2025, 6, 15, 8, 0, 0)
    users      = [f"CUST_{i:03d}" for i in range(1, 21)]
    normal_amounts = [
        12.50, 23.75, 45.00, 67.20, 89.99, 134.50,
        156.30, 178.90, 210.00, 245.60, 312.40, 389.75,
    ]

    records: list[dict] = []

    # ── Transactions normales ─────────────────────────────────────
    for i in range(rows):
        user = random.choice(users)
        amount = round(random.choice(normal_amounts) + random.uniform(-5, 5), 2)
        ts = base_time + timedelta(hours=i * 0.3, minutes=random.randint(0, 59))
        records.append({
            "transaction_id": f"TX{i+1:05d}",
            "user_id":        user,
            "amount":         amount,
            "timestamp":      ts.strftime("%Y-%m-%d %H:%M:%S"),
            "description":    "Paiement normal",
        })

    # ── Anomalie 1 : montant élevé (unusual_amount) ───────────────
    for j, amount in enumerate([18500.00, 42000.00, 99999.99], start=1):
        ts = base_time + timedelta(hours=rows * 0.3 + j)
        records.append({
            "transaction_id": f"TX_HIGH_{j:02d}",
            "user_id":        f"SUSPECT_{j:02d}",
            "amount":         amount,
            "timestamp":      ts.strftime("%Y-%m-%d %H:%M:%S"),
            "description":    "Virement suspect montant élevé",
        })

    # ── Anomalie 2 : montants quasi-ronds (round_amount) ──────────
    quasi_rounds = [
        (499.99, "CUST_007"), (1000.01, "CUST_012"),
        (500.00, "CUST_003"), (999.98, "CUST_018"),
        (4999.95, "CUST_005"),
    ]
    for j, (amount, user) in enumerate(quasi_rounds, start=1):
        ts = base_time + timedelta(hours=rows * 0.3 + 10 + j)
        records.append({
            "transaction_id": f"TX_ROUND_{j:02d}",
            "user_id":        user,
            "amount":         amount,
            "timestamp":      ts.strftime("%Y-%m-%d %H:%M:%S"),
            "description":    "Montant proche d'un seuil rond",
        })

    # ── Anomalie 3 : haute fréquence (high_frequency) ─────────────
    freq_start = base_time + timedelta(hours=rows * 0.3 + 20)
    for j in range(15):  # 15 transactions en 50 minutes → dépasse MAX_TX_PER_HOUR=10
        ts = freq_start + timedelta(minutes=j * 3, seconds=random.randint(0, 59))
        records.append({
            "transaction_id": f"TX_FREQ_{j+1:02d}",
            "user_id":        "FRAUD_FREQ",
            "amount":         round(random.uniform(10, 50), 2),
            "timestamp":      ts.strftime("%Y-%m-%d %H:%M:%S"),
            "description":    "Transaction fréquente suspecte",
        })

    # ── Anomalie 4 : hors-heures (off_hours) ──────────────────────
    off_hours_times = ["2025-06-16 02:15:00", "2025-06-16 23:45:00", "2025-06-17 03:30:00"]
    for j, ts_str in enumerate(off_hours_times, start=1):
        records.append({
            "transaction_id": f"TX_NIGHT_{j:02d}",
            "user_id":        f"CUST_{j*3:03d}",
            "amount":         round(random.uniform(200, 800), 2),
            "timestamp":      ts_str,
            "description":    "Transaction nocturne suspecte",
        })

    # ── Mélanger (sauf header) ────────────────────────────────────
    random.shuffle(records)

    # ── Écriture CSV ──────────────────────────────────────────────
    headers = ["transaction_id", "user_id", "amount", "timestamp", "description"]
    lines   = [",".join(headers)]
    for r in records:
        lines.append(",".join(str(r[h]) for h in headers))

    output.write_text("\n".join(lines), encoding="utf-8")

    # ── Résumé ────────────────────────────────────────────────────
    total = len(records)
    injected = total - rows
    print(f"\n✅ CSV généré : {output}")
    print(f"   Total lignes    : {total}")
    print(f"   Normales        : {rows}")
    print(f"   Anomalies injec.: {injected}")
    print(f"     - unusual_amount  : 3  (TX_HIGH_*)")
    print(f"     - round_amount    : 5  (TX_ROUND_*)")
    print(f"     - high_frequency  : 15 (TX_FREQ_* — user FRAUD_FREQ)")
    print(f"     - off_hours       : 3  (TX_NIGHT_*)")
    print(f"\nTestez avec :")
    print(f"  curl -X POST http://localhost:8000/upload \\")
    print(f"    -H 'Authorization: Bearer <TOKEN>' \\")
    print(f"    -F 'file=@{output}'\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Générateur de CSV de test AnomaFlow")
    parser.add_argument("--rows",   type=int,   default=80,                    help="Nombre de transactions normales (défaut: 80)")
    parser.add_argument("--output", type=str,   default="sample_transactions.csv", help="Fichier de sortie")
    parser.add_argument("--seed",   type=int,   default=42,                    help="Graine aléatoire pour reproductibilité")
    args = parser.parse_args()

    generate(rows=args.rows, seed=args.seed, output=Path(args.output))


if __name__ == "__main__":
    main()
