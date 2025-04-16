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
debut = Log(debut, "Début migration (Prévoir 6mn)")


#TODO:
#- Compteur
#- mail_mail et mail_message à revoir
#- ir_filters
#- Pieces jointes et liens entre les différentes tables et les pieces jointes
#- Comparer le montant totla des factures avant et après migration
#- Comparer toutes les tables
#- Faire le controle d'intégrité de la base de donnée
#- La connexion avec un utilsateur ne fonctione pas  => res_group à revoir
#- PDF de la facure à faire


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

#** res_users : chatter_position **********************************************
cr_dst.execute("update res_users set chatter_position='bottom'" )
cnx_dst.commit()
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
    update account_move_line set invoice_date=date;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Pour faire fonctionner les paiments ***************************************
SQL="""
    update account_move set always_tax_exigible=false where always_tax_exigible is null;
    update account_move set checked=false where checked is null;
    update account_move set made_sequence_gap=false where made_sequence_gap is null;
    update account_move set posted_before=true where posted_before is null;
    update account_move set is_manually_modified=true where is_manually_modified is null;
    update account_move set quick_edit_total_amount=0 where quick_edit_total_amount is null;
    update account_move set is_storno=false where is_storno is null;
    update account_move set invoice_currency_rate=1 where invoice_currency_rate is null;
    update account_move set amount_untaxed_in_currency_signed=amount_untaxed_signed where amount_untaxed_in_currency_signed is null;
    update account_move set commercial_partner_id=partner_id where commercial_partner_id is null;
    update account_move set amount_total_in_currency_signed=amount_total_signed;

    update account_move_line set amount_residual_currency=amount_residual;
    update account_move_line set parent_state=(select am.state from account_move am where move_id=am.id limit 1);
    update account_move_line aml set partner_id=(select partner_id from account_move where id=aml.move_id) where partner_id is not null;
    update account_move_line set discount=0 where discount is null;
    update account_move_line set discount_amount_currency=0 where discount_amount_currency is null;
    update account_move_line set discount_balance=0 where discount_balance is null;
    update account_move_line set tax_tag_invert=true  where display_type!='payment_term';
    update account_move_line set tax_tag_invert=false where display_type='payment_term';
    update account_move_line set quantity=0, price_unit=0,price_subtotal=0, price_total=0  where display_type!='product';
    update account_move_line set tax_group_id=3 where tax_line_id is not null;    
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Mettre les avoir en négatif ***********************************************
SQL="""
    update account_move set  amount_untaxed_signed=-amount_untaxed where move_type='out_refund';
    update account_move set  amount_untaxed_in_currency_signed=-amount_untaxed where move_type='out_refund';
    update account_move set  amount_total_signed=-amount_total where move_type='out_refund';
    update account_move set  amount_tax_signed=-amount_tax where move_type='out_refund';
    update account_move set  amount_total_in_currency_signed=-amount_total where move_type='out_refund';
    update account_move set  amount_residual_signed=-amount_residual where move_type='out_refund';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_move_line / tax_repartition_line_id *******************************
SQL="""
    update account_move_line set tax_repartition_line_id=(select id 
    from account_tax_repartition_line where tax_id=tax_line_id and repartition_type='tax' limit 1) 
    where tax_line_id is not null
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


debut = Log(debut, "Fin account_move_line")


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


#** Lien entre les réglements et les factures de réglements *******************
SQL="SELECT distinct payment_id,move_id FROM account_move_line WHERE payment_id is not null"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:   
    SQL="UPDATE account_payment SET move_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['move_id'],row['payment_id']])
cnx_dst.commit()
#******************************************************************************


#** account_journal : default_account_id **************************************
SQL="""
    SELECT id,name,default_credit_account_id,default_debit_account_id
    FROM account_journal
    order by name
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:   
    default_account_id = row['default_credit_account_id'] or row['default_debit_account_id']
    SQL="UPDATE account_journal SET default_account_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[default_account_id,row['id']])
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


#** is_account_invoice_activite_rel *******************************************
SQL="delete from is_account_invoice_activite_rel"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT ai.id,ai.move_id,rel.activite_id FROM is_account_invoice_activite_rel rel join account_invoice ai on rel.invoice_id=ai.id"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:  
    #print(row)
    if row['move_id']:
        SQL="""
            INSERT INTO is_account_invoice_activite_rel (invoice_id,activite_id)
            VALUES (%s,%s)
        """
        cr_dst.execute(SQL,[row['move_id'],row['activite_id']])
cnx_dst.commit()
#******************************************************************************


#** account_move_line : champs opta-s *****************************************
SQL="SELECT * FROM account_invoice_line"
cr_src.execute(SQL)
rows = cr_src.fetchall()
champs=['is_dates_intervention','is_activite_id','is_frais_id','is_frais_ligne_id']
for row in rows:
    for champ in champs:
        val = row[champ]
        SQL="UPDATE account_move_line SET "+champ+"=%s WHERE is_account_invoice_line_id=%s"
        cr_dst.execute(SQL,[val,row['id']])
cnx_dst.commit()
#******************************************************************************


#** account_move : champs opta-s **********************************************
SQL="SELECT * FROM account_invoice"
cr_src.execute(SQL)
rows = cr_src.fetchall()
champs=[
    'is_createur_id','is_affaire_id','is_detail_activite','is_phase','is_intervenant','is_prix_unitaire','is_frais',
    'is_detail_frais','is_date_encaissement','is_montant_encaissement','is_code_service','is_ref_engagement'
]
for row in rows:
    for champ in champs:
        val = row[champ]
        SQL="UPDATE account_move SET "+champ+"=%s WHERE id=%s"
        cr_dst.execute(SQL,[val,row['move_id']])
cnx_dst.commit()
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


# #** Wizard création de facture ************************************************
SQL="""
    delete from account_payment_register_move_line_rel;
"""
cr_dst.execute(SQL,[account_id])
cnx_dst.commit()
# #******************************************************************************


#** is_activite : rec_name ***********************************************
SQL="""
    SELECT act.id,act.nature_activite,aff.code_long
    FROM is_activite act join is_affaire aff  on act.affaire_id=aff.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    name="[%s] %s"%(row['code_long'],row['nature_activite'])
    SQL="UPDATE is_activite SET rec_name=%s WHERE id=%s"
    cr_dst.execute(SQL,[name,row['id']])
cnx_dst.commit()
#******************************************************************************


#** is_affaire : rec_name ***********************************************
SQL="""
    SELECT ia.id,ia.code_long,ia.nature_affaire,rp.name 
    FROM is_affaire ia left outer join res_partner rp on ia.partner_id=rp.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    name="[%s] %s (%s)"%(row['code_long'],row['nature_affaire'],row['name'])
    SQL="UPDATE is_affaire SET rec_name=%s WHERE id=%s"
    cr_dst.execute(SQL,[name,row['id']])
cnx_dst.commit()
#******************************************************************************


#** res_partner : complete_name ***********************************************
SQL="SELECT rp1.id,rp1.name,rp2.name as parent_name FROM res_partner rp1 left outer join res_partner rp2 on  rp1.parent_id=rp2.id" 
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    name=row['name'] or ''
    parent_name=row['parent_name']
    if parent_name:
        name="%s, %s"%(parent_name,name)
    SQL="UPDATE res_partner SET complete_name=%s WHERE id=%s"
    cr_dst.execute(SQL,[name,row['id']])
cnx_dst.commit()
#******************************************************************************






debut = Log(debut, "Fin migration")
