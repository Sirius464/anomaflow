#!/usr/bin/env python3
"""
AnomaFlow — Script de migration v1 → v2
========================================
Ce script migre la base de données SQLite existante vers le schéma v2.

Changements de schéma appliqués :
  1. Anomaly.timestamp (String) → Anomaly.transaction_at (DateTime)
  2. Ajout des colonnes manquantes avec valeurs par défaut
  3. Ajout des index de performance
  4. Mise à jour de la version du schéma

Usage :
    python migrate_v1_to_v2.py [--db-path ./anomaflow.db] [--dry-run]

Sécurité :
    - Une sauvegarde automatique est créée avant toute modification
    - Le mode --dry-run permet de prévisualiser sans rien écrire
    - Chaque étape est journalisée et réversible via la sauvegarde
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ── Couleurs terminal ─────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
MUTED  = "\033[90m"

def ok(msg: str)   -> None: print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg: str) -> None: print(f"  {YELLOW}⚠{RESET}  {msg}")
def err(msg: str)  -> None: print(f"  {RED}✗{RESET} {msg}", file=sys.stderr)
def info(msg: str) -> None: print(f"  {CYAN}→{RESET} {msg}")
def skip(msg: str) -> None: print(f"  {MUTED}–{RESET} {msg} {MUTED}(déjà à jour){RESET}")


# ── Helpers SQLite ────────────────────────────────────────────────────────────

def column_exists(con: sqlite3.Connection, table: str, column: str) -> bool:
    cur = con.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def index_exists(con: sqlite3.Connection, index_name: str) -> bool:
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cur.fetchone() is not None


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def get_row_count(con: sqlite3.Connection, table: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ── Étapes de migration ───────────────────────────────────────────────────────

def step_backup(db_path: Path, dry_run: bool) -> Path:
    """Créer une sauvegarde horodatée de la base de données."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.parent / f"{db_path.stem}_v1_backup_{ts}{db_path.suffix}"
    if dry_run:
        info(f"[DRY-RUN] Sauvegarderait vers {backup}")
    else:
        shutil.copy2(db_path, backup)
        ok(f"Sauvegarde créée : {backup}")
    return backup


def step_rename_timestamp_column(con: sqlite3.Connection, dry_run: bool) -> None:
    """
    Migre Anomaly.timestamp (String) → Anomaly.transaction_at (DateTime).
    SQLite < 3.25 ne supporte pas RENAME COLUMN, on recrée la table.
    """
    if not table_exists(con, "anomalies"):
        skip("Table 'anomalies' introuvable")
        return

    if column_exists(con, "anomalies", "transaction_at"):
        skip("Colonne 'transaction_at' déjà présente")
        return

    if dry_run:
        info("[DRY-RUN] Renommerait 'timestamp' → 'transaction_at' dans anomalies")
        return

    info("Migration de 'anomalies.timestamp' → 'anomalies.transaction_at'…")

    # Vérifier si RENAME COLUMN est disponible (SQLite ≥ 3.25)
    sqlite_version = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if sqlite_version >= (3, 25, 0):
        # Méthode rapide
        con.execute("ALTER TABLE anomalies RENAME COLUMN timestamp TO transaction_at")
        ok("Colonne renommée via RENAME COLUMN")
    else:
        # Méthode de reconstruction (SQLite < 3.25)
        warn(f"SQLite {sqlite3.sqlite_version} < 3.25 — reconstruction de la table…")
        _rebuild_anomalies_table(con)
        ok("Table 'anomalies' reconstruite avec 'transaction_at'")


def _rebuild_anomalies_table(con: sqlite3.Connection) -> None:
    """Reconstruit la table anomalies avec le nouveau schéma."""
    con.executescript("""
        BEGIN;

        CREATE TABLE anomalies_v2 (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id           INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
            transaction_id      TEXT    NOT NULL,
            user_id_transaction TEXT    NOT NULL,
            amount              REAL    NOT NULL,
            transaction_at      TEXT,               -- sera converti en DateTime par SQLAlchemy
            anomaly_type        TEXT    NOT NULL,
            reason              TEXT    NOT NULL,
            severity            TEXT    NOT NULL,
            confidence_score    REAL    NOT NULL DEFAULT 0.0,
            detected_at         TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        INSERT INTO anomalies_v2 (
            id, upload_id, transaction_id, user_id_transaction,
            amount, transaction_at, anomaly_type, reason,
            severity, confidence_score, detected_at
        )
        SELECT
            id, upload_id, transaction_id, user_id_transaction,
            amount, timestamp, anomaly_type, reason,
            severity, confidence_score, detected_at
        FROM anomalies;

        DROP TABLE anomalies;
        ALTER TABLE anomalies_v2 RENAME TO anomalies;

        COMMIT;
    """)


