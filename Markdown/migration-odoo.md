Outils à mettre en place pour faire une migration d'Odoo
====

```
+-----------------------------------------------------------+----------+
| Outil                                                     | Fait     |
+-----------------------------------------------------------+----------+
| Liste des tables d'une base avec le nombre                |          |
| d'enregistrement                                          |          |
+-----------------------------------------------------------+----------+
| Liste des champs d'une table                              |          |
+-----------------------------------------------------------+----------+
| Comparatif entre les tables d'une base et une autre       |          |
+-----------------------------------------------------------+----------+
| Comparatif entre les champs d'une d'une table d'une base  |          |
| et de l'autre                                             |          |
+-----------------------------------------------------------+----------+
|                                                           |          |
+-----------------------------------------------------------+----------+
| Faire une migration des données de démo des modules       |          |
| Facturation et ventes entre les bases odoo12 et odoo13    |          |
+-----------------------------------------------------------+----------+
|                                                           |          |
+-----------------------------------------------------------+----------+
| Comparer les types des champs d'une table entre les 2     |          |
| bases                                                     |          |
|                                                           |          |
| Pour chaque champ rechercher si il est utilisé            |          |
| (rechercher les distinct sur ce champ et les non vides,   |          |
| et les non null)                                          |          |
+-----------------------------------------------------------+----------+
| Copier une table d'une base dans une autre avec           |          |
| dump/restore (si le format est le même)                   |          |
+-----------------------------------------------------------+----------+
|                                                           |          |
+-----------------------------------------------------------+----------+
| Copier une table sur une autre sans supprimer les id      |          |
| existant =\> Recherche l'id et faire un update de         |          |
| celui-ci si le contenu est diffent (faire un sumcheck     |          |
| pour savoir si l'enregistrement est le même ou pas        |          |
|                                                           |          |
| =\> Calculer le checksum de chaque enregistrement et      |          |
| faire une mise à jour dans la table de destination si     |          |
| différence                                                |          |
+-----------------------------------------------------------+----------+
| Tables à migrer :                                         |          |
|                                                           |          |
| \- res_users                                              |          |
|                                                           |          |
| \- res_partner                                            |          |
|                                                           |          |
| \- product_product                                        |          |
|                                                           |          |
| \- product_template                                       |          |
+-----------------------------------------------------------+----------+
| Migration odoo des groupes et droits. Voir comment faire  |          |
|                                                           |          |
| =\> Les groupes par défaut évoluent et les droits         |          |
| également                                                 |          |
+-----------------------------------------------------------+----------+
| Nouvelles actions à créer :                               |          |
|                                                           |          |
| -   table2table : Migre les données d'une table vers la   |          |
|     base de destination                                   |          |
|                                                           |          |
| -   table2csv                                             |          |
|                                                           |          |
| -   csv2table                                             |          |
+-----------------------------------------------------------+----------+
|                                                           |          |
+-----------------------------------------------------------+----------+
| Comparer les modules installés (faire la liste de tous    | 22/11/20 |
| les modules et comparer si il existe dans les 2 bases et  |          |
| si ils sont installés                                     |          |
+-----------------------------------------------------------+----------+
| Comparer les catégories de modules (+ lien avec           |          |
| res_groups)                                               |          |
+-----------------------------------------------------------+----------+
|                                                           |          |
+-----------------------------------------------------------+----------+
| La migration des tables res_groups et ir_module_category  |          |
| semble fonctionner, mais à mon avis cela doit poser des   |          |
| problèmes dans la gestion des droits, car les groupes ont |          |
| changés et les droits liés également                      |          |
+-----------------------------------------------------------+----------+
``


# Séquences des tables

Il faut initialer le compteur de chaque table après la migration car
pour les pièces jointes, cela fait planter la génération à la volée des
CSS une page blanche s'affiche à la place d'Odoo

odoo13=# select setval(\'ir_attachment_id_seq\',515);

# ir_attachment

rsync -rva /home/odoo/.local/share/Odoo/filestore/odoo12/
/home/odoo/.local/share/Odoo/filestore/odoo13

Avec Odoo 13, il y a 5 format d'image et non plus 3 :

Champ res_field de ir_attachment dans Odoo 12 :

image

image_medium

image_small

Champ res_field de ir_attachment dans Odoo 13 :

image_1920

image_512

image_1024

image_128

image_256

Il faut donc faire cette requête pour revoir les vignettes des images :

odoo13=#

update ir_attachment set res_field=\'image_128\' where
res_field=\'image_small\';

update ir_attachment set res_field=\'image_1920\' where
res_field=\'image\';

**Problèmes constatés**

-   Impossible de voir la liste des utilisateurs, probablement lié à un
    problème de droit sur les vues ou menus (cf point suivant)

**Problèmes avec ces tables :**

ir_ui_view

ir_ui_view_group_rel

Un problème est survenu!

Enregistrement inexistant ou détruit. (Enregistrement:
ir.module.category(57,), Utilisateur: 2)

Le problème vient de la table « res_groups » qui est en relation avec la
table «  ir.module.category » via le champ « category_id »

doo13_migre=# select id,name,category_id from res_groups;

id \| name \| category_id

\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\--

36 \| Quotation Templates \| 5

1 \| Internal User \| 41

8 \| Access to Private Addresses \|

2 \| Access Rights \| 57

4 \| Multi Companies \| 58

**Problème avec « product_attribute »**

Migration product_attribute

Traceback (most recent call last):

File \"./migration-odoo-12-vers13.py\", line 57, in \<module\>

MigrationTable(db_src,db_dst,table)

File
\"/media/sf_dev_odoo/13.0/migration-12-vers-13/migration_fonction.py\",
line 216, in MigrationTable

CSV2Table(cnx_dst,cr_dst,table)

File
\"/media/sf_dev_odoo/13.0/migration-12-vers-13/migration_fonction.py\",
line 183, in CSV2Table

cr_dst.execute(SQL)

psycopg2.IntegrityError: ERREUR: une valeur NULL viole la contrainte NOT
NULL de la colonne « display_type »

DETAIL: La ligne en échec contient (1, Legs, 1, always, 1, 2020-11-18
15:34:37.921483, 1, 2020-11-18 15:34:37.921483, null)

CONTEXT: COPY product_attribute, ligne 2 : « 2020-11-18
15:34:37.921483,1,always,1,Legs,1,2020-11-18 15:34:37.921483,1 »

Mettre display_type=radio par défaut pour ce nouveau champ

**Revoir cette fonction pour ne pas mettre en dur ces lignes**

def MigrationTable(db_src,db_dst,table,rename={}):

cnx_src,cr_src=GetCR(db_src)

cnx_dst,cr_dst=GetCR(db_dst)

champs_src = GetChamps(cr_src,table)

champs_dst = GetChamps(cr_dst,table)

champs = champs_src + champs_dst \# Concatener les 2 listes

**if table==\'product_attribute\':**

**champs_src.append(\'type\')**

**champs_dst.append(\'type\')**

# Migration 12 vers 13 avec les principaux modules installés

## ![](vertopal_25b0784a80ac44599d01760317683300/media/image1.png){width="7.480555555555555in" height="0.9006944444444445in"}

## Différences sur les modules installés

./migration-odoo.py compare_modules

\- decimal_precision state_src=installed OK

\- web_settings_dashboard state_src=installed OK

## Différence entre les groupes

./migration-odoo.py compare_res_groups \| grep test

\- Administrator OK test

\- Advanced Pricelists OK test

\- Basic Pricelists OK test

\- Billing Administrator OK test

\- Billing Manager OK test

\- Display Serial & Lot Number on OK test

\- Enable Route on Sales Order Li OK test

\- Lock Confirmed Sales OK test

\- Manage Pricelist Items OK test

\- Manage Vendor Price OK test

\- Manage delivery dates from sal OK test

\- Manager OK test

\- Pricelists On Product OK test

\- Produce residual products OK test

\- Sales Pricelists OK test

\- Use products on vendor bills OK test

## Comparatif des tables

92 tables différentes

./migration-odoo.py compare_tables \| grep test1 \| wc -l

92

**Ajouter les taxes sur les commandes**

# res_partner

Champs modifiés

champ type_src type_dst ok_src ok_dst

customer boolean OK

customer_rank integer OK

supplier boolean OK

supplier_rank integer OK

Condition de paiement

Liste de prix
