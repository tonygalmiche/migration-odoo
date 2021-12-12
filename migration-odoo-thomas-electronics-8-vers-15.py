#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "thomas-electronics8"
db_dst = "thomas-electronics15"
#******************************************************************************

cnx,cr=GetCR(db_src)
db_vierge = db_dst+'-vierge'
SQL='DROP DATABASE \"'+db_dst+'\";CREATE DATABASE \"'+db_dst+'\" WITH TEMPLATE \"'+db_vierge+'\"'
cde="""echo '"""+SQL+"""' | psql postgres"""
#lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)
cnx_vierge,cr_vierge=GetCR(db_vierge)


# ** purge des tests **********************************************************
SQL="""
    delete from crm_team;
    delete from account_partial_reconcile ;
    delete from account_move;
    delete from mail_channel;
    delete from mail_alias;
    delete from mail_mail;
    delete from mail_message;
    -- delete from mail_message_subtype;
    delete from mail_followers;
    
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** res_partner ***************************************************************
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


#** Migration mot de passe ****************************************************
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
#******************************************************************************



#** res_company_users_rel *****************************************************
MigrationTable(db_src,db_dst,'res_company_users_rel')
cr_dst.execute("insert into res_company_users_rel values(1,2)")
cnx_dst.commit()
# #****************************************************************************


#** res_groups ****************************************************************
MigrationResGroups(db_src,db_dst)
cr_dst.execute("delete from res_groups_users_rel where gid=10;") # L'utilisateur ne peut pas avoir plus d'un type d'utilisateur.
cnx_dst.commit()
# #****************************************************************************


# ** Tables diverses **********************************************************
tables=[
    "is_famille",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************



#** product *******************************************************************
default={
    'sale_line_warn'    : 'no-message',
    'purchase_line_warn': 'no-message',
    'tracking'          : 'none',
}
rename={
    'type':'detailed_type'
}
MigrationTable(db_src,db_dst,"product_template",default=default,rename=rename)
MigrationTable(db_src,db_dst,"product_product")
MigrationIrProperty(db_src,db_dst,'product.template', field_src='property_account_income' , field_dst='property_account_income_id')
MigrationIrProperty(db_src,db_dst,'product.template', field_src='property_account_expense', field_dst='property_account_expense_id')
MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')
#******************************************************************************


#** Traductions account_payment_term ******************************************
SQL="SELECT id,name FROM product_template"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    res_id = row["id"]
    value=GetTraduction(cr_src,'product.template','name', res_id)
    if value:
        SQL="update product_template set name=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
    value=GetTraduction(cr_src,'product.template','note', res_id)
    if value:
        SQL="update product_template set note=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
SQL="delete from ir_translation where name like 'product.template,%'"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_account ***********************************************************
table='account_account'
rename={
    'user_type': 'user_type_id',
}
MigrationTable(db_src,db_dst,table,rename=rename)
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


# account_account : set user_type_id et internal_type *************************
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




#** product_template **************************************************************
MigrationIrProperty(db_src,db_dst,'product.template', 'property_account_income_id')
MigrationIrProperty(db_src,db_dst,'product.template', 'property_account_expense_id')
#******************************************************************************




#** account_tax **************************************************************
SQL="""
    delete from account_tax_repartition_line;
    delete from account_account_tag_account_tax_repartition_line_rel;
    -- update res_company set account_purchase_tax_id=11;
    -- update res_company set account_sale_tax_id=1;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
table='account_tax'
rename={
    'type':'amount_type'
}
default={
    'tax_group_id': 1,
    'country_id'  : 75, # France
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default)
MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')
#******************************************************************************


#** Ajouter les comptes sur les taxes *****************************************
SQL="SELECT id FROM account_tax"
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
       INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, invoice_tax_id, company_id, sequence, use_in_tax_closing)
       VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',id,1,1,True])
    SQL="""
       INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, refund_tax_id, company_id, sequence, use_in_tax_closing)
       VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',id,1,1,True])
cnx_dst.commit()
#******************************************************************************




#** account_journal ***********************************************************
default={
    'active'                 : True,
    'invoice_reference_type' :'invoice',
    'invoice_reference_model': 'odoo',
}
MigrationTable(db_src,db_dst,"account_journal",default=default)
#******************************************************************************


#** Position fiscale **********************************************************
MigrationTable(db_src,db_dst,'account_fiscal_position')
MigrationTable(db_src,db_dst,'account_fiscal_position_tax')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_position', field_dst='property_account_position_id')
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


# ** Property res_parter ******************************************************
MigrationIrProperty(db_src,db_dst,'res.partner','property_payment_term_id')
MigrationIrProperty(db_src,db_dst,'res.partner','property_supplier_payment_term_id')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_receivable', field_dst='property_account_receivable_id')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_payable'   , field_dst='property_account_payable_id')
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


# ** stock_location / stock_warehouse  ****************************************
MigrationTable(db_src,db_dst,'stock_location')
default={'manufacture_steps': 'mrp_one_step'}
MigrationTable(db_src,db_dst,'stock_warehouse', default=default)
SQL="""
    update stock_location set parent_path=name;
    update product_category set parent_path='/' where parent_path is null;
    update product_category set complete_name=name;
    update stock_warehouse set active='t';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
MigrationIrProperty(db_src,db_dst,'product.template', 'property_stock_production')
MigrationIrProperty(db_src,db_dst,'product.template', 'property_stock_inventory')
# *****************************************************************************


#** res_company ***************************************************************
cr_dst.execute("update res_company set account_purchase_tax_id=Null")
cnx_dst.commit()
MigrationDonneesTable(db_src,db_dst,'res_company')
#******************************************************************************



#** mrp_bom ***************************************************************
rename={'product_uom':'product_uom_id'}
default={
    'ready_to_produce': 'all_available',
    'consumption'     : 'warning',
}
MigrationTable(db_src,db_dst,'mrp_bom', rename=rename, default=default)
rename={'product_uom':'product_uom_id'}
MigrationTable(db_src,db_dst,'mrp_bom_line', rename=rename)
#******************************************************************************

#  id | message_main_attachment_id | code | active |  type  | product_tmpl_id | product_id | product_qty | product_uom_id | sequence | ready_to_produce | picking_type_id | company_id | consumption | create_uid |        create_date        | write_uid |        write_date         
# ----+----------------------------+------+--------+--------+-----------------+------------+-------------+----------------+----------+------------------+-----------------+------------+-------------+------------+---------------------------+-----------+---------------------------
#   1 |                            |      | t      | normal |               1 |            |        1.00 |              1 |          | all_available    |                 |          1 | warning     |          2 | 2021-12-11 10:18:16.58228 |         2 | 2021-12-11 10:18:16.58228
