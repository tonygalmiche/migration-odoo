#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os

#** Paramètres *****************************************************************
db_src = "odoo12"
db_dst = "odoo13"
#*******************************************************************************

cnx,cr=GetCR(db_src)
db_migre = db_dst+'_migre'
SQL="DROP DATABASE "+db_migre+";CREATE DATABASE "+db_migre+" WITH TEMPLATE "+db_dst
cde='echo "'+SQL+'" | psql postgres'
#lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
db_dst = db_migre








tables=[


    'account_payment_term',
    'account_payment_term_line',


    'res_partner',
    'res_partner_industry',
    'res_company',
    'ir_module_category',
    'res_users',
#    'res_groups',
    'ir_attachment',
    'sale_order',
    'sale_order_line',

    'product_category',
    'product_template',
    'product_product',
    'product_attribute',
    'product_supplierinfo',
#    'product_attribute_custom_value',
#    'product_attribute_product_template_rel',
#    'product_attribute_value',
#    'product_attribute_value_product_product_rel',
#    'product_attribute_value_product_template_attribute_line_rel',
#    'product_template_attribute_exclusion',
#    'product_template_attribute_line',
#    'product_template_attribute_value',

    'product_price_list',
    'product_pricelist',
    'product_pricelist_item',



    'mail_message',
    'res_company_users_rel',
#    'res_groups_users_rel',
    'res_users_log',
    'team_favorite_user_rel',

    #'mail_mail_res_partner_rel',
    #'ir_ui_view',
    #'ir_ui_view_group_rel',


    'purchase_order',
    'purchase_order_line',


    'project_project',
    'project_tags',
    'project_favorite_user_rel',
    'project_tags_project_task_rel',
    'project_task',
    'project_task_type',
    'project_task_type_rel',
    'resource_calendar',


    'mail_alias',
    'mail_followers',
    'mail_channel',
    'mail_channel_partner',
]



for table in tables:
    print('Migration ',table)
    rename={}
    if table=='product_attribute':
        rename={'type':'display_type'}

    MigrationTable(db_src,db_dst,table,rename=rename)

MigrationResGroups(db_src,db_dst)



#** res_partner ****************************************************************
cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)

SQL="""
    SELECT id,name,supplier,customer
    FROM res_partner
    ORDER BY name
"""
cr.execute(SQL)
rows = cr.fetchall()
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


#** ir_property ****************************************************************
properties=[
    ('res.partner','property_payment_term_id'),
    ('res.partner','property_supplier_payment_term_id')
]
for p in properties:
    model = p[0]
    field = p[1]
    MigrationIrProperty(db_src,db_dst,model,field)
#*******************************************************************************










cde="rsync -rva /home/odoo/.local/share/Odoo/filestore/"+db_src+"/ /home/odoo/.local/share/Odoo/filestore/"+db_dst
lines=os.popen(cde).readlines()

SQL="""
    update ir_attachment set res_field='image_128'  where res_field='image_small';
    update ir_attachment set res_field='image_1920' where res_field='image';
"""
cnx_dst,cr_dst=GetCR(db_dst)
cr_dst.execute(SQL)
cnx_dst.commit()