def step_add_missing_columns(con: sqlite3.Connection, dry_run: bool) -> None:
    """Ajoute les colonnes introduites en v2 si elles manquent."""
    additions = [
        ("users",   "updated_at",  "TEXT DEFAULT NULL"),
        ("uploads", "file_size",   "INTEGER DEFAULT 0"),
    ]

    for table, col, definition in additions:
        if not table_exists(con, table):
            skip(f"Table '{table}' introuvable")
            continue
        if column_exists(con, table, col):
            skip(f"{table}.{col}")
            continue
        if dry_run:
            info(f"[DRY-RUN] Ajouterait {table}.{col}")
        else:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            ok(f"Colonne ajoutée : {table}.{col}")


def step_add_indexes(con: sqlite3.Connection, dry_run: bool) -> None:
    """Crée les index de performance v2."""
    indexes = [
        ("ix_uploads_user_date",     "CREATE INDEX IF NOT EXISTS ix_uploads_user_date ON uploads(user_id, upload_date)"),
        ("ix_anomalies_severity",    "CREATE INDEX IF NOT EXISTS ix_anomalies_severity ON anomalies(severity)"),
        ("ix_anomalies_type",        "CREATE INDEX IF NOT EXISTS ix_anomalies_type ON anomalies(anomaly_type)"),
        ("ix_anomalies_user_tx",     "CREATE INDEX IF NOT EXISTS ix_anomalies_user_tx ON anomalies(user_id_transaction)"),
    ]

    for name, sql in indexes:
        if index_exists(con, name):
            skip(f"Index '{name}'")
            continue
        if dry_run:
            info(f"[DRY-RUN] Créerait index '{name}'")
        else:
            con.execute(sql)
            ok(f"Index créé : {name}")


def step_validate_data(con: sqlite3.Connection) -> bool:
    """Vérifie l'intégrité des données après migration."""
    passed = True

    checks = [
        ("users",     "SELECT COUNT(*) FROM users"),
        ("uploads",   "SELECT COUNT(*) FROM uploads"),
        ("anomalies", "SELECT COUNT(*) FROM anomalies"),
    ]

    for label, query in checks:
        try:
            count = con.execute(query).fetchone()[0]
            ok(f"Intégrité {label} : {count} enregistrement(s)")
        except Exception as exc:
            err(f"Échec validation {label} : {exc}")
            passed = False

    # Vérifier référentiels
    try:
        orphans = con.execute(
            "SELECT COUNT(*) FROM anomalies a LEFT JOIN uploads u ON a.upload_id = u.id WHERE u.id IS NULL"
        ).fetchone()[0]
        if orphans > 0:
            warn(f"{orphans} anomalie(s) orpheline(s) détectée(s) (upload_id inexistant)")
        else:
            ok("Intégrité référentielle anomalies→uploads : OK")
    except Exception as exc:
        warn(f"Vérification référentielle impossible : {exc}")

    return passed


def step_record_migration(con: sqlite3.Connection, dry_run: bool) -> None:
    """Crée une table de versioning de schéma et enregistre la migration."""
    if dry_run:
        info("[DRY-RUN] Enregistrerait la migration dans schema_versions")
        return

    con.execute("""
        CREATE TABLE IF NOT EXISTS schema_versions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            version    TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            description TEXT
        )
    """)

    # Éviter les doublons
    existing = con.execute(
        "SELECT id FROM schema_versions WHERE version = 'v2.0.0'"
    ).fetchone()

    if not existing:
        con.execute(
            "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
            ("v2.0.0", "Migration v1→v2 : transaction_at, index, colonnes optionnelles")
        )
        ok("Version 'v2.0.0' enregistrée dans schema_versions")
    else:
        skip("Version 'v2.0.0' déjà enregistrée")


