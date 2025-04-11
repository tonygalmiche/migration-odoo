#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os

#** Paramètres ****************************************************************
db_src = "opta-s12"
db_dst = "opta-s18"
#******************************************************************************

cnx,cr=GetCR(db_src)
cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)
debut=datetime.now()
debut = Log(debut, "Début migration (Prévoir 2mn)")


#TODO:

#- Documenter le focntionnemnt des regelement et du raprochement des factues dans Odoo 18
#- Finaliser la migration des facutres suite à la docuementation sur les raprochement et refaire une migration complète
#- Vérfier tous les champs manqautat dans les factures et lignes de facture
#- Si je passe en brouillon et que je vlaide une facure migrée payée, elle reste bien en payée mis son regelmen en bas à droite dispararait
#- Il manque les champs persnalisés des factures
#- Dans la vue liste des facues, les montants sont à 0
#- Voir le sens des avoir (postiif ou nagtif)
#- Compteur
#- mail_mail et mail_message à revoir
#- ir_filters
#- Pieces jointes et liens entre les différentes tables et les pieces jointes
#- Comparer le montant totla des factures avant et après migration
#- Comparer toutes les tables
#- Faire le controle d'intégrité de la base de donnée



# Tentativ de reglement sur la facture 2025-00011
#Vous ne pouvez pas enregistrer un paiement car il n'y a plus rien à payer sur les écritures comptables sélectionnées.


# odoo@bookworm:/media/sf_dev_odoo$ cat migration-odoo/controle-integrite-bdd.sql | psql opta-s18
# ERREUR:  une instruction insert ou update sur la table « account_payment_register_move_line_rel » viole la contrainte de clé
# étrangère « account_payment_register_move_line_rel_line_id_fkey »
# DÉTAIL : La clé (line_id)=(3028300) n'est pas présente dans la table « account_move_line ».
# CONTEXTE : instruction SQL « UPDATE pg_constraint SET convalidated=false WHERE conname = 'account_payment_register_move_line_rel_line_id_fkey'; ALTER TABLE account_payment_register_move_line_rel VALIDATE CONSTRAINT account_payment_register_move_line_rel_line_id_fkey; »
# fonction PL/pgSQL inline_code_block, ligne 22 à EXECUTE
# odoo@bookworm:/media/sf_dev_odoo$ 




# opta-s12=# select * from account_invoice_payment_rel limit 5 ;
#  payment_id | invoice_id 
# ------------+------------
#      232057 |     320900
#      232059 |     320902
#      232070 |     320913
#      232072 |     320915
#      232074 |     320917
# (5 lignes)






# Dans la facture du regelment le champ 'memo' n'est pas renseigné
# Mais c'est surtout le champ 'move_id' qui pose prolbème car il est relié à la facture client et non pas à la facture du regkement : 
# => Du coup, le bouton 'Piece comptable' en haut du regelment affiche la factue client et non pas la facture du regelement 
# opta-s18=# select  id,move_id,name,memo,create_date from account_payment where id=325132;
#    id   | move_id |       name        | memo |        create_date        
# --------+---------+-------------------+------+---------------------------
#  325132 |  657951 | CUST.IN/2024/0344 |      | 2024-12-17 07:56:31.80769



# Dans Odoo 12, j'ai le lien entre le reglement et la facture du reglement dans la table account_move_line
# opta-s12=# select id,payment_id,move_id from account_move_line where id=3027041;
#    id    | payment_id | move_id 
# ---------+------------+---------
#  3027041 |     325132 |  658026
# (1 ligne)



#** Lien entre les réglements et les factures de réglements *******************
SQL="SELECT distinct payment_id,move_id FROM account_move_line WHERE payment_id is not null"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:   
    print(row['payment_id'], row['move_id']) 
    SQL="UPDATE account_payment SET move_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['move_id'],row['payment_id']])
cnx_dst.commit()
#******************************************************************************

sys.exit()


