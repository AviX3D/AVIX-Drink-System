# Mise en ligne sur GitHub + mises à jour

## 1. Créer le repo (une seule fois)

1. Va sur https://github.com/new
2. Nom : `avix-drink-system` (ou ce que tu veux)
3. **Public**
4. Ne coche rien d'autre (pas de README, pas de licence) — on a déjà nos fichiers
5. Crée le repo

## 2. Pousser le code (une seule fois)

Dans ce dossier, ouvre un terminal (ou Git Bash) :

```bash
git init
git add .
git commit -m "Version initiale"
git branch -M main
git remote add origin https://github.com/TON_USERNAME/avix-drink-system.git
git push -u origin main
```

⚠️ Remplace `TON_USERNAME` par ton pseudo GitHub.

## 3. Brancher la vérification de mise à jour (une seule fois)

Ouvre `avix_drink.py`, tout en haut, ligne `GITHUB_REPO = "TON_USERNAME/avix-drink-system"` :
remplace `TON_USERNAME/avix-drink-system` par le vrai chemin de ton repo (ex: `thomas123/avix-drink-system`).

Recommit ce changement :
```bash
git add avix_drink.py
git commit -m "Config repo pour les maj auto"
git push
```

## 4. Publier une nouvelle version (à chaque mise à jour)

1. Dans `avix_drink.py`, monte le numéro de version :
   ```python
   APP_VERSION = "3.0.1"   # ex: 3.0.0 -> 3.0.1
   ```
2. Deux choix pour builder :
   - **`BUILD.bat`** → génère juste `dist\AVIX Drink System.exe` (le client double-clique dessus, pas d'installation)
   - **`BUILD_MSI.bat`** → génère en plus un vrai installeur `AVIX_Drink_System_Setup.exe` (raccourci bureau + menu démarrer + désinstalleur propre). Nécessite [NSIS](https://nsis.sourceforge.io) installé une fois sur ton PC. **Recommandé pour tes clients.**
3. Commit et tag :
   ```bash
   git add avix_drink.py
   git commit -m "v3.0.1"
   git tag v3.0.1
   git push && git push --tags
   ```
4. Sur GitHub → onglet **Releases** → **Draft a new release**
   - Choisis le tag `v3.0.1`
   - Titre : `v3.0.1`
   - Glisse `dist\AVIX Drink System.exe` dans la zone de fichiers
   - **Publish release**

C'est tout. Le tag GitHub (`v3.0.1`) doit toujours correspondre à `APP_VERSION` dans le code — c'est ce que l'appli compare pour savoir si une maj existe.

## Comment ça marche côté client

À chaque lancement, l'appli interroge en silence l'API GitHub (`/releases/latest`) pour connaître la dernière version publiée. Si elle est plus récente que celle installée, un bouton orange **"⭱ Mise à jour vX.X.X"** apparaît dans le menu de gauche ; un clic ouvre la page de téléchargement dans le navigateur. Aucune installation forcée — le client garde la main.

Pas de connexion internet ou repo pas encore public → l'appli ne fait rien de spécial, elle continue normalement.
