"""Service de détection d'anomalies"""
import pandas as pd
from typing import List, Dict
from app.config import settings

def detect_anomalies(df: pd.DataFrame) -> List[Dict]:
    anomalies = []
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    mean_amount = df['amount'].mean()
    std_amount = df['amount'].std()
    threshold = mean_amount + (settings.ANOMALY_THRESHOLD_MULTIPLIER * std_amount)
    
    for idx, row in df.iterrows():
        if row['amount'] > threshold:
            anomalies.append({
                'transaction_id': str(row['transaction_id']),
                'user_id': str(row['user_id']),
                'amount': float(row['amount']),
                'timestamp': str(row.get('timestamp', '')),
                'anomaly_type': 'unusual_amount',
                'reason': f"Montant élevé : {row['amount']:.2f}€ (seuil: {threshold:.2f}€)",
                'severity': 'HIGH',
                'confidence_score': min(1.0, (row['amount'] - threshold) / mean_amount)
            })
    
    for idx, row in df.iterrows():
        if row['amount'] in settings.SUSPICIOUS_ROUND_AMOUNTS:
            anomalies.append({
                'transaction_id': str(row['transaction_id']),
                'user_id': str(row['user_id']),
                'amount': float(row['amount']),
                'timestamp': str(row.get('timestamp', '')),
                'anomaly_type': 'round_amount',
                'reason': f"Montant rond suspect : {row['amount']}€",
                'severity': 'MEDIUM',
                'confidence_score': 0.7
            })
    
    user_counts = df['user_id'].value_counts()
    for user_id, count in user_counts.items():
        if count > settings.MAX_TRANSACTIONS_PER_HOUR:
            user_txs = df[df['user_id'] == user_id]
            first_tx = user_txs.iloc[0]
            anomalies.append({
                'transaction_id': str(first_tx['transaction_id']),
                'user_id': str(user_id),
                'amount': float(user_txs['amount'].sum()),
                'timestamp': str(first_tx.get('timestamp', '')),
                'anomaly_type': 'high_frequency',
                'reason': f"Trop de transactions : {count}",
                'severity': 'HIGH',
                'confidence_score': min(1.0, count / settings.MAX_TRANSACTIONS_PER_HOUR)
            })
    
    return anomalies[:50]