#** account_payment : recherche move_id ***************************************
SQL="""
    SELECT id,name,default_credit_account_id,default_debit_account_id
    FROM account_journal
    order by name
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:   
    print(row['name']) 
    default_account_id = row['default_credit_account_id'] or row['default_debit_account_id']
    SQL="UPDATE account_journal SET default_account_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[default_account_id,row['id']])
cnx_dst.commit()
#******************************************************************************


# pfp18=# select id,name->>'fr_FR',default_account_id,suspense_account_id,profit_account_id,loss_account_id,bank_account_id from account_journal;
#  id |        ?column?         | default_account_id | suspense_account_id | profit_account_id | loss_account_id | bank_account_id 
# ----+-------------------------+--------------------+---------------------+-------------------+-----------------+-----------------
#   1 | Factures clients        |                567 |                     |                   |                 |                
#   2 | Factures fournisseurs   |                394 |                     |                   |                 |                
#   3 | Opérations diverses     |                    |                     |                   |                 |                
#   4 | Différence de change    |                    |                     |                   |                 |                
#   5 | TVA sur encaissements   |                    |                     |                   |                 |                
#   6 | Banque                  |                649 |                 312 |               651 |             652 |                
#   7 | Espèces                 |                650 |                 312 |               651 |             652 |                
#   8 | Valorisation des stocks |                    |                     |                   |                 |                
# (8 lignes)




sys.exit()



#** account_payment : recherche move_id ***************************************
SQL="""
    SELECT ai.move_id,rel.payment_id
    FROM account_invoice_payment_rel rel join account_invoice ai on rel.invoice_id=ai.id
    order by ai.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:    
    SQL="UPDATE account_payment SET move_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['move_id'],row['payment_id']])
cnx_dst.commit()
#******************************************************************************





sys.exit()



#** res_company ***************************************************************
MigrationDonneesTable(db_src,db_dst,'res_company')
#******************************************************************************



#** ir_default ****************************************************************
SetDefaultValue(db_dst, 'res.partner', 'property_account_payable_id'   , '401000')
SetDefaultValue(db_dst, 'res.partner', 'property_account_receivable_id', '411000')
#******************************************************************************


#** res_partner ***************************************************************
MigrationTable(db_src,db_dst,'res_partner_title',text2jsonb=True)
default={
    'autopost_bills': 'ask',
}
MigrationTable(db_src,db_dst,'res_partner',text2jsonb=True,default=default)
#******************************************************************************






#** res_users *****************************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** res_currency ***************************************************************
MigrationTable(db_src,db_dst,'res_currency',text2jsonb=True)
SQL="update res_currency set full_name=currency_unit_label->>'fr_FR'"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_journal ***********************************************************
table="account_journal"
rename={
#    'currency'   : 'currency_id',
#    'sequence_id': 'sequence',
}
default={
#    'active'                 : True,
    'invoice_reference_type' :'invoice',
    'invoice_reference_model': 'odoo',
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default,text2jsonb=True)
#******************************************************************************


# #** Correction champ 'type' dans account_journal ******************************
# journal_type={
#     'sale'           : 'sale',
#     'sale_refund'    : 'sale',
#     'purchase'       : 'purchase',
#     'purchase_refund': 'purchase',
#     'cash'           : 'cash',
#     'bank'           : 'bank',
#     'general'        : 'general',
#     'situation'      : 'general',
# }
# SQL="select id,type from account_journal"
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     type8  = row["type"]         # Champ type dans Odoo 8
#     type16 = journal_type[type8] # Champ type dans Odoo 16
#     SQL="update account_journal set type=%s where id=%s"
#     cr_dst.execute(SQL,[type16, row["id"]])
# cnx_dst.commit()
# #******************************************************************************


#** account_payment *************************************************************
table="account_payment"
default = {
    'company_id': 1
}
rename={
    "payment_date": "date",
    "payment_method_id": "payment_method_line_id",
}
MigrationTable(db_src,db_dst,table,default=default,rename=rename,text2jsonb=True)


