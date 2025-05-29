# Migration Odoo Opta-S de 12 vers 18

## A Faire
* Revoir les domain mis en commentaire dans les models
* Revoir le champ active_id / context dans les vues XML
* Rapport PDF


# Si je crée un utilisateur ensuite, j'ai plein de problèmes d’intégrité ce qui est normal : 
Dans ce cas, il faut repartir sur une base viergeou vider ces tables et probablement d'autres : 
```
delete from res_users_log ;
delete from change_password_user;
delete from res_device_log
delete from res_users_settings where user_id not in (select id from res_users);
delete from discuss_channel_member ;
```


## Le widget de règlement en bas à droite affiche un account.move et non pas un account.payment
De plus, sur le règlement, il manque le bouton en haut pour accéder à la pièce comptable même sur les nouvelles factures
Il fallait renseigner le champ `default_account_id` dans `account_journal`


## Manque le widget pour le paiement en bas à droite de la facture
cf ```account_partial_reconcile```


## Something went wrong... If you really are stuck, share the report with your friendly support service 
Après avoir activé la migration de account_partial_reconcile, j'ai eu ce message.
Pour le résoudre, il fallait initialiser ces champs dans ```account_partial_reconcile```:
```debit_currency_id, credit_currency_id,debit_amount_currency et  credit_amount_currency```


## L'écriture n'est pas équilibrée.
J'ai eu ce message en voulant remettre en brouillon la facture 2025-00061 (2025-00061/61)
Et en voulant payer cette même facture, j'ai eu ce message :
```Vous ne pouvez pas enregistrer un paiement car il n'y a plus rien à payer sur les écritures comptables sélectionnées.```
Pour résoudre cela, il fallait corriger la migration du champ ```display_type``` de ```account_move_line```



## Lien entre les factures et les règlements
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


## Mode de paiement invalide
En voulant afficher la facture reliée au réglement. Solution : 
```
rename={
    "payment_method_id": "payment_method_line_id",
}
```


## Le compte 512001 Banque ne permet pas le lettrage
Modifiez sa configuration pour pouvoir lettrer des écritures. Solution : 
```
cr_dst.execute("update account_account set reconcile=true where code_store->>'1' like '512001%'") 
```


## Erreur, un partenaire ne peut pas suivre deux fois le même objet
Message en validant une facture. Solution : 
```
MigrationTable(db_src,db_dst,'mail_followers', where="partner_id is not null")
```

## Mettre le compte 512xxx par défaut
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


## Montant du à 0 
Une facture est considérée comme réglée dés sa validation ce qui n'est pas normal 
=> Montant du à 0 
=> Il faut configurer property_account_payable_id et property_account_receivable_id dans res_partner
=> Cela ne fonctionne pas avec la facture 2025-00081. Mais si je la duplique, cela fonctionne

Pour résoudre ce problème, il faut initialiser le champ 'parnet_id' dans account_move_line:
```opta-s18=# update account_move_line aml set partner_id=(select partner_id from account_move where id=aml.move_id) where partner_id is not null;```




## def create
```
2025-03-17 13:47:38,304 1725 WARNING opta-s18 py.warnings: /opt/odoo18/odoo/api.py:466: DeprecationWarning: 
The model odoo.addons.is_opta_s18.models.is_frais is not overriding the create method in batch
```

## Since 17.0, the "attrs" and "states" attributes are no longer used.
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

## Deprecated call to decimal_precision.get_precision(<application>), use digits=<application> instead 
```
digits=(16, 4),
digits='Product Price'
```

## XML
```
tree => list
<graph type="bar" orientation="vertical" stacked="False"> => remove orientation => <graph type="bar" stacked="False">
```

## Autres points à revoir
```
context="{'default_activite_id': active_id}"  => A revoir
<div class="oe_chatter"> =>  <chatter open_attachments="True"/>
```


## INSERT INTO ir_model_data (module,name,model,res_id,noupdate)\n            
Message lors de l'instalation du module sur base vierges : 
```
  2025-04-26 08:43:59,849 7736 ERROR sgp18 odoo.sql_db: bad query: b"\n            
  INSERT INTO ir_model_data (module,name,model,res_id,noupdate)\n            
  ERROR: ERREUR:  ON CONFLICT DO UPDATE command cannot affect row a second time
  ASTUCE : S'assure qu'aucune ligne proposée à l'insertion dans la même commande n'a de valeurs contraintes dupliquées.
```
Il n'y a pas de problème lors de la mise à jour du module => Ne pas en tenir compte



## Problèmes avec wkhtmltopdf
Le PDF sort avec une page blanche ou le pied de page n'apparait pas
En voulant changer de module PDF dans la configuration tout est blanc
Message dans les logs : 
```
2025-04-27 07:27:51,990 1163 WARNING opta-s18 odoo.addons.base.models.ir_actions_report: wkhtmltopdf: Exit with code 1 due to network error: ProtocolUnknownError
```

A faire en cas de problème:
* Ne pas récupérer les pièces jointes de la base vierge avec rsync => Cela n’est plus necessaire
* Ne pas insérer l'attachment res.company.scss => Apparemment, il faut tout de même le faire
* Mettre à jour manuellement le module 'web' pour remettre en place les attachment des feuilles de styles
* Changer le modèle dans la confiugration et enregistrer les changements
* Redémarrer Odoo
* Rafraîchir le navigateur
* Ajouter le nouveau paramètre `report.url` avec `http://127.0.0.1:8069`
* Passer en mode développeur avec les assets
* Sortir du mode développeur pour arriver à afficher le pied de page




## Problème pour accéder aux pièces jointes

Message en ouvrant une affaire avec des pièces jointes : 
```
Désolé, TATU Caroline (id=5777) n'a pas d'accès 'lire' à :
- Pièce jointe (ir.attachment)
Oups ! On dirait que vous êtes tombé sur des enregistrements top secrets.
La faute aux règles suivantes :
```

Aucun règle n'est indiquée dans le message ce qui est curieux et en après vérification, il n'y a aucune règle qui pose problème

Ce problème apparait uniquement si le tchat est activié dans le model et il vient de cette fonction Python dans `ir.attachment`
```python
@api.model

def check(self, mode, values=None): 
```

Et de ces lignes en particulier:
```python
if not res_id and create_uid != self.env.uid:
    raise AccessError(_("Sorry, you are not allowed to access this document."))
```

Donc si le res_id n'est pas renseigné dans le `ir.attachment` et que le create_uid est différent de l'utilisateur, cela bloque

La première solution simple mais non sécurisé est de passer les pièces jointes en public
```update ir_attachment set public=True```

La deuxième est de revoir le script de migration pour renseigner le `res_id` dans le cas des champ `Many2many` comme celui-ci:
```python 
proposition_ids = fields.Many2many('ir.attachment', 'is_affaire_propositions_rel', 'doc_id', 'file_id', 'Propositions commerciales')
```

cf `init_res_id_ir_attachment_Many2many` pour résoudre ce problème


