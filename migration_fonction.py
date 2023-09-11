# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import csv
import base64
import magic
import os
import json
#from xmlrpc import client as xmlrpclib
import xmlrpc.client
from datetime import datetime



def Log(debut,msg):
    now = datetime.now()
    print("%s : %06.2fs : %s"%(now.strftime('%H:%M:%S') , (now-debut).total_seconds(), msg))
    return now


def s(txt,lg=0):
    if lg>0:
        txt=(str(txt)+u'                                                                                                 ')[:lg]
    return txt


def GetCR(db):
    try:
        cnx = psycopg2.connect("dbname='"+db+"'")
    except:
        print("Connexion à la base "+db+" impossible !")
        sys.exit()
    cr = cnx.cursor(cursor_factory=RealDictCursor)
    return cnx,cr


def CountRow(cursor,table):
    SQL="""
        SELECT count(*) as ct
        FROM """+table+"""
    """
    cursor.execute(SQL)
    rows2 = cursor.fetchall()
    nb=0
    for row2 in rows2:
        nb=row2['ct']
    return nb


def ListeTables(cr):
    SQL="""
        SELECT tablename
        FROM pg_catalog.pg_tables
        WHERE schemaname != 'pg_catalog'AND schemaname != 'information_schema'
        ORDER BY tablename
    """
    cr.execute(SQL)
    rows = cr.fetchall()
    res=[]
    for row in rows:
        res.append(row['tablename'])
    return res


def GetChamps(cursor,table):
    SQL="""
        SELECT
            a.attname
        FROM
            pg_catalog.pg_attribute a
        WHERE
            a.attrelid = (
                SELECT oid
                FROM pg_catalog.pg_class
                WHERE relname='"""+table+"""' AND relnamespace = (
                    SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = 'public'
                )
            )
            AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attname
    """
    cursor.execute(SQL)
    rows = cursor.fetchall()
    res=[]
    for row in rows:
        v = row['attname']
        if v=="order":
            v='"order"'
        if v=="references":
            v='"references"'
        if v=="default":
            v='"default"'
        res.append(v)
    return res


def GetDistinctVal(cursor,table,champ):
    SQL="select distinct t."+champ+" from "+table+" t"
    cursor.execute(SQL)
    rows = cursor.fetchall()
    return len(rows)


def GetChampsTable(cursor,table,champ=False):
    SQL="""
        SELECT
            a.attname,
            pg_catalog.format_type(a.atttypid, a.atttypmod) as type,
            a.attnotnull, a.atthasdef,
            -- adef.adsrc,
            pg_catalog.col_description(a.attrelid, a.attnum) AS comment
        FROM
            pg_catalog.pg_attribute a
            LEFT JOIN pg_catalog.pg_attrdef adef ON a.attrelid=adef.adrelid AND a.attnum=adef.adnum
        WHERE
            a.attrelid = (
                SELECT oid
                FROM pg_catalog.pg_class
                WHERE relname='"""+table+"""' AND relnamespace = (
                    SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = 'public'
                )
            )
            AND a.attnum > 0 AND NOT a.attisdropped
    """
    if champ:
        SQL+=" AND a.attname='"""+champ+"""' """
    SQL+="""
        ORDER BY a.attname
    """
    cursor.execute(SQL)
    rows = cursor.fetchall()
    res=[]
    for row in rows:
        nb = GetDistinctVal(cursor,table,row['attname'])
        res.append([row['attname'],row['type'], nb])
    return res


def GetModules(cursor):
    SQL="SELECT name FROM ir_module_module"
    cursor.execute(SQL)
    rows = cursor.fetchall()
    res=[]
    for row in rows:
        res.append(row['name'])
    return res


def GetExternalIdGroups(cursor):
    """Liste des external id des groupes"""
    SQL="""
        select name
        from ir_model_data
        where model='res.groups' 
        order by name 
    """
    cursor.execute(SQL)
    rows = cursor.fetchall()
    res=[]
    for row in rows:
        res.append(row['name'])
    return res


def GetGroup(cursor,external_id):
    """Infos sur un groupe à partir de son external id"""
    SQL="""
        select 
            i.module, 
            g.name,
            i.res_id 
        from ir_model_data i inner join res_groups g on g.id=i.res_id 
        where i.model='res.groups' and i.name='"""+external_id+"""' 
        order by i.module,i.name 
    """
    cursor.execute(SQL)
    rows = cursor.fetchall()
    res=[]
    for row in rows:
        res=row
    return res


