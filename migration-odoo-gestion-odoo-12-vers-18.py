#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#TODO : 
# Documentation a mettre au format md et non pas odt pour faire des rechrches depuis Studio Code


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
    delete from account_account_res_company_rel;
    delete from mail_followers;

    ALTER TABLE account_move_line DISABLE TRIGGER ALL;
    delete from account_move_line;
    ALTER TABLE account_move_line ENABLE TRIGGER ALL;

    ALTER TABLE account_tax_repartition_line DISABLE TRIGGER ALL;
    delete from account_tax_repartition_line;
    ALTER TABLE account_tax_repartition_line ENABLE TRIGGER ALL;

    ALTER TABLE account_account_tag_account_tax_repartition_line_rel DISABLE TRIGGER ALL;
    delete from account_account_tag_account_tax_repartition_line_rel;
    ALTER TABLE account_account_tag_account_tax_repartition_line_rel ENABLE TRIGGER ALL;

    update res_company set account_purchase_tax_id=1;
    update res_company set account_sale_tax_id=2;
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
    #"sale_line_warn": "no-message",
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

#** account_account_res_company_rel *******************************************
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
rename={
    'type':'amount_type'
}
default={
    "tax_group_id": 1,
    "country_id"  : 75,
}
MigrationTable(db_src,db_dst,'account_tax',rename=rename,default=default,text2jsonb=True)
#******************************************************************************

#** Ajouter les comptes sur les taxes *****************************************    
cr_dst.execute("delete from account_tax_repartition_line")
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
    'is_storno': False,
    'always_tax_exigible': False,
    'checked': True,
    'posted_before': True,
    'made_sequence_gap': True,
    'invoice_currency_rate': 1,
}
MigrationTable(db_src,db_dst,'account_move'     , table_dst='account_move'     , rename=rename,default=default)
default={
    'currency_id': 1,
    'debit': 0,
    'credit': 0,
    'amount_currency': 0,
    'display_type': 'product',
    'is_imported': False,
    'tax_tag_invert': False,
}
rename={}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)
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
        ai.payment_term_id,
        ai.state,
        ai.is_affaire_id,
        ai.is_date_paiement
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
    sequence_number = int(row['number'] or '0')
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
                payment_state=%s,
                sequence_number=%s,
                is_affaire_id=%s,
                is_date_paiement=%s
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
            payment_state,
            sequence_number,
            row['is_affaire_id'],
            row['is_date_paiement'],
            move_id
        ))
        SQL="""
            SELECT 
                ail.id,
                ail.product_id,
                ail.name,
                ail.price_unit,
                ail.price_subtotal,
                ail.sequence,
                ai.partner_id,
                ai.state
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
                    is_account_invoice_line_id=%s,
                    price_unit=%s,
                    price_subtotal=%s,
                    price_total=%s,
                    balance=(debit-credit),
                    amount_currency=(debit-credit),
                    sequence=%s,
                    partner_id=%s,
                    parent_state=%s
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
                row2['partner_id'],
                row2['state'],
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
    update account_move_line set currency_id=(select currency_id from res_company limit 1);
    update account_move_line set company_currency_id=(select currency_id from res_company limit 1);
    update account_move_line set amount_residual_currency=amount_residual;
    update account_move_line set invoice_date=date;

    update account_move_line aml set parent_state=(select am.state from account_move am where am.id=aml.move_id); 
    
    update account_move set currency_id=(select currency_id from res_company limit 1);
    update account_move set amount_untaxed_in_currency_signed=amount_untaxed_signed;
    update account_move set amount_total_in_currency_signed=amount_total_signed;
    update account_move set sequence_prefix='';
 
    -- Correction bug sur compte 401/411 des factures de Plastigray
    update account_move_line set account_id=281 where account_id=267;
"""
cr_dst.execute(SQL)
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

#** account_move_line / tax_repartition_line_id *******************************
SQL="""
    update account_move_line set tax_repartition_line_id=(select id 
    from account_tax_repartition_line where tax_id=tax_line_id and repartition_type='tax' limit 1) 
    where tax_line_id is not null
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

#** account_fiscal_position_tax ***********************************************
default={
}
MigrationTable(db_src,db_dst,'account_fiscal_position_tax', default=default)
#******************************************************************************

#** mail **********************************************************************
tables=[
    "mail_mail",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************

#** mail_message *****************************************************************
table = 'mail_message'
default = {'message_type': 'notification'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************

# #** mail_notification *****************************************************************
# table = 'mail_notification'
# rename = {
#     'message_id': 'mail_message_id',
#     'partner_id': 'res_partner_id',
# }
# default = {'notification_type': 'email'}
# MigrationTable(db_src,db_dst,table,rename=rename,default=default)
# #******************************************************************************

#** mail_message_subtype ******************************************************
table = 'mail_message_subtype'
MigrationTable(db_src,db_dst,table,text2jsonb=True)
#******************************************************************************

#** mail **********************************************************************
tables=[
    "mail_mail_res_partner_rel",
    "mail_message_res_partner_rel",
    "message_attachment_rel",
    "mail_tracking_value",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************

#** mail_message **************************************************************
SQL="""
    update mail_message set model='account.move' where model='account.invoice';
    update mail_message set model='stock.lot' where model='stock.production.lot';
    update mail_message set model=NULL where model='procurement.order';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************

#** Liens entre mail_message et account_invoice *******************************
ids=InvoiceIds2MoveIds(cr_src)
SQL="SELECT id, res_id from mail_message where model='account.invoice' order by id"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    invoice_id = row["res_id"]
    if invoice_id in ids:
        move_id = ids[invoice_id]
        SQL="update mail_message set res_id=%s where id=%s"
        cr_dst.execute(SQL, [move_id, row["id"]])
cnx_dst.commit()
#******************************************************************************

# ** ir_filters ***************************************************************
# ** Si le filtre n'a pas d'action associée il sera visible dans tous les menus du modèle
# ** Et comme l'id de l'action change lors du changement de version, il est préférable de vider ce champ
default = {'sort': []}
MigrationTable(db_src,db_dst,"ir_filters", default=default)
SQL="""
    update ir_filters set action_id=NULL, active='t';
    update ir_filters set user_id=2 where user_id=1;
    update ir_filters set model_id='account.move' where model_id='account.invoice';

"""
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT id,model_id,domain,context FROM ir_filters"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    if row['model_id']=='account.move':
        domain  = row['domain'].replace('date_invoice','invoice_date')
        context = row['context'].replace('date_invoice','invoice_date')
        SQL="UPDATE ir_filters set domain=%s, context=%s WHERE id=%s"
        cr_dst.execute(SQL,(domain, context,row['id']))
cnx_dst.commit()
#******************************************************************************


# ** Migration des pièces jointes *********************************************
MigrationTable(db_src,db_dst,"ir_attachment")
#******************************************************************************

#** Pièces jointes des factures ***********************************************
SQL="""
    SELECT 
        id,
        move_id
     from account_invoice
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="update ir_attachment set res_model='account.move', res_id=%s where res_id=%s and res_model='account.invoice'"
    cr_dst.execute(SQL,[row["move_id"], row["id"]])
cnx_dst.commit()
#******************************************************************************

#** Récupérer la ligne de ir_attachment pour faire fonctionner les PDF ********
table="ir_attachment"
where="name='res.company.scss'"
db_vierge = 'odoo18'
CopieTable(db_vierge,db_dst,table,where)
#******************************************************************************




