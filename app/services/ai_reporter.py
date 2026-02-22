"""
AnomaFlow v2.0 — Service de génération de rapports IA
Corrections & améliorations v2 :
  - analyze_anomaly_patterns() est maintenant la fonction principale
  - Modèle centralisé via settings.GROQ_MODEL (plus de hardcode)
  - Retry avec backoff exponentiel sur erreur 429 / 5xx
  - Fallback dégradé détaillé si l'IA est indisponible
  - Score de risque intégré dans le prompt
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_prompt(
    anomalies: list[dict],
    total_tx: int,
    risk_summary: dict[str, Any],
) -> str:
    """Construit le prompt enrichi pour l'analyse IA."""

    by_type_lines = "\n".join(
        f"  - {k}: {v} cas" for k, v in risk_summary.get("by_type", {}).items()
    )
    by_sev_lines = "\n".join(
        f"  - {k}: {v}" for k, v in risk_summary.get("by_severity", {}).items()
    )
    top5_lines = "\n".join(
        f"  {i+1}. [{a['severity']}] {a['anomaly_type']} — "
        f"{a['amount']:.2f}€ (confiance {a['confidence_score']:.0%}) — {a['reason'][:80]}"
        for i, a in enumerate(anomalies[:5])
    )

    return f"""Tu es un expert senior en détection de fraude et en conformité financière (AML/KYC).

═══════════════════════════════════════════════════════
📊 CONTEXTE DU FICHIER ANALYSÉ
═══════════════════════════════════════════════════════
• Transactions totales  : {total_tx}
• Anomalies détectées   : {len(anomalies)} ({risk_summary.get('anomaly_rate', 0):.1f}%)
• Score de risque global: {risk_summary.get('score', 0):.1f}/100 — Niveau {risk_summary.get('level', 'N/A')}

📂 RÉPARTITION PAR TYPE D'ANOMALIE :
{by_type_lines or '  (aucune)'}

⚠️  RÉPARTITION PAR SÉVÉRITÉ :
{by_sev_lines or '  (aucune)'}

🔍 TOP 5 ANOMALIES LES PLUS CRITIQUES :
{top5_lines or '  (aucune anomalie)'}

═══════════════════════════════════════════════════════
📋 TON RAPPORT DOIT COUVRIR (max 450 mots, format structuré) :
═══════════════════════════════════════════════════════
1. 🎯 TYPE DE RISQUE PRINCIPAL — Quel schéma de fraude ou irrégularité est le plus probable ?
2. 📊 ÉVALUATION GLOBALE — Justifie le niveau de risque {risk_summary.get('level', '')} observé
3. ⚡ ACTIONS IMMÉDIATES — 3 mesures prioritaires à appliquer dans les 24h
4. 🔎 INVESTIGATIONS COMPLÉMENTAIRES — Quels patterns creuser davantage ?
5. 🛡️  RECOMMANDATIONS PRÉVENTIVES — Comment renforcer les contrôles à long terme ?

Sois précis, actionnable et concis. Évite le jargon générique."""


async def _call_groq(prompt: str) -> str | None:
    """
    Appelle l'API Groq avec retry + backoff exponentiel.
    Retourne le texte généré ou None en cas d'échec définitif.
    """
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings.GROQ_TEMPERATURE,
        "max_tokens": settings.GROQ_MAX_TOKENS,
    }

    for attempt in range(1, settings.GROQ_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.GROQ_TIMEOUT) as client:
                response = await client.post(settings.GROQ_API_URL, headers=headers, json=payload)

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]

            if response.status_code == 429:
                wait = 2 ** attempt
                logger.warning("Groq rate limit — retry %d/%d dans %ds", attempt, settings.GROQ_MAX_RETRIES, wait)
                await asyncio.sleep(wait)
                continue

            if response.status_code >= 500:
                wait = 2 ** attempt
                logger.warning("Groq erreur serveur %d — retry %d/%d dans %ds", response.status_code, attempt, settings.GROQ_MAX_RETRIES, wait)
                await asyncio.sleep(wait)
                continue

            logger.error("Groq erreur inattendue %d : %s", response.status_code, response.text[:200])
            return None

        except httpx.TimeoutException:
            logger.warning("Groq timeout (tentative %d/%d)", attempt, settings.GROQ_MAX_RETRIES)
            await asyncio.sleep(2 ** attempt)
        except Exception as exc:
            logger.error("Erreur connexion Groq : %s", exc)
            return None

    return None