def GetInfosModule(cursor,module):
    SQL="SELECT id,state FROM ir_module_module WHERE name='"+module+"'"
    cursor.execute(SQL)
    rows = cursor.fetchall()
    res=[]
    for row in rows:
        res=row
    return res


def NbChampsTable(cursor,table):
    SQL="""
        SELECT
            a.attname,
            pg_catalog.format_type(a.atttypid, a.atttypmod) as type,
            a.attnotnull, a.atthasdef,
            -- adef.adsrc,
            pg_catalog.col_description(a.attrelid, a.attnum) AS comment
        FROM
            pg_catalog.pg_attribute a
            LEFT JOIN pg_catalog.pg_attrdef adef ON a.attrelid=adef.adrelid AND a.attnum=adef.adnum
        WHERE
            a.attrelid = (
                SELECT oid
                FROM pg_catalog.pg_class
                WHERE relname='"""+table+"""' AND relnamespace = (
                    SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = 'public'
                )
            )
            AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attname
    """
    cursor.execute(SQL)
    rows = cursor.fetchall()
    nb=len(rows)
    return nb


#def Table2CSV(cr_src,table,champs='*',rename=False, default=False,where="", text2jsonb=False, cr_dst=False, table_dst=False, db_src=False):

def SQL2CSV(db_src, table, SQL):
    cnx_src,cr_src=GetCR(db_src)
    cr_src = cnx_src.cursor('BigCursor', cursor_factory=RealDictCursor)
    cr_src.itersize = 50000 # Rows fetched at one time from the server => Permet de limiter l'utilisation de la mémoire
    cr_src.execute(SQL)
    #table="stock_move_line"
    path = "/tmp/%s-%s.csv"%(db_src or 'x',table)
    ct=0
    f = open(path, 'w', newline ='')
    for row in cr_src:
        if ct==0:
            keys=[]
            for key in row:
                keys.append(key)
            f.write(','.join(keys)+'\r\n')
            writer = csv.DictWriter(f, fieldnames=keys)
        writer.writerow(row)
        ct+=1
    f.close()


def Table2CSV(cr_src,table,champs='*',rename=False, default=False,where="", text2jsonb=False, cr_dst=False, table_dst=False, db_src=False):
    SQL="SELECT "+champs+" FROM "+table+" t"
    if where!="":
        SQL=SQL+" WHERE "+where
    #path = "/tmp/"+table+".csv"
    path = "/tmp/%s-%s.csv"%(db_src or 'x',table)
    if rename or default or text2jsonb:
        cr_src.execute(SQL)
        rows = cr_src.fetchall()
        keys1 = []
        keys2 = []
        for row in rows:
            for k in row:
                x=k
                keys1.append(x)
                if k in rename:
                    x=rename[k]
                keys2.append(x)
            break
        for x in default:
            if x not in keys1:
                keys1.append(x)
            if x not in keys2:
                keys2.append(x)
        f = open(path, 'w', newline ='')
        writer = csv.DictWriter(f, fieldnames=keys1)
        f.write(','.join(keys2)+'\r\n')
        jsons=[]
        if text2jsonb and cr_dst:
            for key in keys2:
                type_champ = GetChampsTable(cr_dst,(table_dst or table),key)
                if type_champ:
                    if type_champ[0][1]=="jsonb":
                        jsons.append(key)
        for row in rows:
            for x in default:
                v = default[x]
                if x in row:
                    if row[x]:
                        v = row[x]
                row[x] = v
            for x in jsons:
                v=row[x]
                if v:
                    model=table.replace("_",".")
                    v=GetTraduction(cr_src, model, x, row["id"]) or v
                    val={
                        "en_US": v,
                        "fr_FR": v,
                    }
                    row[x]=json.dumps(val)
            writer.writerow(row)
        f.close()
    else:
        #Source : https://kb.objectrocket.com/postgresql/from-postgres-to-csv-with-python-910
        SQL_for_file_output = "COPY ({0}) TO STDOUT WITH CSV HEADER".format(SQL)
        with open(path, 'w') as f_output:
            cr_src.copy_expert(SQL_for_file_output, f_output)