table="account_payment_term"
default = {
    # 'sequence': 10
}
MigrationTable(db_src,db_dst,table,default=default,text2jsonb=True)
table="account_payment_term_line"
default = {
    'delay_type': 'days_after',
}
rename={
}
MigrationTable(db_src,db_dst,table,default=default,rename=rename)
SQL="""
    update account_payment set state='canceled' where state='cancelled';
    update account_payment set state='paid' where state='posted';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************

#** Mettre le compte 512xxx pour les réglements par défaut ********************
account_id = AccountCode2Id(cr_src,'512001')
SQL="update ir_model_data set res_id=%s where name='1_account_journal_payment_debit_account_id'" # identifiant externe pour le compte 512xxx
cr_dst.execute(SQL,[account_id])
cnx_dst.commit()
#******************************************************************************

#** Position fiscale **********************************************************
default={
#    'company_id': 1,
}
MigrationTable(db_src,db_dst,'account_fiscal_position',default=default,text2jsonb=True)
MigrationTable(db_src,db_dst,'account_fiscal_position_tax')
MigrationTable(db_src,db_dst,'account_fiscal_position_account')
#******************************************************************************


#** account_account ***********************************************************
table='account_account'
rename={
    'user_type': 'user_type_id',
}
default={
    'account_type': 'income',
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default,text2jsonb=True)
#******************************************************************************

#** account_account : code => code_store **************************************
SQL="SELECT id,code FROM account_account order by code"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    code = row['code']
    val=json.dumps({'1': code})
    SQL="UPDATE account_account SET code_store=%s WHERE id=%s"
    cr_dst.execute(SQL,[val,row['id']])
cnx_dst.commit()
#******************************************************************************

#** account_account : internal_group => account_type **************************
mydict={
    'liability': 'liability_payable',
    'equity'   : 'equity',
    'expense'  : 'expense',
    'income'   : 'income',
    'asset'    : 'asset_receivable',
}
SQL="SELECT id,internal_group FROM account_account order by internal_group"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:    
    internal_group = row['internal_group']
    account_type = mydict.get(internal_group)
    if internal_group:
        SQL="UPDATE account_account SET account_type=%s WHERE id=%s"
        cr_dst.execute(SQL,[account_type,row['id']])
cnx_dst.commit()
#******************************************************************************

#** account_account_res_company_rel *******************************************
SQL="delete from account_account_res_company_rel"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT id FROM account_account"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:  
    SQL="""
        INSERT INTO account_account_res_company_rel (account_account_id,res_company_id)
        VALUES (%s,1)
    """
    cr_dst.execute(SQL,[row['id']])
cnx_dst.commit()
#******************************************************************************

# account_account account_type ************************************************
cr_dst.execute("update account_account set account_type='asset_current' where code_store->>'1' like '445%'") # Dette à court terme pour la TVA
cnx_dst.commit()
#******************************************************************************

#Le compte 512001 Banque ne permet pas le lettrage. Modifiez sa configuration pour pouvoir lettrer des écritures.
cr_dst.execute("update account_account set reconcile=true where code_store->>'1' like '512001%'") 
cnx_dst.commit()
#******************************************************************************



#L'ccès aux facures payées ne fonctione plus depuis que j'ai fait ces requetes
# # account_tag
# SQL="""
#     delete from account_account_account_tag;
#     delete from account_account_tag_account_tax_repartition_line_rel;
#     delete from account_account_tag_account_move_line_rel;
# """
# cr_dst.execute(SQL)
# cnx_dst.commit()
# #******************************************************************************

#** account_tax_group *********************************************************
rename={
    #'type':'amount_type'
}
default={
    "company_id": 1,
}
MigrationTable(db_src,db_dst,'account_tax_group',rename=rename,default=default,text2jsonb=True)
#******************************************************************************

#** account_tax **************************************************************
table='account_tax'
rename={
}
default={
   "country_id"  : 75,
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default,text2jsonb=True)
#******************************************************************************




