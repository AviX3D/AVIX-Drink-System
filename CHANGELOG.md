# Changelog

## v4.0.0
- Logo AVIX et polices dans le style du logo (Barlow Condensed extra-grasse italique, embarquée).
- Interface entièrement refaite : tableau de bord clair, gros STOP toujours visible.
- **Tuto de démarrage** pas à pas (au premier lancement, relançable depuis le menu).
- **Détection automatique de la box** par échange avec le firmware, et reconnexion toute seule après un débranchement. Plus besoin de choisir un port COM.
- **Instance unique** : relancer l'appli ramène la fenêtre déjà ouverte.
- Volants, button boxes et manettes pris en compte **même quand le jeu est au premier plan**. Le bon périphérique est retenu, même si tu en as plusieurs.
- Touche clavier reconnue par sa position physique (AZERTY + Maj OK). Le hook clavier n'est posé que s'il sert.
- Bouton du capot affiché dans l'appli, débit réglable, amorçage (pompe tant qu'on maintient), purge avec temps d'attente.
- Hydratation : calibration en ml, compteur de la session et du jour, rappel « pense à boire ».
- Sécurités : pompe coupée à la connexion, à la déconnexion et à la fermeture, coupure à 20 s, gestion du redémarrage de la box.
- Diagnostic copiable pour le support, journal sur disque, réglages enregistrés sans risque de corruption (reprise des réglages de la v3).
- Correctif : la v3 communiquait à 115200 bauds alors que la doc indiquait 9600. Le firmware V2 est fourni dans `firmware/`.
