# Satellite Timeline Viewer

Une application Streamlit personnelle pour choisir n’importe quel endroit sur une carte mondiale, récupérer les acquisitions publiques Sentinel-2 disponibles et les parcourir avec un curseur temporel.

## Fonctionnement

1. Cliquez sur la carte pour placer le centre de la zone.
2. Choisissez une emprise de 1 à 30 km, une période et une limite de nébulosité.
3. Cliquez sur **Charger les photos de cette zone**.
4. Déplacez le curseur temporel pour parcourir les images ; il s’ouvre sur la plus récente.

Les données proviennent de Sentinel-2 L2A via le catalogue public Earth Search d’Element 84 et les COG AWS Open Data. Aucune clé API n’est nécessaire.

## Installation

```powershell
cd C:\Users\matth\Business\satellite-timeline-viewer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8502
```

Puis ouvrir <http://localhost:8502>.

## Tests

```powershell
python -m pytest -q
```

## Limites

- La nébulosité du catalogue concerne la tuile Sentinel-2 entière, pas uniquement la zone affichée.
- Sentinel-2 fournit une résolution de 10 m en couleur naturelle, pas une photographie à très haute résolution.
- Une acquisition peut être partiellement nuageuse même si elle respecte le seuil choisi.
- La recherche est limitée à 200 résultats, ce qui couvre normalement les deux années proposées pour un point.
- La carte de sélection utilise les tuiles OpenStreetMap et nécessite également une connexion internet.
