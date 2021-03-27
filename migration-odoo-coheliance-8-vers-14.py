#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os

#** Paramètres ****************************************************************
db_src = "coheliance8"
db_dst = "coheliance14"
#******************************************************************************

cnx,cr=GetCR(db_src)
db_migre = db_dst+'_migre'
SQL="DROP DATABASE "+db_migre+";CREATE DATABASE "+db_migre+" WITH TEMPLATE "+db_dst
cde='echo "'+SQL+'" | psql postgres'
lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
db_dst = db_migre

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


#sys.exit()


#** res_partner ***************************************************************
MigrationTable(db_src,db_dst,'res_partner_title')
MigrationTable(db_src,db_dst,'res_partner')
#******************************************************************************


#** res_users *****************************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** res_users (id=2) **********************************************************
champs = GetChamps(cr_dst,'res_partner')
champs.remove('id')
champs=','.join(champs)
SQL="""
    INSERT INTO res_partner(id,"""+champs+""")
    SELECT 2,"""+champs+"""
    FROM res_partner WHERE id=3;
"""
cr_dst.execute(SQL)
cnx_dst.commit()

champs = GetChamps(cr_dst,'res_users')
champs.remove('id')
champs.remove('login')
champs=','.join(champs)
SQL="""
    INSERT INTO res_users(id,login,"""+champs+""")
    SELECT 2,'superuser',"""+champs+"""
    FROM res_users WHERE id=1;
    UPDATE res_users set login='__system__', partner_id=2 where id=1;
    UPDATE res_users set login='admin', partner_id=3 where id=2;   
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************

# coheliance14_migre=# update res_users set password=  where id^C
# coheliance14_migre=# update res_users set password=(select password from res_users where id=1) where id=2;
# UPDATE 1
# coheliance14_migre=# insert into res_company_users_rel values(1,2);
# INSERT 0 1

# #** Migration mot de passe **************************************************
SQL="SELECT id,password_crypt FROM res_users"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE res_users SET password=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['password_crypt'],row['id']])
cnx_dst.commit()
SQL="update res_users set password=(select password from res_users where id=1) where id=2"
cr_dst.execute(SQL)
cnx_dst.commit()
# #****************************************************************************


#** res_company_users_rel *****************************************************
MigrationTable(db_src,db_dst,'res_company_users_rel')
cr_dst.execute("insert into res_company_users_rel values(1,2)")
cnx_dst.commit()
# #****************************************************************************


#** Migration des comptes *****************************************************
SQL="""
    delete from account_journal;
    delete from account_account;
    delete from account_account_template;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_journal ***********************************************************
table="account_journal"
rename={
    'currency'   : 'currency_id',
    'sequence_id': 'sequence',
}
default={
    'active'                 : True,
    'invoice_reference_type' :'invoice',
    'invoice_reference_model': 'odoo',
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default)
#******************************************************************************


#** account_account ***********************************************************
table='account_account'
rename={
    'user_type': 'user_type_id',
}
MigrationTable(db_src,db_dst,table,rename=rename)
#******************************************************************************


#** account_root **************************************************************
SQL="SELECT id,code FROM account_account"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    id=row["id"]
    code=row["code"]
    root_id = (ord(code[0]) * 1000 + ord(code[1:2] or '\x00'))
    SQL="UPDATE account_account SET root_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[root_id,id])
cnx_dst.commit()
#******************************************************************************