#** Ajouter les comptes sur les taxes *****************************************    
SQL="""
    ALTER TABLE account_tax_repartition_line DISABLE TRIGGER ALL;
    delete from account_tax_repartition_line;
    ALTER TABLE account_tax_repartition_line ENABLE TRIGGER ALL;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT id, account_id,refund_account_id FROM account_tax"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    id = row["id"]
    SQL="""
        INSERT INTO account_tax_repartition_line (document_type,factor_percent,repartition_type, tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,['invoice',0,'base',id,1,1,False])
    SQL="""
        INSERT INTO account_tax_repartition_line (document_type,factor_percent,repartition_type, tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,['refund',0,'base',id,1,1,False])
    SQL="""
    INSERT INTO account_tax_repartition_line (document_type,factor_percent,repartition_type, tax_id, company_id, sequence, use_in_tax_closing, account_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,['invoice',100,'tax',id,1,1,True,row["account_id"]])
    SQL="""
    INSERT INTO account_tax_repartition_line (document_type,factor_percent,repartition_type, tax_id, company_id, sequence, use_in_tax_closing, account_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,['refund',100,'tax',id,1,1,True,row["refund_account_id"]])
cnx_dst.commit()
#******************************************************************************



















#** account_move_line *********************************************************
debut = Log(debut, "Début account_move_line (40s)")
rename={
    'amount': 'amount_total'
}
default={
    'move_type'  : 'entry',
    'currency_id': 1,
    'auto_post': 'no',
}
MigrationTable(db_src,db_dst,'account_move'     , table_dst='account_move'     , rename=rename,default=default)
default={
    'currency_id': 1,
    'debit': 0,
    'credit': 0,
    'amount_currency': 0,
    'display_type': 'payment_term',
}
rename={}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)
#******************************************************************************


#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""
    update account_move_line set display_type='product' where product_id is not null;
    update account_move_line set display_type='tax' where tax_line_id is not null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************





MigrationTable(db_src,db_dst,'account_full_reconcile')



#** account_invoice_line => account_move **************************************
cnx_src,cr_src=GetCR(db_src)
SQL="""
    SELECT 
        ai.id,
        ai.move_id,
        ai.number,
        ai.date_invoice,
        ai.type,
        rp.name,
        ai.date_due,
        ai.amount_untaxed,
        ai.amount_tax,
        ai.amount_total,
        ai.residual,
        ai.user_id,
        ai.fiscal_position_id,
        ai.name move_name,
        ai.origin,
        ai.payment_term_id,
        ai.state
    from account_invoice ai inner join res_partner rp on ai.partner_id=rp.id 
    order by ai.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
