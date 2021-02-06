#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *

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


tables=[
    'is_base_documentaire',
    'is_niveau',
    'is_region',
    'is_sport',
    'is_statut',
    'is_statut_sportif',
    'res_partner_title',
    'res_partner_category',
    'res_partner',
    'res_partner_res_partner_category_rel',
    'res_users',
    'res_company_users_rel',
    'res_partner_financeur_rel',
    'calendar_event_type',
    'calendar_event',
    'calendar_event_res_partner_rel',
    'meeting_category_rel',
    'crm_phonecall',
]
for table in tables:
    rename=default={}
    if table=="calendar_event":
        default={
            'privacy': 'public',
        }
    if table=="crm_phonecall":
        default={
            'direction': 'out',
        }
    if table=="res_users":
        default={
            'notification_type': 'email',
        }
    MigrationTable(db_src,db_dst,table,rename=rename,default=default)


# ** calendar_attendee ********************************************************
table = 'calendar_attendee'
default={
    'partner_id': 1,
    'event_id': 1,
}
MigrationTable(db_src,db_dst,table,default=default)

SQL="SELECT id,partner_id, event_id FROM calendar_attendee"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    if row['event_id']:
        SQL="UPDATE calendar_attendee SET event_id=%s WHERE id=%s"
        cr_dst.execute(SQL,[row['event_id'],row['id']])
    if row['partner_id']:
        SQL="UPDATE calendar_attendee SET partner_id=%s WHERE id=%s"
        cr_dst.execute(SQL,[row['partner_id'],row['id']])
cnx_dst.commit()
# *****************************************************************************


# #** Migration mot de passe **************************************************
SQL="SELECT id,password_crypt FROM res_users"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE res_users SET password=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['password_crypt'],row['id']])
cnx_dst.commit()
# #****************************************************************************


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
#******************************************************************************


#** Mettre le nouveau user_id 2 dans la company_id=1 **************************
SQL="""
    INSERT INTO res_company_users_rel (cid, user_id)
    VALUES (1,2)
    ON CONFLICT DO NOTHING
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** res_partner ***************************************************************
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


#** Groupes *******************************************************************
MigrationResGroups(db_src,db_dst)
#******************************************************************************


#** Problème installation module eCommerce ************************************
cr_dst.execute("update res_users set active='f' where id=1")
cr_dst.execute("delete  from res_groups_users_rel where uid=3")
cr_dst.execute("update res_users set active='t' where id=3")
cnx_dst.commit()
#******************************************************************************




print("Pour finaliser la migration, il faut démarrer Odoo avec cette commande : ")
print("/opt/odoo-14/odoo-bin -c /etc/odoo/nouvelle-trajectoire.con")
name = input("Appuyer sur Entrée pour continuer") 


# ** ir_attachment ************************************************************
table = 'ir_attachment'
rename={
    'file_type': 'mimetype',
}
MigrationTable(db_src,db_dst,table,rename=rename)
SQL="""
    update ir_attachment set res_field='image_128'  where res_field='image_small';
    update ir_attachment set res_field='image_1920' where res_field='image';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


# ** image dans res_partner dans ir_attachment ********************************
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