def CSV2Table(cnx_dst,cr_dst,table_src,table_dst=False, db_src=False):
    #Source : https://www.postgresqltutorial.com/import-csv-file-into-posgresql-table/
    if not table_dst:
        table_dst=table_src
    path = "/tmp/%s-%s.csv"%(db_src or 'x',table_src)
    f = open(path, "r")
    champs = f.readline()
    # order est un nom de champ réservé dans une table postgresql
    champs=champs.replace(',order,','",order",') 
    if champs[0:6]=="order,":
        champs='"order",'+champs[6:]
    if champs[0:11]=="references,":
        champs='"references",'+champs[11:]
    if champs[0:8]=="default,":
        champs='"default",'+champs[8:]
    if len(champs)>0:
        SQL="""
            ALTER TABLE """+table_dst+""" DISABLE TRIGGER ALL;
            DELETE FROM """+table_dst+""";
            COPY """+table_dst+""" ("""+champs+""") FROM '"""+path+"""' DELIMITER ',' CSV HEADER;
            ALTER TABLE """+table_dst+""" ENABLE TRIGGER ALL;
        """
        cr_dst.execute(SQL)
        res=cnx_dst.commit()


def SetSequence(cr_dst,cnx_dst,table):
    try:
        sequence=1
        SQL="select id from "+table+" order by id desc limit 1"
        cr_dst.execute(SQL)
        rows = cr_dst.fetchall()
        for row in rows:
            sequence=row['id']+1
        SQL="select setval('"+table+"_id_seq',"+str(sequence)+")"
        cr_dst.execute(SQL)
        cnx_dst.commit()
    except:
        pass


def DumpRestoreTable(db_src,db_dst,table):
    """ Cela permet en particuler de résoudre le problème avec la table mail_message_subtype qui contient le champ default qui est un nom réservé"""
    cde='pg_dump -Fc --data-only -d '+db_src+' -t "'+table+'" > "/tmp/'+table+'.dump" 2>/dev/null'
    os.popen(cde).readlines()
    cde='pg_restore --data-only -d '+db_dst+' -t "'+table+'" /tmp/'+table+'.dump'
    os.popen(cde).readlines()


def MigrationTable(db_src,db_dst,table_src,table_dst=False,rename={},default={},where="",text2jsonb=False):
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)

    SQL="select * from %s limit 1"%table_src
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    #print("%s : len=%s"%(table_src,len(rows)))
    if len(rows)>0:
        if not table_dst:
            table_dst=table_src
        champs_src = GetChamps(cr_src,table_src)
        champs_dst = GetChamps(cr_dst,table_dst)
        champs = champs_src + champs_dst # Concatener les 2 listes
        for k in rename:
            champs_src.append(k)
            champs_dst.append(k)
        champs = list(set(champs))       # Supprimer les doublons
        champs.sort()                    # Trier
        communs=[]
        for champ in champs:
            if champ in champs_src and champ in champs_dst:
                communs.append(champ)
        champs=','.join(communs)
        Table2CSV(cr_src,table_src,champs,rename=rename,default=default,where=where,text2jsonb=text2jsonb, cr_dst=cr_dst,table_dst=table_dst,db_src=db_src)
        CSV2Table(cnx_dst,cr_dst,table_src,table_dst,db_src=db_src)
        SetSequence(cr_dst,cnx_dst,table_dst)


def CopieTable(db_src,db_dst,table,where):
    "Permet de copier certaines lignes d'une table dans une autre base avec une clause where"
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    champs_src = GetChamps(cr_src,table)
    champs_src.remove('id') #Suppression de l'id pour pouvoir faire des insert into sans doublons
    champs=",".join(champs_src)
    SQL="SELECT * FROM %s WHERE %s"%(table,where)
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for row in rows:
        x=[]
        values=[]
        for line in  champs_src:
            x.append("%s")
            values.append(row[line])
        x=",".join(x)
        SQL="""
            INSERT INTO %s (%s)
            VALUES (%s)
        """%(table,champs,x)
        cr_dst.execute(SQL,values)
    cnx_dst.commit()


def GetChampsCommuns(cr_src,cr_dst,table):
    """Retourne la liste des champs communs aux 2 tables"""
    champs_src = GetChamps(cr_src,table)
    champs_dst = GetChamps(cr_dst,table)
    champs = champs_src + champs_dst # Concatener les 2 listes
    champs = list(set(champs))       # Supprimer les doublons
    champs.sort()                    # Trier
    communs=[]
    for champ in champs:
        if champ in champs_src and champ in champs_dst:
            communs.append(champ)
    return(communs)