nb=len(rows)
ct=0
for row in rows:
    payment_states={
        'draft': 'draft',
        'cancel': 'cancel',
        'paid': 'paid',
        'open': 'not_paid',
    }
    payment_state = payment_states.get(row['state'], None)


    ct+=1
    move_id = row['move_id']
    if move_id:
        SQL="""
            UPDATE account_move 
            set 
                invoice_date=%s,
                move_type=%s,
                invoice_partner_display_name=%s,
                invoice_date_due=%s,
                amount_untaxed=%s,
                amount_tax=%s,
                amount_total=%s,
                amount_residual=%s,
                amount_untaxed_signed=%s,
                amount_tax_signed=%s,
                amount_total_signed=%s,
                amount_residual_signed=%s,
                invoice_user_id=%s,
                fiscal_position_id=%s,
                invoice_origin=%s,
                invoice_payment_term_id=%s,
                payment_state=%s
            where id=%s
        """
        cr_dst.execute(SQL,(
            row['date_invoice'],
            row['type'],
            row['name'],
            row['date_due'],
            row['amount_untaxed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['amount_untaxed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['user_id'],
            row['fiscal_position_id'],
            row['origin'],
            row['payment_term_id'],
            payment_state,
            move_id
        ))
        SQL="""
            SELECT 
                ail.id,
                ail.product_id,
                ail.name,
                ail.price_unit,
                ail.price_subtotal,
                ail.sequence
            from account_invoice_line ail inner join account_invoice ai on ail.invoice_id=ai.id
            WHERE ai.id="""+str(row['id'])+"""
            order by ail.sequence,ail.id
        """
        cr_src.execute(SQL)
        rows2 = cr_src.fetchall()
        nb2=len(rows2)
        ct2=0
        #Comme il n'y a pas de lien entre account_invoice_line et account_move_line, je considère que les id sont dans le même ordre
        for row2 in rows2:
            SQL="""
                UPDATE account_move_line 
                set 
                    name=%s, 
                    is_account_invoice_line_id=%s,
                    price_unit=%s,
                    price_subtotal=%s,
                    price_total=%s,
                    balance=(debit-credit),
                    amount_currency=(debit-credit),
                    sequence=%s
                WHERE id IN (
                    SELECT id
                    FROM account_move_line
                    WHERE move_id=%s and product_id is not null
                    ORDER BY id
                    LIMIT 1 OFFSET %s
                ) 
            """
            cr_dst.execute(SQL,(
                row2['name'],
                row2['id'],
                row2['price_unit'],
                row2['price_subtotal'],
                row2['price_subtotal'],
                row2['sequence'],
                move_id,
                ct2
            ))
            ct2+=1
cnx_dst.commit()
SQL="""
    update account_move_line set price_unit=(credit-debit) where price_unit is null;
    update account_move_line set balance=(debit-credit) where balance is null;
    update account_move_line set amount_currency=balance where amount_currency=0;
    update account_move_line set price_subtotal=(credit-debit) where price_subtotal is null;
    update account_move_line set price_total=(credit-debit) where price_total is null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


debut = Log(debut, "Fin account_move_line")


#** account_invoice_payment_rel => account_move__account_payment **************
SQL="delete from account_move__account_payment"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="""
    SELECT ai.move_id,rel.payment_id 
    FROM account_invoice ai join account_invoice_payment_rel rel on ai.id=rel.invoice_id 
    ORDER BY ai.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO account_move__account_payment (invoice_id,payment_id)
        VALUES (%s,%s)
    """
    cr_dst.execute(SQL,[row['move_id'],row['payment_id']])
cnx_dst.commit()
#******************************************************************************


#** Migration des taxes sur les factures **************************************
SQL="DELETE FROM account_move_line_account_tax_rel"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT invoice_line_id, tax_id  FROM account_invoice_line_tax order by invoice_line_id"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="SELECT id FROM account_move_line WHERE is_account_invoice_line_id="+str(row['invoice_line_id'])
    cr_dst.execute(SQL)
    rows2 = cr_dst.fetchall()
    for row2 in rows2:
        SQL="""
            INSERT INTO account_move_line_account_tax_rel (account_move_line_id, account_tax_id)
            VALUES (%s,%s)
            ON CONFLICT DO NOTHING
        """
        cr_dst.execute(SQL,[row2['id'],row['tax_id']])
cnx_dst.commit()
#******************************************************************************


#** account_partial_reconcile (widget en bas à droite des factures) ***********
MigrationTable(db_src,db_dst,'account_partial_reconcile')
SQL="""
    update account_partial_reconcile set debit_currency_id=1;
    update account_partial_reconcile set credit_currency_id=1;
    update account_partial_reconcile set debit_amount_currency=amount;
    update account_partial_reconcile set credit_amount_currency=amount;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** product_category **********************************************************
MigrationTable(db_src,db_dst,'product_category')
property_account_income_categ_id  = JsonAccountCode2Id(cr_dst,'707100')
property_account_expense_categ_id = JsonAccountCode2Id(cr_dst,'607100')
SQL="SELECT id FROM product_category"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    set_json_property(cr_dst,cnx_dst,'product_category', row['id'], 'property_account_income_categ_id' , 1, property_account_income_categ_id)
    set_json_property(cr_dst,cnx_dst,'product_category', row['id'], 'property_account_expense_categ_id', 1, property_account_expense_categ_id)
#******************************************************************************


#** product *******************************************************************
default={
    "service_tracking": "no",
}
MigrationTable(db_src,db_dst,'product_template',text2jsonb=True, default=default)
MigrationTable(db_src,db_dst,'product_product')
#******************************************************************************


#** product_template : Compte de revenus et de charges ************************
SQL="SELECT id,name FROM product_template order by name"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    val = getPropertyValue(db_src,'product.template','property_account_income_id',row['id'])
    if val:
        set_json_property(cr_dst,cnx_dst,'product_template', row['id'], 'property_account_income_id' , 1, val)
    val = getPropertyValue(db_src,'product.template','property_account_expense_id',row['id'])
    if val:
        set_json_property(cr_dst,cnx_dst,'product_template', row['id'], 'property_account_expense_id' , 1, val)
#******************************************************************************


#** Taxes à la vente et taxe fournisseur sur les articles *********************
MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')
#******************************************************************************


# ** Tables diverses **********************************************************
tables=[
    'is_activite',
    'is_activite_dynacase_rel',
    'is_activite_pieces_jointes_rel',
    'is_affaire',
    'is_affaire_attachment_rel',
    'is_affaire_consultant_rel',
    'is_affaire_convention_rel',
    'is_affaire_dynacase_rel',
    'is_affaire_forfait_jour',
    'is_affaire_intervenant',
    'is_affaire_phase',
    'is_affaire_phase_activite',
    'is_affaire_propositions_rel',
    'is_affaire_taux_journalier',
    'is_affaire_vendue_par',
    'is_cause',
    'is_compte_banque',
    'is_depense_effectuee_par',
    'is_dynacase',
    'is_export_compta',
    'is_export_compta_ana',
    'is_export_compta_ana_attachment_rel',
    'is_export_compta_ana_ligne',
    'is_export_compta_attachment_rel',
    'is_export_compta_ligne',
    'is_facture_st',
    'is_frais',
    'is_frais_dynacase_rel',
    'is_frais_justificatif_rel',
    'is_frais_lignes',
    'is_secteur',
    'is_suivi_production_affaire',
    'is_suivi_production_affaire_line',
    'is_suivi_temps',
    'is_suivi_temps_simplifie_wizard',
    'is_type_intervention',
    'is_type_offre',
    'is_type_societe',
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


#** is_export_compta_ana_ligne : invoice_id => move_id ************************
SQL="""
    SELECT ana.id,ai.move_id
    FROM is_export_compta_ana_ligne ana join account_invoice ai on ana.invoice_id=ai.id
    order by ana.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:    
    SQL="UPDATE is_export_compta_ana_ligne SET invoice_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['move_id'],row['id']])
cnx_dst.commit()
#******************************************************************************


#** is_activite : invoice_id => move_id ***************************************
SQL="""
    SELECT ia.id,ai.move_id
    FROM is_activite ia join account_invoice ai on ia.invoice_id=ai.id
    order by ia.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:    
    SQL="UPDATE is_activite SET invoice_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['move_id'],row['id']])
cnx_dst.commit()
#******************************************************************************


#** Pièces jointes ************************************************************
MigrationTable(db_src,db_dst,'ir_attachment')
#MigrationTable(db_src,db_dst,'sale_order_piece_jointe_attachment_rel')
#******************************************************************************


#TODO : A revoir

# #** mail **********************************************************************
# MigrationTable(db_src,db_dst,'mail_message_subtype',text2jsonb=True)
# MigrationTable(db_src,db_dst,'mail_alias')
# MigrationTable(db_src,db_dst,'mail_followers', where="partner_id is not null")
# MigrationTable(db_src,db_dst,'mail_followers_mail_message_subtype_rel')
# default={
#     'message_type'  : 'notification',
# }
# MigrationTable(db_src,db_dst,'mail_message', default=default)
# cr_dst.execute("update mail_message set body='' where body is null") # Sans cela, l'affichage de la facture plante
# cnx_dst.commit()
# #******************************************************************************

SQL="""
    update account_journal set alias_id=Null;
    delete from mail_alias;
    delete from mail_followers;
    delete from mail_followers_mail_message_subtype_rel;
    delete from mail_tracking_value;
    delete from discuss_channel_member;
    delete from account_account_tag_account_tax_repartition_line_rel;
"""
cr_dst.execute(SQL)
cnx_dst.commit()




#** Divers ********************************************************************
SQL="""
    delete from account_payment_register_move_line_rel;
"""
cr_dst.execute(SQL,[account_id])
cnx_dst.commit()
#******************************************************************************



debut = Log(debut, "Fin migration")
