Migration Odoo Thomas Electronics 8 vers 15
====

# ***A Faire manuellement après la migration***

   |***A Faire***|***Fait le***|
   | :- | :-: |
   |Remettre le logo de la société||
   |||

# ***Notes pendant le formation du 12/01/2022***

   |***A Faire***|***Fait le***|
   | :- | :-: |
   |Il manque les infos de compta dans les articles et les clients<br>=> Mettre les utilisateurs dans le groupe « Show Accounting Features - Readonly »|12/01/22|
   |Production : Quantité sur 4 chiffres|12/01/22|
   |<p>Opérations sur nomenclatures. Impossible d’enregistrer la nomenclature après avoir ajouté des opérations</p><p>update mrp\_bom\_line set company\_id=1;</p>|12/01/22|
   |<p>Commande fournisseur : Ne pas afficher « San Francisco » dans l’adresse en PDF</p><p>Ordre de fabrication : San Francisco apparaît dans onglet « Divers »</p><p>Stock / Entrepôt et Stock / Type opération à renommer</p>|13/01/22|
   |<p>Article consommable => Article stockable</p><p>update product\_template set detailed\_type='product';</p><p>update product\_template set type='product';</p>|13/01/22|
   |<p>Espacer les lignes et écrire plus petit :</p><p>- Facture<br>- BL<br>- Commande fournisseur</p>|13/01/22|
   |Commande fournisseur PDF : Il manque le tampon avec la signature|13/01/22|
   |Commande fournisseur : Dans le PDF mettre le champ « Date de confirmation » et non pas « Date de réception » dans l’entête|13/01/22|
   |<p>Vérifier les documents en anglais et français</p><p>BL</p><p>Facture</p><p>Commande fournisseur</p>|13/01/22|
   |Comparer les différents documents PDF avec Odoo 8|13/01/22|
   |<p>Facture :</p><p>Manque adresse de facturation sur la droite de la facture</p><p>Il manque la note sur la facture PDF</p>|13/01/22|
   |<p>Impression OF : Vérifier si nomenclature et gamme s’impriment sur le même document</p><p>Il faut ajouter la quantité unitaire en plus de la quantité</p>|17/01/22|
   |Le champ coût n’est pas récupéré|19/01/22|
   |Problème avec les traductions des unités (ex : KG)|19/01/22|




# ***A Faire***

   |***A Faire***|***Fait le***|
   | :- | :-: |
   |Finaliser la migration des rapports (Facture, BL,...||
   |En cliquant sur une commande, elle ne s’affiche pas (bug migration des données)||
   |Migrer les nomenclatures||
   |Mettre en ligne le module Odoo||
   |Configurer VPS pour mettre nginix sur port 8069||
   |Mettre en place la migration sur VPS||



|<p>*nfoSaône - 1 rue Jean Moulin 21110 Pluvault - http://www.infosaone.com*</p><p>*Tony Galmiche - Tél : 03 80 47 93 81 - Portable : 06 19 43 39 31 - Courriel :  tony.galmiche@infosaone.com*</p>|*age 5/5**|
| :- | :-: |
#

# ***Afficher le plan comptable et les autres menus de la compta***
Pour cela, il faut mettre les utilisateurs dans ce groupe non visible depuis la fiche utilisateur :
```Show Accounting Features - Readonly```


# ***L'utilisateur ne peut pas avoir plus d'un type d'utilisateur.***
   Si ce message apparaît :
```
msgid "The user cannot have more than one user types."
msgstr "L'utilisateur ne peut pas avoir plus d'un type d'utilisateur."
```
Il faut rechercher les groupes de type d’utilisateurs :
```
thomas-electronics15=# select id,name from res\_groups where id in (9, 10, 1);

` `id |     name      

----+---------------

`  `9 | Portal

` `10 | Public

`  `1 | Internal User
```

Et rechercher si un utilisateur est dans 2 groupes à la fois :
```
select \* from res\_groups\_users\_rel where gid IN (9, 10, 1) order by uid,gid;
```
Si c’est le cas, il faut l’enlever des groupes en trop :
```
delete from res\_groups\_users\_rel where gid=10;
1. # ***Impossible d’afficher une commande après l’avoir créée manuellement***
   Cela est lié à la mauvaise migration des emplacements des articles résolu ci-dessous
1. # ***Erreur en affichant la liste des articles ou un article en particulier***
   Ce message apparait:  

`  `loc\_domain.append(('location\_id.parent\_path', '=like', location.parent\_path + '%'))

TypeError: unsupported operand type(s) for +: 'bool' and 'str'
```

Pour résoudre cela, il faut migrer correctement les entrepôts et emplacements de stocks :
```
MigrationTable(db\_src,db\_dst,'stock\_location')
default={'manufacture\_steps': 'mrp\_one\_step'}
MigrationTable(db\_src,db\_dst,'stock\_warehouse', default=default)
SQL="""

`    `update stock\_location set parent\_path=name;

`    `update product\_category set parent\_path='/' where parent\_path is null;

`    `update product\_category set complete\_name=name;

`    `update stock\_warehouse set active='t';

"""

cr\_dst.execute(SQL)

cnx\_dst.commit()

MigrationIrProperty(db\_src,db\_dst,'product.template', 'property\_stock\_production')

MigrationIrProperty(db\_src,db\_dst,'product.template', 'property\_stock\_inventory')

```











# ***Importation du stock***
   L’importation du stock est complexe, car la gestion des emplacements et des routes a beaucoup changé. Il y a aussi la table stock\_rule en plus :

```
\# \*\* stock\_quant \*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

\# TODO : Je ne migre pas les emplacements, car c'est très complexe, car il y a la table stock\_rule en plus

\# mais du coup, je dois changer le champ location\_id dans stock\_quant

default={'reserved\_quantity': 0}

rename={'qty': 'quantity'}

MigrationTable(db\_src,db\_dst,'stock\_quant', default=default, rename=rename, where="location\_id=12")

SQL="""

`    `update stock\_quant set location\_id=8;

`    `update stock\_quant set inventory\_date=in\_date;

`    `update stock\_quant set inventory\_quantity\_set='f';

"""

cr\_dst.execute(SQL)

cnx\_dst.commit()

\# \*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*
|<p>*nfoSaône - 1 rue Jean Moulin 21110 Pluvault - http://www.infosaone.com*</p><p>*Tony Galmiche - Tél : 03 80 47 93 81 - Portable : 06 19 43 39 31 - Courriel :  tony.galmiche@infosaone.com*</p>|*age 5/5**|
| :- | :-: |

```