def _fallback_report(
    anomalies: list[dict],
    total_tx: int,
    risk_summary: dict[str, Any],
) -> str:
    """Rapport de secours détaillé généré sans IA."""
    sev = risk_summary.get("by_severity", {})
    types = risk_summary.get("by_type", {})
    rate = risk_summary.get("anomaly_rate", 0)
    score = risk_summary.get("score", 0)
    level = risk_summary.get("level", "N/A")

    top_anomalies_block = ""
    for i, a in enumerate(anomalies[:5], 1):
        top_anomalies_block += (
            f"  {i}. [{a['severity']}] {a['anomaly_type'].upper()} — "
            f"{a['amount']:.2f}€\n"
            f"     ↳ {a['reason']}\n"
        )

    types_block = "\n".join(f"  • {k}: {v}" for k, v in types.items()) or "  • Aucune"

    return f"""📊 RAPPORT ANOMAFLOW v2 — MODE DÉGRADÉ (IA non disponible)
{'═' * 55}

📈 STATISTIQUES GÉNÉRALES
  Transactions analysées : {total_tx}
  Anomalies détectées    : {len(anomalies)} ({rate:.1f}%)
  Score de risque        : {score:.1f}/100 — Niveau {level}

⚠️  SÉVÉRITÉ DES ANOMALIES
  🔴 HIGH   : {sev.get('HIGH', 0)}
  🟠 MEDIUM : {sev.get('MEDIUM', 0)}
  🟡 LOW    : {sev.get('LOW', 0)}

📂 RÉPARTITION PAR TYPE
{types_block}

🔍 TOP 5 ANOMALIES CRITIQUES
{top_anomalies_block or '  Aucune anomalie critique'}
💡 RECOMMANDATIONS AUTOMATIQUES
  1. Examiner en priorité les {sev.get('HIGH', 0)} anomalie(s) HIGH
  2. Vérifier manuellement les montants quasi-ronds répétés
  3. Activer GROQ_API_KEY dans .env pour des analyses IA approfondies

{'═' * 55}
⚙️  Configurez GROQ_API_KEY dans .env pour activer l'analyse IA complète"""


# ── API publique ──────────────────────────────────────────────────────────────

async def generate_report(
    anomalies: list[dict],
    total_tx: int,
    risk_summary: dict[str, Any] | None = None,
) -> str:
    """
    Point d'entrée principal.
    Génère un rapport IA détaillé ou un rapport dégradé si l'IA est
    indisponible.

    Args:
        anomalies:    Liste des anomalies détectées
        total_tx:     Nombre total de transactions analysées
        risk_summary: Dictionnaire de score de risque (compute_risk_score)

    Returns:
        Rapport textuel formaté
    """
    if risk_summary is None:
        risk_summary = {
            "score": 0, "level": "N/A",
            "anomaly_rate": (len(anomalies) / total_tx * 100) if total_tx else 0,
            "by_type": {}, "by_severity": {},
        }

    if not settings.GROQ_API_KEY:
        logger.info("GROQ_API_KEY absente — rapport dégradé")
        return _fallback_report(anomalies, total_tx, risk_summary)

    prompt = _build_prompt(anomalies, total_tx, risk_summary)
    ai_text = await _call_groq(prompt)

    if ai_text:
        return (
            f"🤖 RAPPORT IA — ANOMAFLOW v2 | Modèle : {settings.GROQ_MODEL}\n"
            f"{'═' * 60}\n\n"
            f"{ai_text}\n\n"
            f"{'─' * 60}\n"
            f"📊 {len(anomalies)} anomalies / {total_tx} transactions "
            f"| Risque : {risk_summary['level']} ({risk_summary['score']:.1f}/100)"
        )

    logger.warning("Toutes les tentatives Groq ont échoué — rapport dégradé")
    return _fallback_report(anomalies, total_tx, risk_summary)