def MigrationDonneesTable(db_src,db_dst,table):
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    champs = GetChampsCommuns(cr_src,cr_dst,table)
    for champ in champs:
        SQL="SELECT id,"+champ+" FROM "+table
        cr_src.execute(SQL)
        rows = cr_src.fetchall()
        for row in rows:
            v = row[champ]
            if v:
                SQL="UPDATE "+table+" SET "+champ+"=%s WHERE id=%s"
                cr_dst.execute(SQL,[v,row['id']])
    cnx_dst.commit()


def GroupName2Id(cr,name):
    SQL="select id from res_groups where name='"+name+"' limit 1"
    cr.execute(SQL)
    rows = cr.fetchall()
    id=0
    for row in rows:
        id=row['id']
    return id




def ExternalId2Id(cr,external_id,module=False,model=False):
    SQL="select res_id from ir_model_data where name='%s' "%external_id
    if module:
        SQL+=" and module='%s'"%module
    if model:
        SQL+=" and model='%s'"%model
    cr.execute(SQL)
    rows = cr.fetchall()
    id=0
    for row in rows:
        id=row['res_id']
        break
    return id




def ExternalId2GroupId(cr,external_id,module=False):
    SQL="""
        select res_id
        from ir_model_data 
        where model='res.groups' and name='"""+external_id+"""'
    """
    if module:
        SQL+=" and module='%s'"%module
    cr.execute(SQL)
    rows = cr.fetchall()
    id=0
    for row in rows:
        id=row['res_id']
    return id


def MigrationResGroups(db_src,db_dst):
    """Migration des groupes par utilisateur en se basant sur l'external id du groupe"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    SQL="""
        select r.gid,r.uid,g.name,i.name external_id
        from res_groups_users_rel r inner join res_groups g on g.id=r.gid
                                    inner join ir_model_data i on g.id=i.res_id and i.model='res.groups'
    """
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for row in rows:
        external_id = row['external_id']
        gid = ExternalId2GroupId(cr_dst,external_id)
        uid = row['uid']
        if uid==1:
            uid=2
        if gid:
            SQL="""
                INSERT INTO res_groups_users_rel (gid, uid)
                VALUES ("""+str(gid)+""","""+str(uid)+""")
                ON CONFLICT DO NOTHING
            """
            cr_dst.execute(SQL)
    cnx_dst.commit()


def AddUserGroupToOtherGroup(db_dst, group_src_external_id, group_dst_external_id):
    """Ajoute les utilisateurs d'un groupe dans un autre groupe"""
    cnx_dst,cr_dst=GetCR(db_dst)
    group_src_id = ExternalId2GroupId(cr_dst,group_src_external_id)
    group_dst_id = ExternalId2GroupId(cr_dst,group_dst_external_id)
    SQL="select * from res_groups_users_rel where gid=%s"
    cr_dst.execute(SQL,[group_src_id])
    rows = cr_dst.fetchall()
    for row in rows:
        AddUserInGroup(db_dst, group_dst_id, row["uid"])


def AddUserInGroup(db_dst, gid, uid):
    """Ajout d'un utilisateur dans un groupe"""
    cnx_dst,cr_dst=GetCR(db_dst)
    SQL="""
        INSERT INTO res_groups_users_rel (gid, uid)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """
    cr_dst.execute(SQL, [gid,uid])
    cnx_dst.commit()


def GetFielsdId(cr,model,field):
    SQL="""
        select  id,name,model
        from ir_model_fields
        where model='"""+model+"""' and name='"""+field+"""'
    """
    cr.execute(SQL)
    rows = cr.fetchall()
    fields_id=0
    for row in rows:
        fields_id=row['id']
    return fields_id


def GetCountrySrc2Dst(cr_src,cr_dst):
    """Correspondance entre les id src et dst de res_country"""
    SQL="""
        SELECT id,name
        FROM res_country
        ORDER BY name
    """
    CountrySrc2Dst={}
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for row in rows:
        SQL="""
            SELECT id
            FROM res_country
            WHERE name=%s
        """
        cr_dst.execute(SQL,[row['name']])
        rows_dst = cr_dst.fetchall()
        for row_dst in rows_dst:
            CountrySrc2Dst[row['id']]=row_dst['id']
    return CountrySrc2Dst