#** account_tax **************************************************************
SQL="""
    delete from account_tax_repartition_line;
    delete from account_account_tag_account_tax_repartition_line_rel;
    update res_company set account_purchase_tax_id=1;
    update res_company set account_sale_tax_id=2;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
table='account_tax'
rename={
    'type':'amount_type'
}
default={
    'tax_group_id': 1,
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default)
cr_dst.execute("update account_tax set amount=100*amount")
cnx_dst.commit()
#******************************************************************************


#** Ajouter les comptes sur les taxes *****************************************
SQL="SELECT id,account_paid_id,account_collected_id FROM account_tax"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    id = row["id"]
    SQL="""
        INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, invoice_tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[0,'base',id,1,1,False])
    SQL="""
        INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, refund_tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[0,'base',id,1,1,False])
    SQL="""
        INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, account_id, invoice_tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',row["account_collected_id"],id,1,1,True])
    SQL="""
        INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, account_id, refund_tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',row["account_paid_id"],id,1,1,True])
cnx_dst.commit()
#******************************************************************************


MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_receivable', field_dst='property_account_receivable_id')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_payable'   , field_dst='property_account_payable_id')


# account_account_type ********************************************************
cr_dst.execute("update account_account set user_type_id=18 ,internal_type='other'")                               # Hors bilan
cr_dst.execute("update account_account set user_type_id=1  ,internal_type='receivable' where code like '411___'") # Recevable
cr_dst.execute("update account_account set user_type_id=2  ,internal_type='payable'    where code like '401___'") # Payable
cr_dst.execute("update account_account set user_type_id=5  ,internal_type='other'      where code like '471___'") # Actif circulant
cr_dst.execute("update account_account set user_type_id=5  ,internal_type='other'      where code like '4456__'") # Actif circulant
cr_dst.execute("update account_account set user_type_id=9  ,internal_type='other'      where code like '4457__'") # Passif circulant
cr_dst.execute("update account_account set user_type_id=13 ,internal_type='other'      where code like '7_____'") # Revenus
cr_dst.execute("update account_account set user_type_id=15 ,internal_type='other'      where code like '6_____'") # Dépenses
cr_dst.execute("update account_account set user_type_id=8  ,internal_type='other'      where code like '2_____'") # Immobilisations
cr_dst.execute("update account_account set user_type_id=3  ,internal_type='other'      where code like '512___'") # Banque et liquidités
cr_dst.execute("update account_account set user_type_id=9  ,internal_type='receivable' where code like '512101'") # Passif circulant
cnx_dst.commit()
#******************************************************************************


# #** Création comptes pour journaux pour faire fonctionner les réglements ******
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Suspense Account','512112',False,9,'other','asset',False,1,127,53049,False])
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Suspense Account','512113',False,9,'other','asset',False,1,127,53049,False])

SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Outstanding Receipts Account','512122',False,5,'other','asset',True,1,127,53049,False])
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Outstanding Receipts Account','512123',False,5,'other','asset',True,1,127,53049,False])


SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Outstanding Payments Account','512132',False,5,'other','asset',True,1,127,53049,False])
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Outstanding Payments Account','512133',False,5,'other','asset',True,1,127,53049,False])
cnx_dst.commit()

SQL="""
    update account_journal set type='general' where code='BNK1';

    update account_journal set default_account_id=(select id        from account_account where code='512102') where code='BNK2';
    update account_journal set suspense_account_id=(select id       from account_account where code='512112') where code='BNK2';
    update account_journal set payment_debit_account_id=(select id  from account_account where code='512122') where code='BNK2';
    update account_journal set payment_credit_account_id=(select id from account_account where code='512132') where code='BNK2';

    update account_journal set default_account_id=(select id        from account_account where code='512103') where code='BNK3';
    update account_journal set suspense_account_id=(select id       from account_account where code='512113') where code='BNK3';
    update account_journal set payment_debit_account_id=(select id  from account_account where code='512123') where code='BNK3';
    update account_journal set payment_credit_account_id=(select id from account_account where code='512133') where code='BNK3';

    delete from account_journal_outbound_payment_method_rel;
    delete from account_journal_inbound_payment_method_rel ;
    insert into account_journal_inbound_payment_method_rel values(8,1);
    insert into account_journal_inbound_payment_method_rel values(10,1);
    insert into account_journal_outbound_payment_method_rel values(8,2);
    insert into account_journal_outbound_payment_method_rel values(10,2);
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# Configuration de res_company pour faire fonctionner les réglements **********
cr_dst.execute("update res_company set income_currency_exchange_account_id=918")
cr_dst.execute("update res_company set expense_currency_exchange_account_id=780")
cr_dst.execute("update res_company set currency_exchange_journal_id=9")
#******************************************************************************


# ** Migration country_id dans res_partner ************************************
SQL="""
    select distinct rp.country_id,rc.name
    from res_partner rp inner join res_country rc on rp.country_id=rc.id 
    where country_id is not null 
"""
cr_src.execute(SQL)
rows_src = cr_src.fetchall()
src2dst={}
for row_src in rows_src:
    SQL="SELECT id FROM res_country WHERE name='"+row_src['name']+"'"
    cr_dst.execute(SQL)
    rows_dst = cr_dst.fetchall()
    for row_dst in rows_dst:
        src2dst[row_src['country_id']]=row_dst['id']
