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

## 4. Publier une nouvelle version

1. Dans `avix_drink.py`, monte `APP_VERSION` (ex. `"4.0.1"`) et ajoute une section en haut de `CHANGELOG.md`. Mets ça sur `main`.
2. Sur GitHub, va dans **Releases**, puis **Draft a new release**. Tape l'étiquette `v4.0.1` (« Create new tag »), cible `main`, écris les notes, puis clique sur **Publish release**.
3. GitHub Actions (`.github/workflows/release.yml`) compile le `.exe` sous Windows et l'ajoute tout seul à la release (`AVIX_Drink_System.exe`). Ça prend environ 5 minutes ; tu peux suivre l'avancement dans l'onglet **Actions**.

Pour ajouter le `.exe` à une release déjà publiée : onglet **Actions**, puis **Release Windows**, puis **Run workflow**, en indiquant l'étiquette.
Mets toujours l'étiquette sous la forme `vX.Y.Z`, avec le même numéro que `APP_VERSION` : c'est ce que l'appli compare pour afficher la bannière de mise à jour.
GitHub ajoute toujours tout seul les archives « Source code » à une release : on ne peut pas les retirer, mais tes clients n'ont besoin que du `.exe`.
