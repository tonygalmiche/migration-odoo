# Migration Odoo Clair-SARL de 15 vers 18


## Impossible de trouver un plan comptable pour cette société
En voulant créer une facture, j'ai eu ce message : 
```
Impossible de trouver un plan comptable pour cette société. Il vous faut le configurer.
```

Dans le plan comptable, il n'y a pas les codes. Il faut revoir la migration du champ `code` vers `code_store` : 
```
champ                          type_src                       type_dst
code                           character varying(64)                      
code_store                                                    jsonb                   
```


## Toute écriture comptable sur un compte débiteur doit avoir une date d'échéance et vice versa
Pour cela, il faut revoir la mmigration du champ `internal_group` vers `account_type` dans `account_account`


## Il manque les numéros des paiements (champ name)
Dans Odoo 15, le champ `name` n'existe pas dans account_payment. Il faut le récupérer dans `account_move`


## Le journal n'est pas le bon dans account_payment
Dans Odoo 15, le champ `journal_id` n'existe pas dans account_payment. Il faut le récupérer dans `account_move`


## La date n'est pas la bonne dans account_payment
Dans Odoo 15, le champ `date` n'existe pas dans account_payment. Il faut le récupérer dans `account_move`


## Sociétés incompatibles sur les enregistrements
En voulant enregistrer un paiement:
```
Paiement brouillon” appartient à la société “My Company” et 
Compte en suspens” (outstanding_account_id : "512001 Compte d'attente de la banque") appartient à une autre société.
```
Il faut migrer la table `account_account_res_company_rel`


## La clé (alias_id)=(3) n'est pas présente dans la table « mail_alias »
```
ERREUR:  une instruction insert ou update sur la table « account_journal » viole la contrainte de clé
étrangère « account_journal_alias_id_fkey »
DÉTAIL : La clé (alias_id)=(3) n'est pas présente dans la table « mail_alias ».
```
Solution : 
`update account_journal set alias_id=Null`



## Impossible d’accéder à Odoo après avoir fait le rsync des fichiers
```
FileNotFoundError: [Errno 2] Aucun fichier ou dossier de ce type: '/media/sf_dev_odoo/home/odoo/filestore/clair-sarl18/c3/c3baf128ac0e79ea504e6eb0679066568ba275bd'
```
Cela correspond à ce fichier : 
```
clair-sarl18=# select id,name,url,mimetype, store_fname from ir_attachment where store_fname='c3/c3baf128ac0e79ea504e6eb0679066568ba275bd';
  id  |         name          |                    url                    |        mimetype        |                 store_fname                 
------+-----------------------+-------------------------------------------+------------------------+---------------------------------------------
 8003 | web.assets_web.min.js | /web/assets/bb9ffaa/web.assets_web.min.js | application/javascript | c3/c3baf128ac0e79ea504e6eb0679066568ba275bd
```
Solution : 
`delete from ir_attachment where store_fname='c3/c3baf128ac0e79ea504e6eb0679066568ba275bd'`


## L'accès à certians articles ne fonctionne pas (ex : ARRACHAGE DES RELEVES)
```
File "/opt/odoo18/addons/account/models/account_tax.py", line 1666, in _add_accounting_data_to_base_line_tax_details
    tax_rep = sorted_tax_reps_data[index]
``` 
cf `account_tax_repartition_line`
et `tax_id = row['invoice_tax_id'] or row['refund_tax_id']`



## Impossible de trouver un plan comptable pour cette société. Il vous faut le configurer.
J'ai eu ce message en créant une facture juste après avoir sélectionné le client ou le fournisseur
Le problème vient de ces champs qui ne sont pas renseignés comme valeur par défaut ou dans res_partner
```
rec_account = self.partner_id.property_account_receivable_id
pay_account = self.partner_id.property_account_payable_id
```

Le json_value était à false pour les valeurs par défaut de ces champs : 
```
clair-sarl18=# select * from ir_default where field_id in (4225,4226);
 id | field_id | user_id | company_id | create_uid | write_uid | condition | json_value |      
----+----------+---------+------------+------------+-----------+-----------+------------+
  8 |     4225 |         |          1 |          1 |         1 |           | false      |
  7 |     4226 |         |          1 |          1 |         1 |           | false      |
```


Cette fonction retourne les comptes (account_id) pas défaut en fonction de la localisation fiscale
```
def _get_fr_template_data(self):
    return {
        'code_digits': 6,
        'property_account_receivable_id': 'fr_pcg_recv',
        'property_account_payable_id': 'fr_pcg_pay',
        'property_account_expense_categ_id': 'pcg_607_account',
        'property_account_income_categ_id': 'pcg_707_account',
        'property_account_downpayment_categ_id': 'pcg_4191',
    }
```

Les external id sont enregistrés dans cette table 
```
odoo18=# select id,model,res_id,name from ir_model_data where name like '%fr_pcg_recv%';
  id   |      model      | res_id |       name        
-------+-----------------+--------+-------------------
 33493 | account.account |    231 | 1_fr_pcg_recv
 33494 | account.account |    232 | 1_fr_pcg_recv_pos
```

J'ai résolu ce problème avec ir_default : 
```
SetDefaultValue(db_dst, 'res.partner', 'property_account_payable_id'   , '40110000')
SetDefaultValue(db_dst, 'res.partner', 'property_account_receivable_id', '411101')
```


## Le compte 481600 est de type débiteur, mais est utilisé dans une opération d'achat
En validant une facture : 
Solution : Revoir les comptes dans les `catégories`