SQL="select id,name,country_id from res_partner where country_id is not null order by name"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    if row['country_id'] in src2dst:
        country_id = src2dst[row['country_id']]
        SQL="UPDATE res_partner SET country_id=%s WHERE id=%s"
        cr_dst.execute(SQL,[country_id,row['id']])
cr_dst.execute("update res_partner set country_id=75 where  country_id=255")
cnx_dst.commit()
# *****************************************************************************


#** product_category **********************************************************
MigrationTable(db_src,db_dst,'product_category')
SQL="""
    update product_category set parent_path='/' where parent_path is null;
    update product_category set complete_name=name;
    update product_category set complete_name='Tous'   ,  name='Tous'     where id=1;
    update product_category set complete_name='En Vente', name='En Vente' where id=2;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
MigrationIrProperty(db_src,db_dst,'product.category', field_src='property_account_income_categ' , field_dst='property_account_income_categ_id')
MigrationIrProperty(db_src,db_dst,'product.category', field_src='property_account_expense_categ', field_dst='property_account_expense_categ_id')
#******************************************************************************


#** product *******************************************************************
table="product_template"
default={
    'sale_line_warn'    : 'no-message',
    'purchase_line_warn': 'no-message',
    'tracking'          : 'none',
}
MigrationTable(db_src,db_dst,table,default=default)
table="product_product"
MigrationTable(db_src,db_dst,table)
MigrationIrProperty(db_src,db_dst,'product.template', field_src='property_account_income' , field_dst='property_account_income_id')
MigrationIrProperty(db_src,db_dst,'product.template', field_src='property_account_expense', field_dst='property_account_expense_id')

MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')

#******************************************************************************


#** is_affaire ****************************************************************
MigrationTable(db_src,db_dst,'is_affaire')
#******************************************************************************


#** sale_order ****************************************************************
MigrationTable(db_src,db_dst,'sale_order')
default={'customer_lead': 0}
MigrationTable(db_src,db_dst,'sale_order_line',default=default)
#******************************************************************************


# ** account_bank_statement ****************************************************
MigrationTable(db_src,db_dst,'account_bank_statement')
rename={'name':'payment_ref'}
default={'move_id': 2}
MigrationTable(db_src,db_dst,'account_bank_statement_line',rename=rename,default=default)
SQL="""
    update account_bank_statement set state='open';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_move_line *********************************************************
