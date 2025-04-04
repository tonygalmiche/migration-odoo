Migration Odoo Opta-S de 12 vers 18
====

A Faire
===

* Facturation à faire fonctionner
* Revoir les domain mis en commentaire dans les models
* Revoir le champ active_id / context dans les vues XML
* Rapport PDF
* Migrer les données
* Mettre un fond gris clair sur les champs et gris clair foncé sur les champs obligaoire





Le widget de règlement en bas à droite affiche un account.move et non pas un account.payment
===
De plus, sur le règlement, il manque le bouton en haut pour accéder à la pièce comptable même sur les nouvelles factures
Il fallait renseigner le champ `default_account_id` dans `account_journal`


Manque le widget pour le paiement en bas à droite de la facture
===
cf ```account_partial_reconcile```



Something went wrong... If you really are stuck, share the report with your friendly support service 
===
Après avoir activé la migration de account_partial_reconcile, j'ai eu ce message.
Pour le résoudre, il fallait initialiser ces champs dans ```account_partial_reconcile```:
```debit_currency_id, credit_currency_id,debit_amount_currency et  credit_amount_currency```





L'écriture n'est pas équilibrée.
===
J'ai eu ce message en voulant remettre en brouillon la facture 2025-00061 (2025-00061/61)
Et en voulant payer cette même facture, j'ai eu ce message :
```Vous ne pouvez pas enregistrer un paiement car il n'y a plus rien à payer sur les écritures comptables sélectionnées.```
Pour résoudre cela, il fallait corriger la migration du champ ```display_type``` de ```account_move_line```



Lien entre les factures et les règlements
===
```
Dans Odoo 12
opta-s12=# select * from account_invoice_payment_rel limit 2 ;
 payment_id | invoice_id 
------------+------------
     232057 |     320900
     232059 |     320902

Dans Odoo 18 : 
opta-s18=# select * from account_move__account_payment limit 2 ;
 invoice_id | payment_id 
------------+------------
     658264 |     325243
     658266 |     325244
```


Mode de paiement invalide
===
En voulant afficher la facture reliée au réglement. Solution : 
```
rename={
    "payment_method_id": "payment_method_line_id",
}
```

Le compte 512001 Banque ne permet pas le lettrage
===
Modifiez sa configuration pour pouvoir lettrer des écritures. Solution : 
```
cr_dst.execute("update account_account set reconcile=true where code_store->>'1' like '512001%'") 
```

Erreur, un partenaire ne peut pas suivre deux fois le même objet
===
Message en validant une facture. Solution : 
```
MigrationTable(db_src,db_dst,'mail_followers', where="partner_id is not null")
```

Mettre le compte 512xxx par défaut
===
```
cf _get_outstanding_account et _setup_utility_bank_accounts pour avoir le compte 512xxx
Cela fait appel à l'identifiant account_journal_payment_debit_account_id
Il faut donc modifier le res_id de cet identifiant

select id,res_id,name,module,model from ir_model_data where name like '%account_journal_payment_debit_account_id%';
   id   | res_id |                    name                    | module  |      model      
 -------+--------+--------------------------------------------+---------+-----------------
  34005 |    654 | 1_account_journal_payment_debit_account_id | account | account.account

select id,code_store from account_account where id=654;
  id  |   code_store    
 -----+-----------------
  654 | {"1": "512002"}
```




Montant du à 0 
===
Une facture est considérée comme réglée dés sa validation ce qui n'est pas normal 
=> Montant du à 0 
=> Il faut configurer property_account_payable_id et property_account_receivable_id dans res_partner


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

