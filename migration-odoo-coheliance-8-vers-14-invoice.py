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
#lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
db_dst = db_migre

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


#** is_affaire ****************************************************************
MigrationTable(db_src,db_dst,'is_affaire')
#******************************************************************************



#** sale_order ****************************************************************
MigrationTable(db_src,db_dst,'sale_order')
default={'customer_lead': 0}
MigrationTable(db_src,db_dst,'sale_order_line',default=default)
#******************************************************************************


#** TODO : Je n'arrviais pas à afficher ceraines factures, mais après avoir migré la table account_account, cela a fonctionné
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
}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)


#** account_invoice_line => account_move **************************************
print("account_invoice => account_move")
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
        ai.residual
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
                amount_residual_signed=%s
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
            move_id
        )
    )
cnx_dst.commit()


#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""UPDATE account_move_line set exclude_from_invoice_tab='t' WHERE product_id is null"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# # ** Migration tax_code_id ****************************************************
# SQL="""
#     select aml.id move_line_id,aml.name,aml.tax_code_id,aml.debit,aml.credit,at.id tax_line_id
#     from account_move_line aml inner join account_tax at on aml.tax_code_id=at.tax_code_id 
# """
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     #print(row)
#     SQL="""
#         UPDATE account_move_line
#         SET 
#             tax_line_id=%s,
#             tax_group_id=1,
#             currency_id=1,
#             company_currency_id=1,
#             quantity=1
#         WHERE id=%s
#     """
#     cr_dst.execute(SQL,[row["tax_line_id"],row["move_line_id"]])
# cnx_dst.commit()
# #******************************************************************************














sys.exit()


#** res_partner **********************************************************
MigrationTable(db_src,db_dst,'res_partner_title')
MigrationTable(db_src,db_dst,'res_partner')
#******************************************************************************




#** res_users **********************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** res_users (id=2) *************************************************************
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


#** Réinitialisation du mot de passe *******************************************
SQL="update res_users set password='$pbkdf2-sha512$25000$5rzXmjOG0Lq3FqI0xjhnjA$x8X5biBuQQyzKksioIecQRg29ir6jY2dTd/wGhbE.wrUs/qJlrF1wV6SCQYLiKK1g.cwVCztAf3WfBxvFg6b7w'"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************





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


#** Création comptes pour journaux pour faire fonctionner les réglements ******
#cr_dst.execute("DELETE FROM account_account where code in ('512001','512002','512003','512004')")
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Bank Suspense Account','512001',False,9,'other','asset',False,1,127,53049,False])
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Banque','512002',False,3,'liquidity','asset',False,1,127,53049,False])
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Outstanding Receipts','512003',False,5,'other','asset',True,1,127,53049,False])
SQL="""
    INSERT INTO account_account (name,code,deprecated,user_type_id,internal_type,internal_group,reconcile,company_id,group_id,root_id,is_off_balance)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL,['Outstanding Payments','512004',False,5,'other','asset',True,1,127,53049,False])
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







#TODO Il reste un bug avec res_parter=2 = partner_root
# SQL="UPDATE ir_model_data set res_id=3 WHERE module='base' and name='partner_root' and model='res.partner' "
# cr_dst.execute(SQL)
# cnx_dst.commit()