MigrationTable(db_src,db_dst,'account_move_reconcile', table_dst='account_full_reconcile')
rename={}
default={
    'move_type'  : 'entry',
    'currency_id': 1,
}
MigrationTable(db_src,db_dst,'account_move'     , table_dst='account_move'     , rename=rename,default=default)
default={
    'currency_id': 1,
}
rename={
    'tax_amount': 'tax_base_amount',
    'reconcile_partial_id': 'full_reconcile_id',
}
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
        ai.order_id,
        ai.is_affaire_id,
        ai.is_refacturable,
        ai.is_nom_fournisseur,
        ai.is_personne_concernee_id,
        ai.amount_untaxed,
        ai.amount_tax,
        ai.amount_total,
        ai.residual,
        ai.user_id,
        ai.fiscal_position,
        ai.name move_name,
        ai.origin,
        ai.supplier_invoice_number,
        ai.payment_term
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
                order_id=%s,
                is_affaire_id=%s,
                is_refacturable=%s,
                is_nom_fournisseur=%s,
                is_personne_concernee_id=%s,
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
                supplier_invoice_number=%s,
                invoice_payment_term_id=%s
            where id=%s
        """
        cr_dst.execute(SQL,(
            row['date_invoice'],
            row['type'],
            row['name'],
            row['date_due'],
            row['order_id'],
            row['is_affaire_id'],
            row['is_refacturable'],
            row['is_nom_fournisseur'],
            row['is_personne_concernee_id'],
            row['amount_untaxed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['amount_untaxed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['user_id'],
            row['fiscal_position'],
            row['origin'],
            row['supplier_invoice_number'],
            row['payment_term'],
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


#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""UPDATE account_move_line set exclude_from_invoice_tab='t' WHERE product_id is null"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Migration tax_code_id ****************************************************
cr_dst.execute("update account_move_line set amount_currency=(debit-credit)")
cr_dst.execute("update account_move_line set company_currency_id=currency_id")
cnx_dst.commit()
SQL="""
    select aml.id move_line_id,aml.name,aml.tax_code_id,aml.debit,aml.credit,at.id tax_line_id
    from account_move_line aml inner join account_tax at on aml.tax_code_id=at.tax_code_id 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        UPDATE account_move_line
        SET 
            tax_line_id=%s,
            tax_group_id=1,
            currency_id=1,
            company_currency_id=1,
            quantity=1
        WHERE id=%s
    """
    cr_dst.execute(SQL,[row["tax_line_id"],row["move_line_id"]])
cnx_dst.commit()
#******************************************************************************


#** Migration des taxes sur les factures **************************************
SQL="DELETE FROM account_move_line_account_tax_rel"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT invoice_line_id, tax_id  FROM account_invoice_line_tax"
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


#** Position fiscale **********************************************************
MigrationTable(db_src,db_dst,'account_fiscal_position')
MigrationTable(db_src,db_dst,'account_fiscal_position_tax')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_position', field_dst='property_account_position_id')
#******************************************************************************


# #** account_move / fiscal_position_id *****************************************
# SQL="select id,partner_id,state from account_move where partner_id is not null"
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for r in rows:
#     fiscal_position_id = GetFiscalPositionPartner(cr_dst,r['partner_id'])
#     if fiscal_position_id:
#         cr_dst.execute("update account_move set fiscal_position_id=%s where id=%s",[fiscal_position_id,r["id"]])
# cnx_dst.commit()
# #******************************************************************************


#** account_move / payment_state **********************************************
SQL="select id,move_id,state from account_invoice"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    if row["state"]=="open":
        cr_dst.execute("update account_move set payment_state='not_paid' where id=%s",[row["move_id"]])
    if row["state"]=="paid":
        cr_dst.execute("update account_move set payment_state='paid' where id=%s",[row["move_id"]])
cnx_dst.commit()
#******************************************************************************



#** account_move_line / amount_residual (reste à payer )***********************
SQL="""
    select id,move_id,internal_number,type,state,residual 
    from account_invoice 
    where state='open' and type='out_invoice' and residual<>0
    order by internal_number
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    move_id = row["move_id"]
    SQL="""
        select aml.id,aml.move_id,aml.account_id,aa.code
        from account_move_line aml inner join account_account aa on aml.account_id=aa.id
        where aa.code like '4%' and aml.move_id="""+str(move_id)+"""
    """
    cr_dst.execute(SQL)
    rows2 = cr_dst.fetchall()
    for row2 in rows2:
        SQL="update account_move_line set amount_residual_currency=%s, amount_residual=%s where id=%s"
        cr_dst.execute(SQL,[row["residual"],row["residual"],row2["id"]])
cnx_dst.commit()
#******************************************************************************


#** account_move_line / move_name, parent_state et account_root_id ************
cr_dst.execute("update account_move_line set move_name=(select am.name from account_move am where move_id=am.id limit 1)")
cr_dst.execute("update account_move_line set parent_state=(select am.state from account_move am where move_id=am.id limit 1)")
cr_dst.execute("update account_move_line set account_root_id=(select aa.root_id from account_account aa where aa.id=account_id)")
cr_dst.execute("update account_move_line set tax_exigible='t'")
cr_dst.execute("update account_move set sequence_prefix=name") # Permet de conserver le numéro si remise en brouillon
cnx_dst.commit()
#******************************************************************************


#** account_move_line / tax_base_amount ***************************************
cr_dst.execute("update account_move_line set tax_base_amount=0 where tax_line_id is null")
SQL="""
    select id,move_id,tax_line_id
    from account_move_line 
    where tax_line_id is not null 
"""
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    SQL="""
        select ait.base_amount
        from account_invoice_tax ait inner join account_invoice ai on ait.invoice_id=ai.id 
                                     inner join account_tax at on ait.tax_code_id=at.tax_code_id 
        where ai.move_id=%s and at.id=%s
    """
    cr_src.execute(SQL,(row["move_id"],row["tax_line_id"]))
    rows2 = cr_src.fetchall()
    for row2 in rows2:
        SQL="update account_move_line set tax_base_amount=%s where id=%s"
        cr_dst.execute(SQL,[row2["base_amount"],row["id"]])
