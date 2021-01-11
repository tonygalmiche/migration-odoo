#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os

#** Paramètres *****************************************************************
db_src = "nouvelle-trajectoire8"
db_dst = "nouvelle-trajectoire14"
#*******************************************************************************

cnx,cr=GetCR(db_src)
db_migre = db_dst+'_migre'
SQL='DROP DATABASE \"'+db_migre+'\";CREATE DATABASE \"'+db_migre+'\" WITH TEMPLATE \"'+db_dst+'\"'
cde="""echo '"""+SQL+"""' | psql postgres"""
lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
db_dst = db_migre

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)




#sys.exit()



tables=[
    'is_base_documentaire',
    'is_niveau',
    'is_region',
    'is_sport',
    'is_statut',
    'is_statut_sportif',
    'res_partner',
    'res_users',
    'res_company_users_rel',
    'ir_attachment',
]

for table in tables:
    print('Migration ',table)
    rename=default={}
    if table=="res_users":
        default={
            'notification_type': 'email',
        }
        #rename={
        #    'password_crypt': 'password',
        #}
    MigrationTable(db_src,db_dst,table,rename=rename,default=default)


# #** Réinitialisation du mot de passe *******************************************
# SQL="update res_users set password='$pbkdf2-sha512$25000$5rzXmjOG0Lq3FqI0xjhnjA$x8X5biBuQQyzKksioIecQRg29ir6jY2dTd/wGhbE.wrUs/qJlrF1wV6SCQYLiKK1g.cwVCztAf3WfBxvFg6b7w'"
# cr_dst.execute(SQL)
# cnx_dst.commit()
# #*******************************************************************************


# #** Migration mot de passe *****************************************************
SQL="SELECT id,password_crypt FROM res_users"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE res_users SET password=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['password_crypt'],row['id']])
cnx_dst.commit()
# #*******************************************************************************


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


#** Mettre le nouveau user_id 2 dans la company_id=1 **************************
SQL="""
    INSERT INTO res_company_users_rel (cid, user_id)
    VALUES (1,2)
    ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


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
#******************************************************************************


#** res_country ***************************************************************
CountrySrc2Dst = GetCountrySrc2Dst(cr_src,cr_dst)
MigrationChampTable(db_src,db_dst,'res_partner', 'country_id', CountrySrc2Dst)
#******************************************************************************


#** ir_attachment *************************************************************
cde="rsync -rva /home/odoo/.local/share/Odoo/filestore/"+db_src+"/ /home/odoo/.local/share/Odoo/filestore/"+db_dst
lines=os.popen(cde).readlines()

SQL="""
    update ir_attachment set res_field='image_128'  where res_field='image_small';
    update ir_attachment set res_field='image_1920' where res_field='image';
"""
cnx_dst,cr_dst=GetCR(db_dst)
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Groupes *******************************************************************
MigrationResGroups(db_src,db_dst)
#******************************************************************************