def MigrationChampTable(db_src,db_dst,table,champ,ids):
    """Migration des id d'un champ d'une table à partir des ids"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)

    SQL="SELECT id,"+champ+" FROM "+table
    cr_dst.execute(SQL)
    rows = cr_dst.fetchall()
    for row in rows:
        id_src=row[champ]
        if id_src:
            id_dst = ids[id_src]
            SQL="UPDATE "+table+" SET "+champ+"=%s WHERE id=%s"
            cr_dst.execute(SQL,[
                    id_dst,
                    row['id'],
                ]
            )
    cnx_dst.commit()


def MigrationIrProperty2Field(db_src,db_dst,model,property_src,field_dst):
    """Migration des données d'une property vers un champ"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    fields_id_src = GetFielsdId(cr_src,model,property_src)
    SQL="""
        select *
        from ir_property
        where fields_id="""+str(fields_id_src)+"""
        order by name,res_id
    """
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    table=model.replace(".","_")
    for r in rows:
        if r["res_id"] and r["value_reference"]:
            value  = r["value_reference"].split(",")[1]
            res_id = r["res_id"].split(",")[1]
            SQL="select id from product_pricelist where id=%s"
            cr_dst.execute(SQL,[value])
            pricelists = cr_dst.fetchall()
            if len(pricelists)>0:
                SQL="UPDATE "+table+" SET "+field_dst+"=%s WHERE id=%s"
                cr_dst.execute(SQL,[value,res_id])
            #else:
            #    print("ERROR",SQL, value,res_id)
    cnx_dst.commit()


