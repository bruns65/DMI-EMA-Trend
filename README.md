# ⚡ FX & Crypto Flow Pro

Une application web de trading quantitative et de scalping haute fréquence, optimisée pour mobile et conçue pour identifier les structures de flux directionnels. L'application implémente la stratégie algorithmique du **Triple Écran** à l'aide de l'ADX (Average Directional Index) et du DMI (Directional Movement Index), adossée à un filtre macro-tendance sous EMA 200.

---

## 🚀 Fonctionnalités Clés

- **Architecture Multi-Source & Résiliente** : Flux de données en temps réel connectés directement aux APIs officielles d'**OKX**, **Bybit** (sans clé API nécessaire) et à un agrégateur interbancaire pour le Forex.
- **Stratégie Triple Écran Strict** : Analyse synchronisée sur trois unités de temps majeures :
  - `1H (Structure)` : Tendance de fond macro et positionnement du prix par rapport à l'**EMA 200**.
  - `15m (Intermédiaire)` : Zone de compression et validation du momentum.
  - `5m (Signal)` : Timing chirurgical et déclenchement d'entrée.
- **Moteur de Gestion du Risque Évolutif** : Calcul automatique et instantané des niveaux de **Take Profit (TP)** et **Stop Loss (SL)** basé sur un ratio Risque/Rendement cible (1:2).
  - Gestion en pourcentage (%) pour les actifs Crypto.
  - Gestion native en **Pips** pour le Forex (incluant la détection automatique des spécificités de l'USD/JPY).
- **Alerte Instantanée Telegram** : Notification automatique sur smartphone lors d'un alignement parfait et simultané des trois écrans de tendance.

---

## 🛠️ Architecture du Projet

Le projet applique le principe de **séparation des préoccupations (Separation of Concerns)** afin de maximiser la résilience face aux pannes d'APIs :

```text
├── app.py          # Interface utilisateur (Streamlit), rendu graphique et logique d'alerte.
├── services.py     # Moteur d'extraction (REST) et calcul algorithmique des indicateurs (DMI/EMA).
├── requirements.txt# Dépendances légères du projet.
└── runtime.txt     # Configuration stricte de l'environnement serveur (Python 3.12.3).