cnx_dst.commit()
#******************************************************************************


#** account_move_line / tax_repartition_line_id *******************************
SQL="""
    update account_move_line set tax_repartition_line_id=(select id 
    from account_tax_repartition_line where invoice_tax_id=tax_line_id and repartition_type='tax' limit 1) 
    where tax_line_id is not null
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_partial_reconcile *************************************************
cr_dst.execute("DELETE FROM account_partial_reconcile")
cnx_dst.commit()
SQL="select reconcile_id,count(*) from account_move_line where reconcile_id is not null  group by reconcile_id having count(*)=2"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        select l1.reconcile_id, l1.id debit_move_id,l2.id credit_move_id,l1.debit,l2.credit 
        from account_move_line l1 join  account_move_line l2 on l1.reconcile_id=l2.reconcile_id and l1.debit>0 and l2.credit>0
        where l1.reconcile_id="""+str(row["reconcile_id"])
    cr_src.execute(SQL)
    rows2 = cr_src.fetchall()
    for row2 in rows2:
        full_reconcile_id = row2["reconcile_id"]
        debit_move_id     = row2["debit_move_id"]
        credit_move_id    = row2["credit_move_id"]
        credit = row2["credit"]
        debit  = row2["debit"]
        SQL="""
            INSERT INTO account_partial_reconcile (debit_move_id, credit_move_id, full_reconcile_id, debit_currency_id, credit_currency_id, amount, debit_amount_currency, credit_amount_currency,company_id,max_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cr_dst.execute(SQL,[debit_move_id,credit_move_id,full_reconcile_id,1,1,credit,debit,credit,1,"1990-01-01"])
cnx_dst.commit()
#******************************************************************************


#** account_payment ***********************************************************
cr_dst.execute("DELETE FROM account_payment")
cnx_dst.commit()
SQL="""
    select am.id,am.name, l.credit,a2.code,l.reconcile_id,am.partner_id
    from account_move am join account_move_line l on am.id=l.move_id join account_journal aj on am.journal_id=aj.id 
                         join account_account a2 on l.account_id=a2.id  
    where aj.type='bank' and a2.code like '4%' ;
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    debit = row["credit"]
    SQL="""
    INSERT INTO account_payment (move_id, is_reconciled, is_matched, is_internal_transfer, payment_method_id, amount, payment_type, partner_type, currency_id, partner_id, destination_account_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """
    cr_dst.execute(SQL,[row['id'],True,False,False,1,debit,'inbound','customer',1,row["partner_id"],1026])
cnx_dst.commit()

#******************************************************************************


#** Lien entre account_move et account_payment ********************************
SQL="select id,move_id from account_payment"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    move_id = row["move_id"]
    SQL="update account_move set payment_id=%s,state='posted' where id=%s"
    cr_dst.execute(SQL,[row["id"],row["move_id"]])
    SQL="update account_move_line set payment_id=%s where move_id=%s"
    cr_dst.execute(SQL,[row["id"],row["move_id"]])
cnx_dst.commit()
#******************************************************************************


