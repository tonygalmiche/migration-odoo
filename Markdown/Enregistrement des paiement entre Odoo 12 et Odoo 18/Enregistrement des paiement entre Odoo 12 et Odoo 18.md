Enregistrement des paiement entre Odoo 12 et Odoo 18
# ***Fonctionnement du règlement d’une facture***
   Le bouton « Paiements » en haut de la facture permet d’arriver sur le paiement BNK1/2025/00005 :

   ![](Aspose.Words.83ea8e9e-03de-4ebb-944e-633c22389ebf.001.png)

   Le widget de paiement en bas à droite permet d'arriver également sur ce même paiement BNK1/2025/00005 :

   ![](Aspose.Words.83ea8e9e-03de-4ebb-944e-633c22389ebf.002.png)

   Depuis ce paiement un bouton en haut permet de retourner à la facture et un deuxième bouton 'Pièce comptable' permet d’accéder à la facture du paiement (account.move) BNK1/2025/00005 :

   ![](Aspose.Words.83ea8e9e-03de-4ebb-944e-633c22389ebf.003.png)




# ***Facture client et facture du paiement en base de données :***

```
   select id,name,create\_date,write\_date from account\_move;
      id      |      name           |        create_date        |         write_date         
   --------+-----------------+----------------------------+----------------------------
   **658328** | **FAC/2025/00005**  | 2025-04-07 06:35:59.398823 | 2025-04-07 06:37:25.469433    => Facture client
   **658329** | **BNK1/2025/00005** | 2025-04-07 06:37:25.469433 | 2025-04-07 06:37:25.469433    => Facture du paiement
```

   # ***Paiement en base de données***
   Le champ `move_id` contient le lien entre le paiement et la facture du paiement
```
   opta-s18=# select  id,move_id,name,memo,create_date from account_payment;
   id         | **move_id** |      name       |      memo      |        create_date         
   --------+---------+-----------------+----------------+----------------------------
   **325264** |  **658329** | BNK1/2025/00005 | FAC/2025/00005 | 2025-04-07 06:37:25.469433
```

# ***Crédits en circulation***
   Si je repasse en brouillon cette facture et que je la valide, les 2 boutons en haut sont toujours opérationnels, mais le widget du paiement en bas n'est plus relié à la facture et le message 'Crédits en circulation' apparaît :

   ![](Aspose.Words.83ea8e9e-03de-4ebb-944e-633c22389ebf.004.png)

   En cliquant sur  `Ajouter`, cela réactive le widget

   La différence entre ces 2 états est le champ `is_reconciled` dans `account_payment` et il y a le champ `payment_state` de la facture qui change

# ***Lien entre la facture client et le paiement***
```
   account_invoice_payment_rel => account_move__account_payment
   opta-s18=# select * from account_move__account_payment
   Lien entre la facure du client et le réglement
   invoice_id  | payment_id
   ------------+-----------
   **658328**  | **325264**
```


# ***Analyse de la facture 2024-00315 (id=657951)***
   Le bouton `Paiement` en haut permet bien d’arriver sur la paiement `CUST.IN/2024/0344` (id=325132)
   Le widget du paiement en bas également. La table est correcte :
```
   invoice_id | payment_id
   -----------+------------
   **657951** |     325132
```

   Dans la facture du paiement le champ '**memo**' n'est pas renseigné.
   Mais c'est surtout le champ `move_id` qui pose problème car il est relié à la facture client et non pas à la facture du paiement.
   Du coup, le bouton `Pièce comptable` en haut du paiement affiche la facture client et non pas la facture du paiement.
```
   opta-s18=# select  id,move\_id,name,memo,create\_date from account\_payment where id=325132;
   id      | move_id     |       name        | memo |        create_date        
   --------+-------------+-------------------+------+---------------------------
   325132  |  **657951** | CUST.IN/2024/0344 |      | 2024-12-17 07:56:31.80769
```
   Dans Odoo 12, j'ai le lien entre le paiement et la facture du paiement dans la table `account_move_line`
```
   opta-s12=# select id,payment_id,move_id from account_move_line where id=3027041;
   id       | payment_id | move_id
   ---------+------------+---------
   3027041  |     325132 |  658026
```

   Après avoir refait le lien correctement entre le paiement et la facture de paiement, le paiement permet bien d’accéder à sa facture.
   Mais le widget en bas n'affiche pas `Crédits en circulation` et le lien est perdu une fois la facture passée en brouillon et validée à nouveau.
   Tout est normal dans la facture client :
```
   opta-s18=# select id,name,origin_payment_id, payment_state, payment_reference from account_move where id=657527;
        id   |    name    | origin_payment_id | payment_state | payment_reference
   ---------+------------+-------------------+---------------+-------------------
   ` `657527 | 2024-00125 |                   | not_paid      | 2024-00125
```

   Tout est normal dans le lien entre la facture client et le  paiement
