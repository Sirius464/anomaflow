"""Service de génération de rapports avec IA"""
import httpx
import pandas as pd  # IMPORT AJOUTÉ
from typing import List, Dict
from app.config import settings

async def generate_report(anomalies: List[Dict], total_tx: int) -> str:
    if not settings.GROQ_API_KEY:
        return generate_simple_report(anomalies, total_tx)
    
    anomaly_summary = []
    for i, anomaly in enumerate(anomalies[:5], 1):
        anomaly_summary.append(f"{i}. {anomaly['anomaly_type']}, {anomaly['amount']:.2f}€, {anomaly['severity']}")
    
    prompt = f"""Analyse : {total_tx} transactions, {len(anomalies)} anomalies.
Top 5: {chr(10).join(anomaly_summary)}
Génère un rapport en 3 paragraphes (250 mots) : résumé, risques, recommandations."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.GROQ_API_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": settings.GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 800}
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return generate_simple_report(anomalies, total_tx)
    except Exception:
        return generate_simple_report(anomalies, total_tx)

def generate_simple_report(anomalies: List[Dict], total_tx: int) -> str:
    severity_counts = {}
    for a in anomalies:
        severity_counts[a['severity']] = severity_counts.get(a['severity'], 0) + 1
    
    report = f"""📊 RAPPORT - ANOMAFLOW
Total : {total_tx} transactions
Anomalies : {len(anomalies)} ({(len(anomalies)/total_tx*100):.2f}%)

🚨 SÉVÉRITÉ:
"""
    for sev in ['HIGH', 'MEDIUM', 'LOW']:
        if sev in severity_counts:
            report += f"• {sev}: {severity_counts[sev]}\n"
    
    report += "\n💡 Examiner les anomalies HIGH en priorité."
    return report

async def analyze_anomaly_patterns(anomalies: List[Dict], df: pd.DataFrame) -> str:
    """Analyse les motifs d'anomalies avec IA (FONCTION AMÉLIORÉE)"""
    
    if not settings.GROQ_API_KEY or not settings.ML_ENABLED:
        return "🔍 IA non configurée - Activez GROQ_API_KEY dans .env"
    
    # Préparer les données pour l'IA
    stats = {
        "total_transactions": len(df),
        "anomalies_count": len(anomalies),
        "amount_mean": f"{df['amount'].mean():.2f}€",
        "amount_std": f"{df['amount'].std():.2f}€",
        "amount_max": f"{df['amount'].max():.2f}€",
        "top_users": dict(df['user_id'].value_counts().head(3))
    }
    
    # Regrouper par type d'anomalie
    anomaly_types = {}
    for a in anomalies:
        anomaly_types[a['anomaly_type']] = anomaly_types.get(a['anomaly_type'], 0) + 1
    
    prompt = f"""En tant qu'analyste financier expert, analyse ces anomalies transactionnelles :

📈 STATISTIQUES :
- Transactions totales : {stats['total_transactions']}
- Anomalies détectées : {stats['anomalies_count']} ({stats['anomalies_count']/stats['total_transactions']*100:.1f}%)
- Montant moyen : {stats['amount_mean']} (écart : {stats['amount_std']})
- Montant maximum : {stats['amount_max']}
- Top utilisateurs : {stats['top_users']}

🚨 RÉPARTITION DES ANOMALIES :
{chr(10).join([f"- {k}: {v} anomalies" for k, v in anomaly_types.items()])}

🔍 TOP 5 ANOMALIES :
{chr(10).join([f"{i+1}. {a['anomaly_type']} - {a['amount']:.2f}€ - {a['severity']} - {a['reason'][:50]}..." for i, a in enumerate(anomalies[:5])])}

📋 TON ANALYSE DOIT INCLURE :
1. 🎯 TYPE DE RISQUE PRINCIPAL : Quel type de fraude/suspicion est le plus probable ?
2. 📊 NIVEAU DE RISQUE GLOBAL : Sur 10 (10 = critique)
3. ⚡ ACTIONS IMMÉDIATES : 3 actions prioritaires à mener
4. 🔎 POINTS D'INVESTIGATION : Quels éléments approfondir ?
5. 🛡️ RECOMMANDATIONS PRÉVENTIVES : Comment éviter ces anomalies à l'avenir ?

Réponds de manière structurée et concise (max 400 mots)."""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1200
                }
            )
            
            if response.status_code == 200:
                return f"""🤖 ANALYSE IA - ANOMAFLOW

{response.json()["choices"][0]["message"]["content"]}

---
📊 Métriques : {stats['anomalies_count']} anomalies sur {stats['total_transactions']} transactions
🔔 Configurez GROQ_API_KEY dans .env pour des analyses plus détaillées"""
            else:
                return f"❌ Erreur API Groq : {response.status_code}"
                
    except Exception as e:
        return f"⚠️ Erreur de connexion IA : {str(e)[:100]}"