#** Factures fournisseurs => inverser les signes => pour réglements ***********
SQL="""
    update account_move set amount_untaxed_signed=-amount_untaxed where move_type='in_invoice';
    update account_move set amount_tax_signed=-amount_tax where move_type='in_invoice';
    update account_move set amount_total_signed=-amount_total where move_type='in_invoice';
    update account_move set amount_residual_signed=-amount_residual where move_type='in_invoice';

    update account_move set posted_before='t' where move_type='in_invoice';
    update account_move set is_move_sent='f' where move_type='in_invoice';

    update account_move_line set price_unit=-price_unit, price_subtotal=-price_subtotal, price_total=-price_total 
    where 
        move_id in (select id from account_move m where m.move_type='in_invoice') and 
        account_id in (select id from account_account where code like '4%');

    update account_move_line set amount_residual=price_total, amount_residual_currency=price_total 
    where 
        move_id in (select id from account_move m where m.move_type='in_invoice') and 
        account_id in (select id from account_account where code like '401%');
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Autres tables *************************************************************
tables=[
    'crm_lead',
    'decimal_precision',
    'hr_employee',
    'is_acompte',
    'is_affaire',
    'is_affaire_intervenant',
    'is_affaire_intervention',
    'is_affaire_vente',
    'is_bilan_pedagogique',
    'is_bilan_pedagogique_financier',
    'is_bilan_pedagogique_type_stagiaire',
    'is_bilan_pedagogique_typologie',
    'is_classification',
    'is_compte_resultat',
    'is_compte_resultat_annee',
    'is_export_compta',
    'is_export_compta_ligne',
    'is_fiche_frais',
    'is_frais',
    'is_frais_ligne',
    'is_import_banque',
    'is_import_banque_cb_attachment_rel',
    'is_import_banque_operation_attachment_rel',
    'is_origine_financement',
    'is_prospective',
    'is_prospective_line',
    'is_region',
    'is_secteur_activite',
    'is_suivi_banque',
    'is_suivi_caisse',
    'is_suivi_tresorerie',
    'is_type_stagiaire_organisme',
    'is_typologie',
    'is_typologie_stagiaire',
    'mail_alias',
    'mail_followers',
    'mail_followers_mail_message_subtype_rel',
    'mail_message',
    'product_pricelist',
    'product_pricelist_item',
    'product_removal',
    'project_task_type',
    'res_bank',
    #'res_company', TODO : Plantage si migration de cette table
    'res_partner_bank',
    'res_partner_category',
    'res_partner_res_partner_category_rel',
    'stock_location',
    'stock_warehouse',
]

for table in tables:
    print('Migration ',table)
    rename={}
    default={}
    if table=="product_pricelist":
        default={
            'discount_policy': 'with_discount',
        }
    if table=="product_pricelist_item":
        default={
            'applied_on'   : '3_global',
            'pricelist_id' : 1,
            'compute_price': 'fixed',
        }
    if table=="project_task_type":
        default={
            'legend_blocked': 'Blocked',
            'legend_done'   : 'Ready',
            'legend_normal' : 'In Progress',
        }
    if table=="hr_employee":
        default={
            'company_id': 1,
            'active': True,
        }
    #TODO : Plantage si migration de cette table => Beacoup de paramètres associés à cette table dans Odoo 14
    # if table=="res_company":
    #     default={
    #         'fiscalyear_last_day'  : 31,
    #         'fiscalyear_last_month': 12,
    #         'account_opening_date' : '2020-01-01',
    #     }
    if table=="mail_message":
        default={
            'message_type'  : 'notification',
        }
    if table=="res_partner_bank":
        default={
            'partner_id'  : 1,
            'active'  : True,
        }

    MigrationTable(db_src,db_dst,table,rename=rename,default=default)
#******************************************************************************


# ** Requetes diverses  *******************************************************
SQL="""
    update stock_location set parent_path=name;
    update product_category set parent_path='/' where parent_path is null;
    update product_category set complete_name=name;
    update stock_warehouse set active='t';
    update product_template set invoice_policy='order';
    update product_template set service_type='timesheet';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
# *****************************************************************************


# ** Migration sale_order_tax => account_tax_sale_order_line_rel **************
print('Migration sale_order_tax => account_tax_sale_order_line_rel')
rename={
    'order_line_id': 'sale_order_line_id',
    'tax_id'       : 'account_tax_id',
}
MigrationTable(db_src,db_dst,'sale_order_tax',table_dst='account_tax_sale_order_line_rel',rename=rename)
# *****************************************************************************


#** compute sale_order_line / price_subtotal ***********************************
SQL="UPDATE sale_order_line SET price_subtotal=product_uom_qty*price_unit"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** siret res_company migré dans res_partner ***********************************
SQL="SELECT siret FROM res_company WHERE id=1"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE res_partner SET siret='"+row['siret']+"' WHERE id=1"
    cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** res_partner ****************************************************************