```
   opta-s18=# select * from account_move__account_payment where invoice_id=657527;
   invoice_id  | payment_id
   ------------+------------
   657527      | 324924
```

   C'est ce champ  `widget{} qui ne s'affiche pas
```
   <field name="invoice_payments_widget" colspan="2" nolabel="1" widget="payment"/>
   def _compute_payments_widget_reconciled_info(self):
   cf la fonction _get_all_reconciled_invoice_partials
```

   Le problème vient de ces tables :
```
   account.full.reconcile
   acount.partial.reconcile
```

   # ***Fonctionnement du lien entre la facture et le paiement***
   La table `account_partial_reconcile` fait le lien entre les lignes de la facture client (`debit_move_id`) et la facture du paiement (`credit_move_id`) et la table `account_full_reconcile`
```
   opta-s18=# select id,move_id from account_move_line where move_id in (658329,658328) order by id;
   id          | move_id
   ------------+---------
   3028327     |  658328
   **3028329** |  658328
   3028330     |  658329
   **3028331** |  658329
   3028335     |  658328

   opta-s18=# select  id,debit_move_id,credit_move_id,full_reconcile_id,write_date  from account_partial_reconcile  order by id desc limit 1;
 ```  
   id        | debit_move_id | credit_move_id | full_reconcile_id |        write_date         
   ----------+---------------+----------------+-------------------+---------------------------
   325331    |   **3028329** |    **3028331** |        **325322** | 2025-04-07 07:50:47.30836
   opta-s18=# select \* from account\_full\_reconcile order by id desc limit 5;
   `   `id   | exchange\_move\_id | create\_uid | write\_uid |        create\_date         |         write\_date         
   --------+------------------+------------+-----------+----------------------------+----------------------------
   ` `**325322** |                  |          2 |         2 | 2025-04-07 07:50:47.30836  | 2025-04-07 07:50:47.30836
```

   Le problème vient du champ 'full\_reconile\_id qui n'est pas renseigné :

   opta-s18=# select id,move\_id,full\_reconcile\_id from account\_move\_line where move\_id in (658329,658328) order by id;

   `   `id    | move\_id | full\_reconcile\_id

   ---------+---------+-------------------

   ` `3028327 |  658328 |                  

   ` `3028329 |  658328 |            325322

   ` `3028330 |  658329 |                  

   ` `3028331 |  658329 |            325322

   ` `3028335 |  658328 |                  

   opta-s18=# select id,move\_id,full\_reconcile\_id from account\_move\_line where move\_id in (657527,657570) order by id;

   `   `id    | move\_id | full\_reconcile\_id

   ---------+---------+-------------------

   ` `3025018 |  657527 |                  

   ` `3025019 |  657527 |                  

   ` `3025147 |  657570 |                  

   ` `3025148 |  657570 |                  

   Le champ full\_reconcile\_id est bien migré, mais en passant la facture en brouillon, celui-ci est effacé ce qui est normal

   C'est également le cas avec une facture créée manuellement qui fonctionne.

   Sur une facture qui fonctionne, ce champ n'est pas remis par défaut mail le widget affiche 'Crédits en circulation' permettant d'associé à nouveau le paiment à la facture

   Il faut donc regarder le fonctionnement ce ce champ et de la fonction « **\_compute\_payments\_widget\_to\_reconcile\_info** »

   <field

   `    `name="invoice\_outstanding\_credits\_debits\_widget" class="oe\_invoice\_outstanding\_credits\_debits py-3" colspan="2" nolabel="1"

   `    `widget="payment"

   `    `invisible="state != 'posted' or not invoice\_has\_outstanding"/>

   Domain pour la recherche des factures dans \_compute\_payments\_widget\_to\_reconcile\_info

   [   ('account\_id', 'in', [281]), ('parent\_state', '=', 'posted'),

   `    `('partner\_id', '=', False),

   `    `('reconciled', '=', False), '|', ('amount\_residual', '!=', 0.0), ('amount\_residual\_currency', '!=', 0.0), ('balance', '<', 0.0)

   ]

   Le problème vient du champ 'partner\_id qui est à False

   Cela vient du champ **commercial\_partner\_id** qui n'est pas renseigné car il existe dans account\_invoice, mais pas dans account\_move

   Cela vient aussi du champ **parent\_state** qui n'est pas renseigné dans account\_move\_line

   update account\_move\_line set parent\_state=(select am.state from account\_move am where move\_id=am.id limit 1)


|<p>*nfoSaône - 1 rue Jean Moulin 21110 Pluvault - http://www.infosaone.com*</p><p>*Tony Galmiche - Tél : 03 80 47 93 81 - Portable : 06 19 43 39 31 - Courriel :  tony.galmiche@infosaone.com*</p>|*age 5/5**|
| :- | :-: |
