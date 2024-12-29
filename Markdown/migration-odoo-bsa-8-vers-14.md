Migration Odoo BSA 8 vers 14

# Réunion 4 avril

```
+-----------------------------------------------------------------+---+
|                                                                 |   |
+-----------------------------------------------------------------+---+
| Système de gestion à ajouter dans menu « Qualité » :            |   |
|                                                                 |   |
| \- Revues : Champs Nom, Date, Référence et Pièces jointes       |   |
|                                                                 |   |
| \- Audit : Nom, Date, Référence, Système (Liste de choix),      |   |
| Auditeurs (Champ texte et non pas liste des utilisateurs) et    |   |
| Pièces jointes                                                  |   |
|                                                                 |   |
| \- Manuels : Titre, catégorie (Liste de choix), Dernier         |   |
| contributeur, Date de modification et Pièces jointes            |   |
|                                                                 |   |
| Importer les données sans les pièces jointes                    |   |
|                                                                 |   |
| Faire fonctionner application tablette « Atelier » qui va       |   |
| chercher dans les articles et le manuel Qualité » =\> Il faudra |   |
| remettre les pièces jointes dans les articles                   |   |
+-----------------------------------------------------------------+---+
|                                                                 |   |
+-----------------------------------------------------------------+---+
| Créer menu « Outillage » dans menu « Qualité » en reprenant les |   |
| données de la liste « GMAO / Machines » =\> Juste les champs de |   |
| la vue liste                                                    |   |
|                                                                 |   |
| =\> Importer les données                                        |   |
+-----------------------------------------------------------------+---+
```

# Réunion du 24 février 2022

  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ----------
  La création des étiquettes depuis les ordres de fabrication ne fonctionne pas                                                                                                                   25/02/22
  Apporter alimentation pointeuse pour la prochaine fois                                                                                                                                          25/02/22
  Voir pour renuméroter les factures =\> Problème création factures suite importation                                                                                                             25/02/22
  Sur base inox, voire pour livrer même si pas de stock car déclaration de fab faites après les livraisons =\> Pour forcer, il faut indiquer la quantité à livrer                                 25/02/22
  Pas de bouton \"Forcer la dispo\" sur les ordres de fabrication =\> Ce bouton n\'est plus nécessaire. Si pas de stock sur les composants, cela va bien générer un stock négatif comme avant     25/02/22
  Mettre en vue liste les articles par défaut                                                                                                                                                     25/02/22
                                                                                                                                                                                                  
  Mettre le lien entre l'étiquette de livraison et stock.move.line et non pas stock.move                                                                                                          
                                                                                                                                                                                                  
                                                                                                                                                                                                  
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ----------

# A Faire

```
+----------------------------------------------------+----------+
| Mettre en ligne le module                          | 18/12/21 |
+----------------------------------------------------+----------+
| Revoir les séquences                               | 20/12/21 |
+----------------------------------------------------+----------+
| Masquer menu « Discussion » et « Suivi des liens » | 20/12/21 |
+----------------------------------------------------+----------+
| Rechercher le terme openerp et remplacer par odoo  | 20/12/21 |
+----------------------------------------------------+----------+
| Reprise partielle des fichiers .xml et .py         | 20/12/21 |
+----------------------------------------------------+----------+
| Élargir les formulaire (commande, factures,\...)   | 08/01/22 |
+----------------------------------------------------+----------+
| Repartir d'une base vierge et installer le module  | 04/02/22 |
+----------------------------------------------------+----------+
|                                                    |          |
+----------------------------------------------------+----------+
| Revoir :                                           |          |
|                                                    |          |
| account_invoice_view.xml                           |          |
|                                                    |          |
| account_move_line_view.xml                         |          |
|                                                    |          |
| mrp_production_view.xml (ir.actions.server)        |          |
|                                                    |          |
| mrp_view.xml (mrp.production.workcenter)           |          |
|                                                    |          |
| product_view.xml (ir.actions.server)               |          |
|                                                    |          |
| purchase_view.xml                                  |          |
|                                                    |          |
| sale_view.xml                                      |          |
|                                                    |          |
| stock_view.xml                                     |          |
+----------------------------------------------------+----------+
| Tester les Wizard                                  |          |
+----------------------------------------------------+----------+
| Migrer les PDF                                     |          |
+----------------------------------------------------+----------+
|                                                    |          |
+----------------------------------------------------+----------+
```