SQL="""
    SELECT id,name,supplier,customer
    FROM res_partner
    ORDER BY name
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    customer_rank=supplier_rank='0'
    if row['supplier']:
        supplier_rank='1'
    if row['customer']:
        customer_rank='1'
    SQL="UPDATE res_partner SET customer_rank="+customer_rank+", supplier_rank="+supplier_rank+" WHERE id="+str(row['id'])
    cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** product_pricelist_item *****************************************************
SQL="update product_pricelist_item set active='t'"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


MigrationResGroups(db_src,db_dst)
MigrationDonneesTable(db_src,db_dst,'res_company')


#** state sale_order **********************************************************
print("state sale_order")
SQL="UPDATE sale_order SET state='sale', invoice_status='invoiced'"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT id,name,state FROM sale_order"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    if row['state']=='manual':
        cr_dst.execute("UPDATE sale_order SET invoice_status='to invoice' WHERE id="+str(row["id"]))
    if row['state']=='draft':
        cr_dst.execute("UPDATE sale_order SET state='draft' WHERE id="+str(row["id"]))
    if row['state']=='cancel':
        cr_dst.execute("UPDATE sale_order SET state='cancel' WHERE id="+str(row["id"]))
cnx_dst.commit()
#*******************************************************************************


#** Migration traduction name dans product.template **************************************
print("Migration traduction name dans product.template")
MigrationNameTraduction(db_src,db_dst,'product.template,name')
# *****************************************************************************


#** mail_message sur les factures (account_invoice_line => account_move) ******
cr_dst.execute("update mail_message set model='account.move' where model='account.invoice'")
cnx_dst.commit()
SQL="SELECT id, move_id FROM account_invoice"
cr_src.execute(SQL)
rows = cr_src.fetchall()
ids={}
for row in rows:
    ids[row["id"]]=row["move_id"]

SQL="SELECT id,res_id FROM mail_message where model='account.move'"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    id=row["id"]
    res_id=row["res_id"]
    res_id=ids.get(res_id,False)
    if res_id:
        SQL="UPDATE mail_message set res_id=%s where id=%s"
        cr_dst.execute(SQL,[res_id,id])
cnx_dst.commit()
#******************************************************************************


#** Factures sur les affaires *************************************************
print("Factures sur les affaires")
SQL="""
    SELECT ia.id, ia.account_id, ai.move_id
    FROM is_acompte ia inner join account_invoice ai on ia.account_id=ai.id 
    WHERE ia.account_id is not null
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE is_acompte set account_id='"+str(row['move_id'])+"' where id="+str(row['id'])
    cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Migration des pièces jointes *********************************************
SQL="""
    select *
    from ir_attachment 
    where res_model<>'ir.ui.view' 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
SQL="DELETE FROM ir_attachment WHERE res_model<>'ir.ui.view' and res_field is null"
cr_dst.execute(SQL)
for row in rows:
    res_id    = row['res_id']
    res_model = row['res_model']
    if row['res_model']=='account.invoice':
        res_id = InvoiceId2MoveId(cr_src,res_id)
        res_model = 'account.move'
    SQL="""
        INSERT INTO ir_attachment (name,res_model,res_id,company_id,create_date,create_uid,file_size,mimetype,store_fname,type,url,write_date,write_uid)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cr_dst.execute(SQL,[
        row['name'],
        res_model,
        res_id,
        row['company_id'],
        row['create_date'],
        row['create_uid'],
        row['file_size'],
        row['file_type'],
        row['store_fname'],
        row['type'],
        row['url'],
        row['write_date'],
        row['write_uid'],
    ])
cnx_dst.commit()
# *****************************************************************************


#** ir_sequence ***************************************************************
SQL="SELECT id,code,implementation,prefix,padding,number_next FROM ir_sequence WHERE code is not null"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    code=row["code"]
    SQL="UPDATE ir_sequence SET prefix=%s,padding=%s,number_next=%s WHERE code=%s"
    cr_dst.execute(SQL,[row["prefix"],row["padding"],row["number_next"],code])
    if row["implementation"]=="standard":
        SQL="SELECT id FROM ir_sequence WHERE code='"+code+"'"
        cr_dst.execute(SQL)
        rows2 = cr_dst.fetchall()
        for row2 in rows2:
            seq_id = "%03d" % row["id"]
            ir_sequence = "ir_sequence_"+seq_id
            SQL="SELECT last_value FROM "+ir_sequence
            cr_src.execute(SQL)
            rows3 = cr_src.fetchall()
            for row3 in rows3:
                seq_id = "%03d" % row2["id"]
                ir_sequence = "ir_sequence_"+seq_id
                last_value = row3["last_value"]+1
                SQL="ALTER SEQUENCE "+ir_sequence+" RESTART WITH %s"
                cr_dst.execute(SQL,[last_value])