def MigrationIrProperty(db_src,db_dst,model,field_src,field_dst=False):
    """Migration des données de la table ir_property pour le model et le field indiqué"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    if not field_dst:
        field_dst=field_src
    fields_id_src = GetFielsdId(cr_src,model,field_src)
    fields_id_dst = GetFielsdId(cr_dst,model,field_dst)
    SQL="""
        DELETE FROM ir_property
        WHERE fields_id="""+str(fields_id_dst)+"""
    """
    cr_dst.execute(SQL)
    SQL="""
        select *
        from ir_property
        where fields_id="""+str(fields_id_src)+"""
        order by name,res_id
    """
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for r in rows:
        SQL="""
            INSERT INTO ir_property (name,res_id,company_id,fields_id,value_reference,type,create_uid,create_date,write_uid,write_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cr_dst.execute(SQL, [
            field_dst,
            r['res_id'] or None,
            r['company_id'],
            fields_id_dst,
            r['value_reference'],
            r['type'],
            r['create_uid'],
            r['create_date'],
            r['write_uid'],
            r['write_date'],
        ])
    cnx_dst.commit()


def AccountCode2Id(cr,code):
    SQL="select id from account_account where code=%s limit 1"
    cr.execute(SQL,[code])
    rows = cr.fetchall()
    id=False
    for row in rows:
        id=row["id"]
    return id


def GetFiscalPositionPartner(cr,partner_id):
    SQL="""
        select value_reference 
        from ir_property 
        where 
            res_id='res.partner,%s' and
            name='property_account_position_id'
    """
    cr.execute(SQL,[partner_id])
    rows = cr.fetchall()
    fiscal_position_id=False
    for r in rows:
        v=r['value_reference']
        v=v.split(",")
        fiscal_position_id=v[1]
    return fiscal_position_id


def GetTraduction(cr,model,field,res_id):
    name=model+","+field
    SQL="""
        SELECT value 
        FROM ir_translation 
        WHERE lang='fr_FR' and name='"""+name+"""' and res_id="""+str(res_id)+""" and type='model'
    """
    cr.execute(SQL)
    rows = cr.fetchall()
    value=False
    for row in rows:
        value=row["value"]
    return value


def MigrationNameTraduction(db_src,db_dst,name):
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    SQL="DELETE FROM ir_translation WHERE name='"+name+"'"
    cr_dst.execute(SQL)
    cnx_dst.commit()
    SQL="SELECT * FROM ir_translation WHERE name='"+name+"'"
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for row in rows:
        SQL="""
            INSERT INTO ir_translation (lang, src, name, res_id, module, state, comments, value, type)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """
        cr_dst.execute(SQL,[
                row['lang'],
                row['src'],
                row['name'],
                row['res_id'],
                row['module'],
                row['state'],
                row['comments'],
                row['value'],
                row['type'],
            ])
    cnx_dst.commit()


def MigrationIrSequenceByName(db_src,db_dst,name):
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    sequence_id_src=sequence_id_dst=False

    SQL="SELECT id FROM ir_sequence WHERE name ilike '%"+name+"%'"
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for row in rows:
        sequence_id_src=row["id"]
    cr_dst.execute(SQL)
    rows = cr_dst.fetchall()
    for row in rows:
        sequence_id_dst=row["id"]
    #print(sequence_id_src, sequence_id_dst)
    if sequence_id_src and sequence_id_dst:
        MigrationIrSequence(db_src,db_dst,id_src=sequence_id_src,id_dst=sequence_id_dst)
    return sequence_id_dst




def MigrationIrSequence(db_src,db_dst,id_src=False,id_dst=False):
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    if id_src and id_dst:
        SQL="SELECT id,code,implementation,prefix,padding,number_next,name FROM ir_sequence WHERE id=%s"
        cr_src.execute(SQL,[id_src])
        rows = cr_src.fetchall()
        for row in rows:
            code=row["code"]
            SQL="UPDATE ir_sequence SET name=%s, code=%s, prefix=%s,padding=%s,number_next=%s WHERE id=%s"
            cr_dst.execute(SQL,[row["name"], row["code"], row["prefix"],row["padding"],row["number_next"],id_dst])
            if row["implementation"]=="standard":
                SQL="SELECT id FROM ir_sequence WHERE id=%s"
                cr_dst.execute(SQL,[id_dst])
                rows2 = cr_dst.fetchall()
                for row2 in rows2:
                    seq_id = "%03d" % row["id"]
                    ir_sequence = "ir_sequence_%s"%seq_id
                    SQL="SELECT last_value FROM %s"%ir_sequence
                    cr_src.execute(SQL)
                    rows3 = cr_src.fetchall()
                    for row3 in rows3:
                        seq_id = "%03d" % row2["id"]
                        ir_sequence = "ir_sequence_"+seq_id
                        last_value = row3["last_value"]+1
                        SQL="ALTER SEQUENCE "+ir_sequence+" RESTART WITH %s"
                        cr_dst.execute(SQL,[last_value])
        cnx_dst.commit()


def Memoryview2File(data,path):
    """Converti un champ postgres memoryview contenant des images ou pieces jointes en fichier"""
    f = open(path,'wb')
    image =base64.b64decode(data)
    f.write(image)
    f.close()
    mime=magic.from_file(path, mime=True)
    ext=mime.split('/')[1]
    new_path = path+"."+ext
    os.rename(path,new_path )
    return new_path


def GetAdminPassword():
    try:
        f = open('admin.pwd', 'r')
        for line in f.readlines():
            password = line.strip()
    except FileNotFoundError:
        password='admin'
    return password


def XmlRpcConnection(db_dst):
    url = "http://127.0.0.1:8069"
    username = 'admin'
    password = GetAdminPassword()

    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
    #print(common.version())
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

    #common = xmlrpclib.ServerProxy('{}/xmlrpc/2/common'.format(url))
    #models = xmlrpclib.ServerProxy('{}/xmlrpc/2/object'.format(url))

    #uid = common.login(db_dst, username, password)
    #uid = common.authenticate(db_dst, username, password, {})
    uid=2
    return models,uid,password


def ImageField2IrAttachment(models,db_dst,uid,password,res_model,res_id,ImageField, name=False):
    """Copie un champ image de type binary dans ir_attachment"""
    image=base64.b64decode(ImageField)
    path='/tmp/ImageField'
    f = open(path,'wb')
    f.write(image)
    f.close()
    mime=magic.from_file(path, mime=True)
    ext=mime.split('/')[1]
    new_path = path+"."+ext
    os.rename(path,new_path )
    BytesImage  = open(new_path,'rb').read()
    ImageBase64 = base64.b64encode(BytesImage)
    datas       = ImageBase64.decode('ascii')
    os.unlink(new_path)
    sizes=['image_1024', 'image_256', 'image_512', 'image_128', 'image_1920']

    if name:
        sizes=[name]

    for size in sizes:
        vals={
            'res_model': res_model,
            'name'     : size,
            'res_field': size,
            'res_id'   : res_id,
            'res_name' : res_model+"/"+size,
            'type'     : 'binary',
            'datas'    : datas,
            'mimetype' : mime,
        }
        id = models.execute(db_dst, uid, password, 'ir.attachment', 'create', [vals])



def ImageModel2IrAttachment(cr_src,models,db_dst,uid,password,res_model,res_field, name=False):
    """Copie tous les champs image d'un model dans ir_attachment"""
    table=res_model.replace(".","_")
    SQL="SELECT id,%s from %s where %s is not null"%(res_field,table,res_field)
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    nb=len(rows)
    ct=1
    for row in rows:
        ImageField2IrAttachment(models,db_dst,uid,password,res_model,row["id"],row[res_field], name=name)
        #print(ct,"/",nb,row["id"])
        ct+=1
    #*******************************************************************************




def InvoiceId2MoveId(cr_src,invoice_id):
    """Correspondance entre l'id des factures suite à la migration de account_invoice dans account_move"""
    SQL="SELECT move_id from account_invoice WHERE id="+str(invoice_id)
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    move_id=0
    for row in rows:
        move_id = row['move_id']
    return move_id


def InvoiceIds2MoveIds(cr_src):
    """Correspondances entre account_invoice et account_move"""
    SQL="SELECT id,move_id from account_invoice"
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    ids={}
    for row in rows:
        ids[row['id']] = row['move_id']
    return ids




def SqlSelectFormat(cr,SQL,exclude=[]):
    """Affiche le résultat d'une resquete Select en enlevant les colonnes vides ou identiques"""
    default_exclude=['write_date','write_uid','create_date','create_uid']
    exclude+=default_exclude
    cr.execute(SQL)
    rows = cr.fetchall()
    fields={}
    values={}
    if len(rows)>0:
        row=rows[0]
        for f in row:
            fields[f]=False

    for row in rows:
        for f in row:
            if f not in values:
                values[f]=[]
            if row[f] not in values[f]:
                values[f].append(row[f])

            if row[f] and f not in exclude:
                l=len(str(row[f]))
                if not fields[f] or fields[f]<l:
                    fields[f]=l
    if len(rows)>1:
        for f in fields:
            if len(values[f])==1:
                fields[f]=False
    res=[]
    for row in rows:
        line={}
        for f in row:
            if fields[f]:
                line[f]=str(row[f])
        res.append(line)
    for f in fields:
        if fields[f]:
            if len(f)>fields[f]:
                fields[f]=len(f)
    line=''
    for f in fields:
        if fields[f]:
            #line+=f+' '*(fields[f]-len(f))
            line+=f+'\t'
    for row in res:
        line=''
        for f in row:
            if fields[f]:
                #line+=row[f]+' '*(fields[f]-len(row[f]))+'\t'
                line+=row[f]+'\t'
    line=''


def parent_store_compute(cr,cnx,table,parent):
    """ Compute parent_path field from scratch. """
    # Each record is associated to a string 'parent_path', that represents
    # the path from the record's root node to the record. The path is made
    # of the node ids suffixed with a slash (see example below). The nodes
    # in the subtree of record are the ones where 'parent_path' starts with
    # the 'parent_path' of record.
    #
    #               a                 node | id | parent_path
    #              / \                  a  | 42 | 42/
    #            ...  b                 b  | 63 | 42/63/
    #                / \                c  | 84 | 42/63/84/
    #               c   d               d  | 85 | 42/63/85/
    #
    # Note: the final '/' is necessary to match subtrees correctly: '42/63'
    # is a prefix of '42/630', but '42/63/' is not a prefix of '42/630/'.
    query = """
        WITH RECURSIVE __parent_store_compute(id, parent_path) AS (
            SELECT row.id, concat(row.id, '/')
            FROM {table} row
            WHERE row.{parent} IS NULL
        UNION
            SELECT row.id, concat(comp.parent_path, row.id, '/')
            FROM {table} row, __parent_store_compute comp
            WHERE row.{parent} = comp.id
        )
        UPDATE {table} row SET parent_path = comp.parent_path
        FROM __parent_store_compute comp
        WHERE row.id = comp.id
    """.format(table=table, parent=parent)
    cr.execute(query)
    cnx.commit()

