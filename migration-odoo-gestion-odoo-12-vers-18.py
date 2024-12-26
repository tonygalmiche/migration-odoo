#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#TODO : 
# Manque les affaires sur les factures
# Pb avec les codes comptable des taxes sur les factures (445x)
# account_payment
# Pieces joints
# Actviviés (serveur, factures et parnter)
# Menu CRM / Facture à revoir (context en création)
# PDF des factures à faire
# Désactvier l'apercu de la facture dans la vue PDF
# Mettre les activités en bas si le module communiatire existe



#** Paramètres ****************************************************************
db_src = "gestion-odoo12"
db_dst = "gestion-odoo18"
#******************************************************************************

cnx,cr=GetCR(db_src)

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** purge des tests **********************************************************
SQL="""
    delete from account_partial_reconcile ;
    delete from account_move;
    delete from mail_followers;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** res_partner ***************************************************************
default={
    "autopost_bills": "ask",
}
MigrationTable(db_src,db_dst,'res_partner', default=default)
SQL="UPDATE res_partner set complete_name=name"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** ir_default ****************************************************************
SetDefaultValue(db_dst, 'res.partner', 'property_account_payable_id'   , '401100')
SetDefaultValue(db_dst, 'res.partner', 'property_account_receivable_id', '411100')
#******************************************************************************






#sys.exit()


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
    "sale_line_warn": "no-message",
}
MigrationTable(db_src,db_dst,'product_template',text2jsonb=True, default=default)
MigrationTable(db_src,db_dst,'product_product')
property_account_income_id  = JsonAccountCode2Id(cr_dst,'706000')
set_json_property(cr_dst,cnx_dst,'product_template', 1, 'property_account_income_id' , 1, property_account_income_id)
property_account_income_id  = JsonAccountCode2Id(cr_dst,'706100')
set_json_property(cr_dst,cnx_dst,'product_template', 2, 'property_account_income_id' , 1, property_account_income_id)
#******************************************************************************



  
# ** Tables diverses **********************************************************
tables=[
    "is_affaire",                                         
    "is_serveur",                                         
    "is_service",                                         
    "is_systeme",                                         
    "is_type_vps",      
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
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


# selection=[
#     ("asset_receivable", "Receivable"),
#     ("asset_cash", "Bank and Cash"),
#     ("asset_current", "Current Assets"),
#     ("asset_non_current", "Non-current Assets"),
#     ("asset_prepayments", "Prepayments"),
#     ("asset_fixed", "Fixed Assets"),
#     ("liability_payable", "Payable"),
#     ("liability_credit_card", "Credit Card"),
#     ("liability_current", "Current Liabilities"),
#     ("liability_non_current", "Non-current Liabilities"),
#     ("equity", "Equity"),
#     ("equity_unaffected", "Current Year Earnings"),
#     ("income", "Income"),
#     ("income_other", "Other Income"),
#     ("expense", "Expenses"),
#     ("expense_depreciation", "Depreciation"),
#     ("expense_direct_cost", "Cost of Revenue"),
#     ("off_balance", "Off-Balance Sheet"),
# ],



#** account_payment *********************************************************
default={
    "company_id": 1,
}
rename={
    'payment_date': 'date'
}
MigrationTable(db_src,db_dst,'account_payment', default=default, rename=rename)
SQL="UPDATE res_partner set complete_name=name"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************





#** account_move_line *********************************************************

MigrationTable(db_src,db_dst,'account_full_reconcile')
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
    'display_type': 'product',
}
rename={}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)
#******************************************************************************










# # Recherche du compte 411200 pour le reglement ci-dessous *********************
# SQL="select id from account_account where code='411100'"
# destination_account_id=False
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     destination_account_id = row["id"]
# if not destination_account_id:
#     print("Compte 411100 non trouvé !")
#     sys.exit()
#  #******************************************************************************



# #** account_payment ***********************************************************
# cr_dst.execute("DELETE FROM account_payment")
# cnx_dst.commit()
# SQL="""
#     select am.id,am.name, l.credit,a2.code,am.partner_id
#     from account_move am join account_move_line l on am.id=l.move_id join account_journal aj on am.journal_id=aj.id 
#                          join account_account a2 on l.account_id=a2.id  
#     -- where aj.type='bank' and a2.code like '4%' ;
# """
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     debit = row["credit"]
#     SQL="""
#     INSERT INTO account_payment (move_id, is_reconciled, is_matched, is_internal_transfer, payment_method_id, amount, payment_type, partner_type, currency_id, partner_id, destination_account_id)
#     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
#     """
#     cr_dst.execute(SQL,[row['id'],True,False,False,1,debit,'inbound','customer',1,row["partner_id"],destination_account_id])
# cnx_dst.commit()

#******************************************************************************








#** account_invoice_line => account_move **************************************
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
        ai.amount_untaxed_signed,
        ai.amount_tax,
        ai.amount_total,
        ai.residual,
        ai.user_id,
        ai.fiscal_position_id,
        ai.name move_name,
        ai.origin,
        ai.payment_term_id
    from account_invoice ai inner join res_partner rp on ai.partner_id=rp.id 
    order by ai.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
nb=len(rows)
ct=0
for row in rows:
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
                invoice_payment_term_id=%s
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
            row['amount_untaxed_signed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['user_id'],
            row['fiscal_position_id'],
            row['origin'],
            row['payment_term_id'],
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
            order by ail.id
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
    update account_move set currency_id=(select currency_id from res_company limit 1);
    update account_move_line set currency_id=(select currency_id from res_company limit 1);
    update account_move_line set company_currency_id=(select currency_id from res_company limit 1);
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************




#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""
    update account_move_line set display_type='payment_term' 
        where account_id in (select id from account_account where account_type in ('asset_receivable', 'liability_payable'));
    update account_move_line set display_type='tax' where tax_line_id is not null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************
