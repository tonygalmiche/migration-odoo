# Préparation migration `is_fromtome14` : Odoo 14 → Odoo 20 (directe, sans OpenUpgrade)

Date de l'analyse : 2026-08-28
Odoo 20 pas encore sorti (sortie prévue fin août 2026) → analyse faite sur les branches **18.0** et **19.0** des dépôts OCA, à réactualiser dès que la 20.0 existe.

## Méthode

Migration directe 14 → 20 en un seul saut, avec les scripts maison du dossier `migration-odoo/` (comme `migration-odoo-infosaone-13-vers-19.py`), pas OpenUpgrade.

Vérification faite via l'API GitHub (contenu du dossier de chaque module dans chaque branche du repo OCA correspondant).

## Changements du framework Odoo lui-même (pas les modules) — 14.0 → 19.0

Analyse faite en diffant directement le code source de `odoo/odoo` entre les tags `14.0` et `19.0` sur GitHub (fichiers clés du framework : `odoo/api.py`, `odoo/fields.py`, `odoo/models.py`, `odoo/addons/base/models/ir_ui_view.py`, `odoo/cli/upgrade_code.py`, `odoo/upgrade_code/*.py`). **Reste à faire : 19.0 → 20.0, une fois cette version sortie** (refaire le même exercice, les scripts `odoo/upgrade_code/` couvrant cette tranche seront alors ajoutés au repo).

### Outil officiel d'aide à la migration du code (le plus utile trouvé)

Depuis la 17.5, Odoo fournit `odoo-bin upgrade_code` : applique automatiquement des scripts de réécriture (regex/AST) sur n'importe quel code, y compris un module custom comme `is_fromtome20`, pas seulement le core.

```bash
python odoo-bin upgrade_code --from=17.5 --to=19.0 --addons-path=/chemin/vers/is_fromtome20 --dry-run
```
Retirer `--dry-run` pour appliquer réellement les réécritures. À lancer en Phase 5/7 (modèles/vues) de la checklist, avant la relecture manuelle.

### Changements couverts par cet outil (automatisables)
- **`<tree>` → `<list>`** : vues, xpath, attribut `view_mode`, `mode=`, `tree_view_ref`, etc. (script très complet, tous les patterns XML/JS/Python usuels)
- **`_sql_constraints = [...]`** → nouvelle syntaxe déclarative `models.Constraint(...)`
- **Contrôleurs HTTP** : `type="json"` → `type="jsonrpc"` dans les `@http.route`
- **`self._cr` / `self._uid` / `self._context`** → `self.env.cr` / `self.env.uid` / `self.env.context`
- **Domaines avec dates dynamiques** : syntaxe changée (relecture manuelle conseillée après passage du script)
- Quelques scripts spécifiques localisation FR/fiscalité (`l10n-fiscal-position-taxes`, `no-tax-tag-invert`, `l10n-translate`) — à surveiller vu les modules compta/paiement/TVA du module

