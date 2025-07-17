#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "france-filets-communication13"
db_dst = "france-filets-communication18"
#******************************************************************************

cnx,cr=GetCR(db_src)
cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)
debut=datetime.now()
debut = Log(debut, "Début migration")


#** res_partner ***************************************************************
MigrationTable(db_src,db_dst,'res_partner_title',text2jsonb=True)
default={
#    'autopost_bills': 'ask',
}
MigrationTable(db_src,db_dst,'res_partner',text2jsonb=True,default=default)
#******************************************************************************


#** res_users *****************************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** res_groups ****************************************************************
MigrationTable(db_src,db_dst,'res_company_users_rel')
MigrationResGroups(db_src,db_dst)
# #****************************************************************************


#** mailing_mailing ***************************************************************
default={
    "schedule_type": "now",
}
MigrationTable(db_src,db_dst,'mailing_mailing', default=default,text2jsonb=True)
#******************************************************************************


#** utm_campaign ***************************************************************
default={
    "title": "tmp",
}
MigrationTable(db_src,db_dst,'utm_campaign', default=default,text2jsonb=True)
#******************************************************************************


# ** Tables utm **********************************************************
tables=[
    'utm_medium',
    'utm_stage',
    'utm_tag',
]
for table in tables:
    print(table)
    MigrationTable(db_src,db_dst,table,text2jsonb=True)
#******************************************************************************


#** utm_source ***************************************************************
#** Il faut un name unique => J'ajoute l'id au bout du name
SQL="SELECT id,name FROM utm_source order by id"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows: 
    name_list = row['name'].split('\t')
    name_src=name_list[0]
    name_dst="%s\t%s"%(name_src, row['id'])
    SQL="UPDATE utm_source SET name=%s WHERE id=%s"
    cr_src.execute(SQL,[name_dst,row['id']])
cnx_src.commit()
MigrationTable(db_src,db_dst,'utm_source',text2jsonb=True)
#******************************************************************************


# ** Tables diverses **********************************************************
tables=[
     'is_mailing_list_assistant',
    'is_region',
    'is_segment',
    'link_tracker',
    'link_tracker_click',
    'link_tracker_code',
    'mail_alias',
    'mail_mail',
    'mail_mass_mailing_list_rel',
    'mail_message',
    'mail_message_res_partner_rel',
    'mail_message_subtype',
    'mail_template',
    'mail_tracking_value',
    'mailing_contact',
    'mailing_list',
]
for table in tables:
    print(table)
    MigrationTable(db_src,db_dst,table,text2jsonb=True)
MigrationTable(db_src,db_dst,'mailing_contact_list_rel',table_dst="mailing_subscription")
#******************************************************************************

cr_dst.execute("DELETE FROM mail_alias")
cr_dst.execute("UPDATE mailing_mailing set calendar_date=sent_date")
cr_dst.execute("UPDATE mailing_mailing set favorite_date=sent_date")
cr_dst.execute("update mailing_mailing set mailing_model_id=396")
cnx_dst.commit()


#** mailing_trace ***************************************************************
rename={
   'opened' : 'open_datetime',
   'replied': 'reply_datetime',
   'sent'   : 'sent_datetime',
   'state'  : 'trace_status',
}
MigrationTable(db_src,db_dst,'mailing_trace',rename=rename)
states={
    'bounced': 'bounce',
    'exception': 'error',
    'ignored': 'cancel',
    'opened': 'open',
    'outgoing': 'outgoing',
    'replied': 'reply',
    'sent': 'sent',
}
for state in states:
    trace_status=states[state]
    SQL="UPDATE mailing_trace set trace_status=%s WHERE trace_status=%s"
    cr_dst.execute(SQL,[trace_status,state])
cnx_dst.commit()
#******************************************************************************


#** mail_activity_type ***************************************************************
default={
   'chaining_type': 'suggest',
}
MigrationTable(db_src,db_dst,'mail_activity_type',default=default,text2jsonb=True)
#******************************************************************************


#** mail_followers ***************************************************************
SQL="DELETE FROM mail_followers where partner_id is null"
cr_src.execute(SQL)
cnx_src.commit()
MigrationTable(db_src,db_dst,'mail_followers')
#******************************************************************************


# ** Tables diverses **********************************************************
tables=[
    'mail_followers_mail_message_subtype_rel',
]
for table in tables:
    MigrationTable(db_src,db_dst,table,text2jsonb=True)
#******************************************************************************


debut = Log(debut, "Fin migration")