# ── Rapport final ─────────────────────────────────────────────────────────────

def print_summary(db_path: Path, con: sqlite3.Connection) -> None:
    print(f"\n{BOLD}{CYAN}─── Résumé post-migration ───────────────────────────────{RESET}")
    for table in ("users", "uploads", "anomalies"):
        if table_exists(con, table):
            count = get_row_count(con, table)
            print(f"  {MUTED}{table:<12}{RESET} {count:>6} lignes")

    versions = con.execute(
        "SELECT version, applied_at FROM schema_versions ORDER BY id"
    ).fetchall() if table_exists(con, "schema_versions") else []
    if versions:
        print(f"\n{BOLD}Versions de schéma appliquées :{RESET}")
        for v, ts in versions:
            print(f"  {GREEN}✓{RESET} {v}  {MUTED}({ts}){RESET}")
    print()


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migration de la base de données AnomaFlow v1 → v2"
    )
    parser.add_argument("--db-path",  default="./anomaflow.db", help="Chemin vers la base de données SQLite")
    parser.add_argument("--dry-run",  action="store_true",       help="Prévisualiser sans modifier")
    parser.add_argument("--no-backup",action="store_true",       help="Ne pas créer de sauvegarde (dangereux)")
    args = parser.parse_args()

    db_path = Path(args.db_path)

    print(f"\n{BOLD}╔══════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║  AnomaFlow — Migration v1 → v2               ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════╝{RESET}\n")

    # ── Vérifications préalables ─────────────────────────────────────────────
    if not db_path.exists():
        err(f"Base de données introuvable : {db_path}")
        err("Vérifiez le chemin avec --db-path")
        sys.exit(1)

    info(f"Base de données : {db_path.resolve()}")
    info(f"Mode            : {'DRY-RUN (aucune modification)' if args.dry_run else 'MIGRATION RÉELLE'}")
    info(f"SQLite version  : {sqlite3.sqlite_version}\n")

    if args.dry_run:
        print(f"{YELLOW}Mode DRY-RUN activé — aucune modification ne sera appliquée.{RESET}\n")

    # ── Sauvegarde ───────────────────────────────────────────────────────────
    print(f"{BOLD}Étape 1 — Sauvegarde{RESET}")
    if not args.no_backup:
        backup = step_backup(db_path, args.dry_run)
    else:
        warn("Sauvegarde désactivée via --no-backup")

    # ── Migration ────────────────────────────────────────────────────────────
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")

    try:
        print(f"\n{BOLD}Étape 2 — Colonnes{RESET}")
        step_rename_timestamp_column(con, args.dry_run)
        step_add_missing_columns(con, args.dry_run)

        print(f"\n{BOLD}Étape 3 — Index{RESET}")
        step_add_indexes(con, args.dry_run)

        print(f"\n{BOLD}Étape 4 — Versioning{RESET}")
        step_record_migration(con, args.dry_run)

        if not args.dry_run:
            con.commit()

        print(f"\n{BOLD}Étape 5 — Validation{RESET}")
        if not args.dry_run:
            ok_data = step_validate_data(con)
            if not ok_data:
                raise RuntimeError("Validation des données échouée — restaurez depuis la sauvegarde")
        else:
            skip("Validation ignorée en mode DRY-RUN")

        if not args.dry_run:
            print_summary(db_path, con)
            print(f"{BOLD}{GREEN}✓ Migration v2.0 terminée avec succès.{RESET}\n")
        else:
            print(f"\n{BOLD}{YELLOW}⚠  DRY-RUN terminé — aucune modification appliquée.{RESET}")
            print(f"   Relancez sans --dry-run pour appliquer la migration.\n")

    except Exception as exc:
        if not args.dry_run:
            con.rollback()
        err(f"Migration échouée : {exc}")
        if not args.no_backup:
            err(f"Restaurez depuis la sauvegarde et signalez ce bug.")
        con.close()
        sys.exit(1)

    con.close()


if __name__ == "__main__":
    main()