### Changement majeur NON couvert par l'outil (à faire à la main)
- **`attrs=` et `states=` sur les vues, supprimés depuis la 17.0** : génèrent désormais une **erreur bloquante** (`ValidationError`) au chargement de la vue, pas juste un avertissement (confirmé dans `ir_ui_view.py` 19.0). Aucun script `upgrade_code` ne le couvre (les scripts ne commencent qu'à partir de la 17.5). À réécrire à la main en expressions Python directes dans `invisible=`/`readonly=`/`required=`, vue par vue — c'est le plus gros chantier mécanique de la Phase 6 de la checklist.

### Réorganisation interne du framework
- `odoo/api.py`, `odoo/fields.py`, `odoo/models.py` sont devenus des **packages** (`odoo/api/`, `odoo/fields/`, `odoo/models/`) entre la 14 et la 19. Sans impact si le code ne fait que `from odoo import api, fields, models` (API publique stable) — à vérifier si du code fait des imports plus profonds (`from odoo.fields import ...` par ex.)

## Dépendances du manifest (`__manifest__.py`)

| Dépendance | Repo | 18.0 | 19.0 | Statut / action |
|---|---|:---:|:---:|---|
| `base`, `mail`, `sale`, `product`, `sale_management`, `account`, `stock`, `purchase`, `purchase_stock`, `mrp`, `board`, `hr` | Odoo core | ✅ | ✅ | RAS, modules standards |
| `account_edi` | Odoo core | ✅ | ✅ | RAS, toujours dans odoo/odoo |
| `account_payment_order` | OCA/bank-payment | ✅ | ✅ | OK |
| `account_payment_partner` | OCA/bank-payment | ✅ | ❌ | **Supprimé du repo à partir de 19.0.** PR `[19.0][MIG]` (#1580) non mergée + PR `[19.0][FIX] Removed account_payment_partner` (#1530). Fonctionnalité probablement absorbée par `account_payment_order` en 19.0 — **à vérifier au moment de la migration** (relire le code de `account_payment_order` 19.0 pour voir si le calcul du compte bancaire du partenaire y est intégré nativement, ou s'il faut porter le module soi-même) |
| `account_payment_purchase` | OCA/bank-payment | ✅ | ✅ | OK |
| `account_payment_sale` | OCA/bank-payment | ✅ | ✅ | OK |
| `account_banking_fr_lcr` | OCA/l10n-france | ⚠️ | ⚠️ | **Renommé en `account_payment_fr_lcr`** (présent en 18.0 et 19.0 sous ce nouveau nom). Mettre à jour le nom de la dépendance dans le manifest + adapter les éventuelles références de code/vues à l'ancien nom technique |
| `account_banking_sepa_credit_transfer` | OCA/bank-payment | ✅ | ✅ | OK |
| `account_banking_sepa_direct_debit` | OCA/bank-payment | ✅ | ✅ | OK |
| `l10n_fr_department` | OCA/l10n-france | ✅ | ✅ | OK |
| `l10n_fr_fec` | — | ❌ | ❌ | **N'existe déjà plus en tant que module séparé dès 14.0** dans OCA/l10n-france ni dans odoo/odoo depuis ~18.0 (existait comme module core Odoo en 14.0, `addons/l10n_fr_fec`, supprimé du core par la suite). L'export FEC est désormais intégré nativement dans la Comptabilité Odoo (menu Reporting). **Action : supprimer cette dépendance du manifest**, vérifier que l'export FEC standard répond au besoin |
| `l10n_fr_intrastat_product` | OCA/l10n-france | ✅ | ✅ | OK (bien présent dans le repo `l10n-france`, pas dans `intrastat-extrastat`) |
| `l10n_fr_siret` | OCA/l10n-france | ✅ | ✅ | OK |
| `l10n_fr_state` | OCA/l10n-france | ✅ | ✅ | OK |
| `list_export_excel_app` | Module tiers payant (Edge Technologies, Apps Store) | — | — | **Obsolète : l'export Excel est natif dans Odoo depuis plusieurs versions.** `is_fromtome14` ne l'utilise nulle part dans son code (seule la ligne `depends`) → **supprimer la dépendance et ne pas migrer ce module** |
| `is_llm2odoo` | Module perso (tonygalmiche) | à migrer soi-même | à migrer soi-même | Idem |

## Points bloquants / actions à prévoir avant de démarrer

1. **`account_payment_partner`** : pas de version OCA au-delà de 18.0. Deux options :
   - rester dépendant de la version 18.0 du module (si compatible/installable tel quel sur une base 19/20, peu probable sans adaptation) ;
   - lire le code source de `account_payment_order` 19.0 pour confirmer si la logique a été internalisée, et adapter `is_fromtome14` en conséquence (suppression de la dépendance si redondante).
2. **`account_banking_fr_lcr` → `account_payment_fr_lcr`** : renommage simple mais à répercuter partout où le nom technique est utilisé (manifest, éventuels `_inherit`, vues héritées, XML ids).
3. **`l10n_fr_fec`** : dépendance à retirer purement et simplement du manifest ; vérifier qu'aucun code du module `is_fromtome14` ne référence des modèles/vues spécifiques à cet ancien module (`grep -r l10n_fr_fec` dans `is_fromtome14`).
4. **`list_export_excel_app` et `is_llm2odoo`** : ce sont des prérequis internes — les migrer (ou au moins les rendre installables sur 20) avant de pouvoir installer/tester `is_fromtome14` sur la nouvelle version.
5. Dès la sortie effective d'Odoo 20 (fin août 2026), refaire cette vérification avec la branche `20.0` de chaque repo OCA cité (`bank-payment`, `l10n-france`) car les statuts peuvent changer (nouvelles migrations, nouvelles suppressions/fusions).

## Commande de vérification réutilisable

```bash
for mod_repo in "account_payment_order:bank-payment" "account_payment_partner:bank-payment" \
  "account_payment_purchase:bank-payment" "account_payment_sale:bank-payment" \
  "account_payment_fr_lcr:l10n-france" "account_banking_sepa_credit_transfer:bank-payment" \
  "account_banking_sepa_direct_debit:bank-payment" "l10n_fr_department:l10n-france" \
  "l10n_fr_siret:l10n-france" "l10n_fr_state:l10n-france" "l10n_fr_intrastat_product:l10n-france"; do
  mod="${mod_repo%%:*}"; repo="${mod_repo##*:}"
  for branch in 20.0 19.0 18.0; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "https://api.github.com/repos/OCA/$repo/contents/$mod?ref=$branch")
    echo "$mod ($repo) - $branch : $code"
  done
done
```
(`200` = module présent dans la branche, `404` = absent/renommé/supprimé)

## Ordre de migration (checklist)

Pas de branche git : création d'un **nouveau module `is_fromtome20`** (copie de `is_fromtome14`), migré étape par étape en parallèle du module 14 qui reste inchangé en prod.

### Méthode technique d'activation progressive (Phases 4 à 7)

Pour piloter l'avancement, on active le module par blocs successifs en commentant/décommentant plutôt qu'en ajoutant le code au fur et à mesure :

1. Dans `__manifest__.py` : `depends` reste intact dès le départ, mais la liste `data` est vidée/commentée (aucun XML chargé). Dans `models/__init__.py` et `wizard/__init__.py` : tous les imports de fichiers `.py` sont commentés → le module s'installe vide.
2. On décommente les imports de modèles dans `models/__init__.py`, fichier par fichier ou domaine par domaine (Phase 5) → les modèles se créent en base, sans vue ni sécurité.
3. On décommente `security/res.groups.xml`, `ir.model.access.csv`, `ir.model.access.xml` dans `data` (Phase 6) → droits d'accès en place.
4. On décommente le reste des XML (`views/*.xml`, `report/*.xml`, `data/*.xml`) progressivement dans `data` (Phase 7 et suivantes).

### Phase 1 — Création du nouveau module
- [ ] Copier `is_fromtome14` → `is_fromtome20`
- [ ] Renommer le module technique partout où nécessaire (nom de dossier, éventuelles références internes)
- [ ] Poser un Odoo 20 propre (base + config serveur) à côté de la prod 14

### Phase 2 — Nettoyage du code mort (sur `is_fromtome20`)
- [ ] Repérer et supprimer tout le **code mort commenté** (lignes de code Python ou XML laissées en commentaire, `#` ou `<!-- -->`) dans tous les fichiers `models/*.py`, `views/*.xml`, `report/*.xml`, `wizard/*.py`
- [ ] Ne toucher à **aucun commentaire explicatif** (docstrings, notes, `# explique pourquoi...`) — relecture manuelle fichier par fichier, pas de suppression automatique par regex

### Phase 3 — Dépendances externes
- [ ] Nettoyer le manifest : retirer `l10n_fr_fec`, retirer `list_export_excel_app`, renommer `account_banking_fr_lcr` → `account_payment_fr_lcr`
- [ ] Trancher le cas `account_payment_partner` (absorbé par `account_payment_order` ou à porter soi-même)
- [ ] Installer tous les modules OCA restants sur l'instance 20 vierge, vérifier qu'ils s'installent entre eux sans erreur
- [ ] Migrer `is_llm2odoo` (module perso, dépendance directe) — le faire s'installer seul sur la 20

### Phase 4 — Squelette du module
- [ ] Manifest minimal (nom `is_fromtome20`, version, depends nettoyés, `data` vide pour l'instant)
- [ ] Le module vide s'installe sur la 20

### Phase 5 — Modèles Python, par domaine métier (sans sécurité ni vues)
- [ ] Transverse (`product.py`, `res_partner.py`, `res_company.py`, `res_users.py`, `mail_activity.py`, `mail_template.py`)
- [ ] Achats (`purchase_order.py`, `supplier_discount.py`, `is_promo_fournisseur.py`)
- [ ] Stock (`stock.py`, `stock_quant.py`, `stock_move_line.py`, `stock_picking.py`, `stock_inventory.py`, `stock_production_lot.py`, `is_stock_move_line.py`, `is_stock_production_lot_contrat.py`, `is_preparation_transfert_entrepot.py`, `is_imprimer_etiquette_gs1.py`)
- [ ] Ventes (`sale_order.py`, `is_sale_order_line.py`, `is_modele_commande.py`, `is_promo_client.py`, `is_listing_prix_client.py`, `product_pricelist.py`)
- [ ] Comptabilité/Paiement (`account_move.py`, `account_payment.py`, `is_account_invoice_line.py`, `is_export_compta.py`, `is_relance_facture.py`, `is_analyse_facturation.py`, `is_audit_marge_brute.py`, `is_marge_brute_article.py`)
- [ ] Métier Fromtome spécifique (`is_commande_fromtome.py`, `is_suivi_commande_hebdo.py`, `is_calcul_des_besoins.py`, `is_analyse_rupture.py`)
- [ ] Divers (`is_fnc.py`, `is_import_le_cellier.py`, `is_suivi_temps.py`, `is_prompt_ia.py`, `intrastat_product_declaration.py`)
- [ ] Wizards (`wizard/mail_compose_message.py`)
- [ ] Tous les modèles se chargent sans erreur (module toujours sans vues ni sécurité à ce stade)

### Phase 6 — Sécurité
- [ ] `security/res.groups.xml`, `ir.model.access.csv`, `ir.model.access.xml` — maintenant que tous les modèles existent, référencer leurs noms techniques sans risque d'erreur
- [ ] Le module s'installe avec les droits d'accès corrects

### Phase 7 — Vues XML, même découpage par domaine
- [ ] Transverse
- [ ] Achats
- [ ] Stock
- [ ] Ventes
- [ ] Comptabilité/Paiement
- [ ] Métier Fromtome spécifique
- [ ] Divers
- [ ] `views/menu.xml` en dernier

### Phase 8 — Rapports QWeb
- [ ] `report/*.xml` un par un, avec vérification visuelle du PDF généré

### Phase 9 — JS / assets
- [ ] `views/assets.xml` — à revoir entièrement (framework OWL très différent de la 14)

### Phase 10 — Data
- [ ] `data/stock_picking_mail.xml`

### Phase 11 — Validation technique
- [ ] Installation à blanc sur base vierge (revalidation finale globale)
- [ ] `-u is_fromtome20 --test-enable --stop-after-init` : active les tests standards Odoo (base gratuite, sans écrire de test custom). Couvre notamment commandes, livraisons, factures, listes de prix via les tests déjà fournis par `sale`, `stock`, `account` — bonne base de vérification structurelle, jugée suffisante pour l'instant, pas de test unitaire custom prévu sur la logique métier propre au module

### Phase 12 — Migration des données de prod (script dédié)

Pas de mise à jour en place de la base 14 vers 20 (pas d'OpenUpgrade) : la base 20 reste une base **neuve**, avec `is_fromtome20` installé dessus. Les données réelles sont transférées par un **script Python à développer**, sur le modèle des scripts existants dans `migration-odoo/` (ex. `migration-odoo-infosaone-13-vers-19.py`) : lecture des données dans la base 14 (SQL direct ou ORM/XML-RPC) puis recréation dans la base 20 via l'ORM, avec mapping/conversion des champs qui ont changé entre les deux versions.

- [ ] Écrire le script de migration des données, par domaine (même découpage que les phases 5/7) pour pouvoir tester et rejouer bloc par bloc
- [ ] Lancer le script sur une copie de la base de prod, vers un serveur de test en 20
- [ ] Contrôles d'intégrité post-migration (comptages, rapprochements comptables, cohérence stock)
- [ ] Répéter jusqu'à un résultat fiable et reproductible

### Phase 13 — Recette fonctionnelle avec les utilisateurs (sur données migrées)

- [ ] Recette manuelle par domaine avec les utilisateurs clés, sur le serveur de test alimenté par les données réelles migrées (Phase 12) — pas sur données de démo, pour valider la logique métier custom (non couverte par les tests standards) dans des conditions représentatives
- [ ] Exécution finale du script de migration lors de la bascule, une fois la recette validée

