# `odoo-bin upgrade_code` — documentation

Analyse faite le 2026-08-28 sur le dépôt `odoo/odoo` (Community, LGPL), branches `19.0` et `master`.

## C'est quoi

Une sous-commande d'`odoo-bin` (comme `shell`, `scaffold`, `deploy`...) qui réécrit automatiquement du code source (Python, XML, JS, CSS/SCSS, CSV, PO/POT) pour appliquer les changements de syntaxe imposés par les nouvelles versions d'Odoo. Elle s'applique à **n'importe quel code pointé par `--addons-path`**, y compris un module custom comme `is_fromtome20` — pas seulement le core Odoo.

Fichier source : `odoo/cli/upgrade_code.py`. Scripts de réécriture : `odoo/upgrade_code/*.py`.

Citation du docstring officiel : *"all the scripts are doing a best-effort at migrating the source code, they only help do the heavy-lifting, they are not silver bullets"* — donc relecture manuelle obligatoire après passage.

## Prérequis

- **Community only, confirmé** : code dans le dépôt public `odoo/odoo`, aucune dépendance à `odoo/enterprise`.
- L'outil lui-même **n'existe qu'à partir de la version 18.0** du code source (absent en 15/16/17). Il faut donc une installation Odoo **18.0 ou plus récente** pour l'exécuter (peu importe la version cible ou celle de la base de données — c'est un simple réécrivain de fichiers texte).
- **Pas besoin de base de données ni de serveur qui tourne** : il lit/écrit des fichiers sur disque, rien d'autre. Juste `odoo-bin` d'une installation 18/19/20 disponible localement, pointé sur le dossier du module à migrer.

## Granularité : fichier par fichier ou tout d'un coup ?

**Les deux sont possibles, ce n'est pas tout ou rien** :

- **Par plage de versions** (défaut) : `--from` / `--to` exécutent tous les scripts dont le numéro de version tombe dans l'intervalle, sur tous les fichiers éligibles du chemin donné.
- **Par script précis** : `--script=NOM` n'exécute qu'un seul script (ex. seulement le renommage `tree` → `list`, sans toucher au reste).
- **Par fichier/dossier précis** : `--glob` restreint les fichiers traités à un motif donné, relatif au dossier passé dans `--addons-path`. Exemple : ne traiter qu'un seul fichier de vues, ou seulement le dossier `models/`.
- **`--dry-run`** : liste les fichiers qui seraient modifiés, sans rien écrire — à utiliser systématiquement en premier passage pour évaluer l'ampleur avant d'appliquer.

Combinaison typique pour un contrôle fin, fichier par fichier :
```bash
python odoo-bin upgrade_code --from=17.5 --to=19.0 \
  --addons-path=/chemin/vers/is_fromtome20 \
  --glob="views/sale_view.xml" \
  --dry-run
```
Puis, une fois validé, retirer `--dry-run` pour appliquer réellement sur ce fichier, avant de passer au suivant. Rien n'oblige à lancer l'outil sur tout le module en une seule fois — c'est même déconseillé pour un module de cette taille (~35 modèles, ~40 vues), afin de pouvoir relire chaque diff produit avant de continuer.

## Options complètes

| Option | Rôle |
|---|---|
| `--from VERSION` | Version de départ (inclusive). Mutuellement exclusif avec `--script` |
| `--to VERSION` | Version de fin (inclusive). Par défaut : version de l'`odoo-bin` utilisé |
| `--script NOM` | Exécute uniquement le script dont le nom contient `NOM` |
| `--glob MOTIF` | Motif de sélection des fichiers (défaut `**/*`, relatif à chaque chemin d'`--addons-path`) |
| `--dry-run` | Liste les fichiers qui seraient modifiés, sans écrire sur disque |
| `--addons-path PATH,...` | Chemin(s) à traiter (peut être le dossier du module directement) |

## Scripts disponibles (branche `19.0`)

| Script | Ce qu'il fait |
|---|---|
| `17.5-01-tree-to-list.py` | Renomme `tree` → `list` partout : balises de vues, `view_mode`, `mode=`, xpath, `tree_view_ref` → `list_view_ref`, texte "tree view" → "list view", `self.env.ref(...)`. Très complet, couvre XML/JS/Python |
| `18.1-00-sql-constraint.py` | Convertit `_sql_constraints = [(...)]` vers la nouvelle syntaxe déclarative `_xxx = models.Constraint(...)` |
| `18.1-02-route-jsonrpc.py` | Dans les contrôleurs HTTP : `type="json"` → `type="jsonrpc"` sur les `@http.route` |
| `18.2-00-l10n-translate.py` | Ajustements de traduction pour les modules de localisation |
| `18.3-00-l10n-fiscal-position-taxes.py` | Changements de structure sur les positions fiscales/taxes — **pertinent pour `is_fromtome20`** (module comptabilité/paiement FR) |
| `18.5-00-deprecated-properties.py` | `self._cr` / `self._uid` / `self._context` → `self.env.cr` / `self.env.uid` / `self.env.context` |
| `18.5-00-domain-dynamic-dates.py` | Réécrit la syntaxe des dates dynamiques dans les domaines. Le plus complexe (AST), relecture manuelle conseillée après passage |
| `18.5-00-no-tax-tag-invert.py` | Changement sur l'inversion des tags de taxes — **pertinent pour `is_fromtome20`** |

## Scripts en préparation pour la suite (branche `master`, pas encore taguée 20.0 — à confirmer/réactualiser une fois la 20.0 sortie)

À surveiller pour la phase 19 → 20 :

| Script | Ce qu'il fait |
|---|---|
| `19.1-00-t-call.py` | Ferme automatiquement les balises `<t>` auto-fermantes dans les templates QWeb |
| `19.3-00-account-groups.py` | Restructuration des groupes comptables |
| `19.3-00-account-report-foldable.py` | Simplifie la syntaxe des formules dans les rapports comptables (`domain_formula` → `domain`, `aggregation_formula` → `aggregation`, etc.) |
| `19.3-00-base64-in-xml.py` | Ajustement de syntaxe pour les champs `type="base64"` en XML |
| `19.4-00-ir-access.py` | Restructuration du système de droits d'accès (`ir.model.access`) — **à surveiller de près pour la Phase 6 (Sécurité) de la migration 19→20** |
| `19.4-00-ormcache-on-transaction.py` | `registry.clear_cache` remplacé par un mécanisme au niveau transaction |
| `19.5-00-tuple-rec_names_search.py` | `_rec_names_search = ['name']` → `_rec_names_search = ('name',)` (liste → tuple) |
| `owl3-migration.py` | **Migration OWL 2 → OWL 3** du JS front-end. Très gros script (regex + AST sur templates et expressions JS). Confirme qu'une nouvelle version majeure du framework JS arrive après la 19 — **impact direct sur la Phase 9 (JS/assets) de la checklist** si le module a des widgets custom |

## Recommandation d'usage dans le cadre de la migration `is_fromtome14` → `is_fromtome20`

- **Phase 5 (modèles Python)** : lancer `--from=17.5 --to=19.0` avec `--glob` restreint à chaque fichier/domaine au fur et à mesure, pour bénéficier de `sql-constraint`, `deprecated-properties`
- **Phase 6 (sécurité)** : rien d'automatisable ici pour 14→19 ; à ré-évaluer pour 19→20 à cause de `19.4-00-ir-access.py`
- **Phase 7 (vues XML)** : lancer `tree-to-list` en premier sur chaque fichier de vues (gain de temps le plus important), puis traiter `attrs`/`states` **à la main** (non couvert par l'outil, cf. `preparation-migration-odoo-fromtome-14-ver-20.md`)
- **Phase 9 (JS/assets)** : à surveiller de près une fois la 20.0 sortie à cause d'`owl3-migration.py`

## Fonctionne-t-il en partant directement du code 14.0 ?

Oui. L'outil repère des motifs textuels (regex/AST : une balise `<tree>`, une liste `_sql_constraints`, un `self._cr`...) et les réécrit, peu importe depuis quand ils sont dans le code — il ne vérifie pas la version d'origine. `--from`/`--to` sélectionnent seulement quels scripts lancer selon leur propre numéro, pas l'état du code cible. Aucun script n'existant avant `17.5-*.py`, `--from=14.0` équivaut à `--from=17.5`. Seule contrainte : exécuter la commande avec le binaire `odoo-bin` d'une installation 18.0+ (l'outil n'existe pas en 14), pointé via `--addons-path` sur le module copié `is_fromtome20`, code 14 intact.

## Limites

- Ne couvre pas la suppression d'`attrs`/`states` (17.0) — le changement le plus impactant pour ce module, à faire entièrement à la main
- Uniquement disponible à partir d'une installation Odoo **18.0+** (pas utilisable directement depuis une installation 14)
- Réécriture best-effort par regex/AST — toujours relire le diff produit, en particulier sur les domaines dynamiques et la fiscalité
- La liste de scripts pour la tranche 19→20 vue sur `master` n'est pas figée tant que la 20.0 n'est pas taguée — à revérifier à ce moment-là