#******************************************************************************


#** Création des sequences pour les factures et avoirs ************************
SQL="SELECT * FROM ir_sequence WHERE implementation='no_gap' and id in (23,25,24,22) order by id"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO ir_sequence (code,name,number_next,implementation,company_id,padding,number_increment,prefix,active,suffix)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[row["code"],row["name"],row["number_next"],row["implementation"],row["company_id"],row["padding"],row["number_increment"],row["prefix"],row["active"],row["suffix"]])
    print(row["name"])
cnx_dst.commit()
#******************************************************************************


#** init sequence_id dans account_journal *************************************
SQL="UPDATE account_journal j set sequence_id=(SELECT id from ir_sequence s where s.name=j.name limit 1)"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** name account_tax **********************************************************
SQL="""
    update account_tax set name ='TVA 20%' where id=2;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_payment_term ******************************************************
table="account_payment_term"
default = {'sequence': 10}
MigrationTable(db_src,db_dst,table,default=default)
table="account_payment_term_line"
default = {'option': "day_after_invoice_date"}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** Traductions account_payment_term ******************************************
SQL="SELECT id,name FROM account_payment_term"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    res_id = row["id"]
    value=GetTraduction(cr_src,'account.payment.term','name', res_id)
    if value:
        SQL="update account_payment_term set name=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
    value=GetTraduction(cr_src,'account.payment.term','note', res_id)
    if value:
        SQL="update account_payment_term set note=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
SQL="delete from ir_translation where name like 'account.payment.term,%'"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** crm_phonecall *************************************************************
table='crm_phonecall'
default={
    'direction': 'out',
}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** Requetes diverses pour résoudre des anomalies *****************************
SQL="""
    update sale_order set procurement_group_id=Null where procurement_group_id is not null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** account_bank_statement ****************************************************
SQL="""
    select *
    from account_bank_statement_line 
    order by id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO account_move(
            name,
            ref,
            date,
            state,
            move_type,
            to_check,
            journal_id,
            company_id,
            currency_id,
            is_move_sent,
            statement_line_id,
            auto_post,
            amount_total,
            amount_total_signed,
            create_date,
            create_uid,
            write_date,
            write_uid
        )        
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """
    cr_dst.execute(SQL,[
        row['name'],
        row['ref'],
        row['date'],
        'draft',
        'entry',
        False,
        8,
        1,
        1,
        False,
        row['id'],
        False,
        row['amount'],
        row['amount'],
        row['create_date'],
        row['create_uid'],
        row['write_date'],
        row['write_uid'],
    ])
    cr_dst.execute('SELECT LASTVAL()')
    lastid = cr_dst.fetchone()['lastval']
    SQL="update account_bank_statement_line set move_id=%s where id=%s"
    cr_dst.execute(SQL,[lastid,row['id']])
cnx_dst.commit()
#******************************************************************************







# ** image dans res_partner dans ir_attachment ********************************
print("Pour finaliser la migration, il faut démarrer Odoo avec cette commande : ")
print("/opt/odoo-14/odoo-bin -c /etc/odoo/coheliance14.conf")
name = input("Appuyer sur Entrée pour continuer") 
models,uid,password = XmlRpcConnection(db_dst)
SQL="SELECT id,image_small,image,name  from res_partner where image is not null order by name"
cr_src.execute(SQL)
rows = cr_src.fetchall()
nb=len(rows)
ct=1
for row in rows:
    ImageField2IrAttachment(models,db_dst,uid,password,"res.partner",row["id"],row["image"])
    print(ct,"/",nb,row["name"])
    ct+=1
#*******************************************************************************





#TODO Il reste un bug avec res_parter=2 = partner_root
# SQL="UPDATE ir_model_data set res_id=3 WHERE module='base' and name='partner_root' and model='res.partner' "
# cr_dst.execute(SQL)
# cnx_dst.commit()





