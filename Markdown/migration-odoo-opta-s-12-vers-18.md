Migration Odoo Opta-S de 12 vers 18
====

A Faire
===

* Documenter les modifications éffectuées (points ci-dessous)
* Facturation à faire fonctionner
* Revoir les domain mis en commentaire dans les models
* Revoir le champ active_id / context dans les vues XML
* Rapport PDF
* Migrer les données
* Mettre un fond gris clair sur les champs et gris clair foncé sur les champs obligaoire



def create
===
```
2025-03-17 13:47:38,304 1725 WARNING opta-s18 py.warnings: /opt/odoo18/odoo/api.py:466: DeprecationWarning: 
The model odoo.addons.is_opta_s18.models.is_frais is not overriding the create method in batch
```

Since 17.0, the "attrs" and "states" attributes are no longer used.
===
Exemples pour remplacer states : 
```
invisible="state not in ['done', 'cancel']" 
readonly="state in ['ready', 'waiting']"
```
Exemples pour remplacer attr : 
```
attrs à remplacer par : 
invisible="is_type_intervenant != 'consultant'"
required="is_type_intervenant == 'consultant'"
```

Deprecated call to decimal_precision.get_precision(<application>), use digits=<application> instead 
===
```
digits=(16, 4),
digits='Product Price'
```

XML
===
```
tree => list
<graph type="bar" orientation="vertical" stacked="False"> => remove orientation => <graph type="bar" stacked="False">
```

Autres points à revoir
===
```
context="{'default_activite_id': active_id}"  => A revoir
<div class="oe_chatter"> =>  <chatter open_attachments="True"/>
```

