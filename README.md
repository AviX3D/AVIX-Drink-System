# AVIX Drink System — Controller

Application Windows native pour piloter une pompe de boisson depuis un volant de simracing (Arduino Nano).

---

## Installer l'application

1. Va dans l'onglet **[Releases](../../releases)** de ce repo (à droite sur GitHub)
2. Télécharge le fichier `.exe` de la dernière version
3. Lance-le — rien d'autre à installer
4. L'appli te préviendra automatiquement quand une nouvelle version sort (bandeau dans le menu), avec un lien direct vers la page de téléchargement

---

## Utilisation
1. Lance l'app
2. Branche l'Arduino Nano en USB
3. Clique sur **↺** pour lister les ports COM
4. Sélectionne le port COM de l'Arduino → **CONNECTER**
5. Appuie sur n'importe quel bouton du volant pour le détecter
6. Clique sur le numéro du bouton à assigner
7. Maintenir le bouton = pompe ON / relâcher = pompe OFF

---

## Commandes Arduino
| Commande  | Action                        |
|-----------|-------------------------------|
| ON:200    | Pompe ON vitesse 200          |
| OFF       | Pompe OFF                     |
| REV:200   | Pompe inversée (purge tube)   |
| SPD:150   | Changer vitesse à la volée    |

Flash `avix_drink_system_v2.ino` sur l'Arduino Nano (baud 9600).

---

## 🛠️ Pour toi — Builder et publier une nouvelle version

Voir **[GITHUB_SETUP.md](GITHUB_SETUP.md)** pour :
- la mise en ligne initiale du repo
- comment publier une nouvelle Release (avec le `.exe`) à chaque mise à jour
- comment le bandeau de mise à jour dans l'appli fonctionne

---

AVIX_3D © 2026 — avix3d.com
