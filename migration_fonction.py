# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import csv
import base64
import magic
import os
import json
import html
import shutil
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


def MigrationTable(db_src,db_dst,table_src,table_dst=False,rename={},default={},where="",text2jsonb=False,exclure=[]):
    """exclure : colonnes communes à ne pas reprendre (ex : type changé entre les versions)"""
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
            if champ in champs_src and champ in champs_dst and champ not in exclure:
                communs.append(champ)
        champs=','.join(communs)
        Table2CSV(cr_src,table_src,champs,rename=rename,default=default,where=where,text2jsonb=text2jsonb, cr_dst=cr_dst,table_dst=table_dst,db_src=db_src)
        CSV2Table(cnx_dst,cr_dst,table_src,table_dst,db_src=db_src)
        SetSequence(cr_dst,cnx_dst,table_dst)


def MigrationTablesTruncate(db_src,db_dst,tables):
    """Migration rapide de grosses tables (plusieurs millions de lignes), à la place de MigrationTable :
    - TRUNCATE au lieu de DELETE : instantané et sans lignes mortes à nettoyer ensuite par le VACUUM
    - COPY ... WITH (FREEZE) dans la même transaction que le TRUNCATE : pas de VACUUM de gel ensuite,
      et pas d'écriture dans le WAL si le serveur est en wal_level = minimal
    - VACUUM (ANALYZE) à la fin, pour ne pas laisser l'autovacuum le faire au mauvais moment
    Les tables sont vidées ensemble, dans une seule transaction : il faut passer dans la même liste
    les tables liées entre elles (ex : is_presse_cycle et is_presse_cycle_of_rel).
    Pas de CASCADE : si une autre table référence l'une d'elles, le TRUNCATE échoue et rien n'est modifié
    (MigrationTable, avec son DELETE, ne vérifie pas les clés étrangères)."""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    copies=[]
    for table in tables:
        communs = GetChampsCommuns(cr_src,cr_dst,table)
        Table2CSV(cr_src,table,','.join(communs),db_src=db_src)
        path = "/tmp/%s-%s.csv"%(db_src or 'x',table)
        champs = ','.join('"%s"'%champ for champ in communs) # Guillemets pour les noms réservés (order, default...)
        copies.append((table,champs,path))
    SQL = ""
    for table in tables:
        SQL+="ALTER TABLE "+table+" DISABLE TRIGGER ALL;\n"
    SQL+="TRUNCATE "+", ".join(tables)+";\n"
    for table,champs,path in copies:
        SQL+="COPY "+table+" ("+champs+") FROM '"+path+"' WITH (FORMAT csv, HEADER, FREEZE);\n"
    for table in tables:
        SQL+="ALTER TABLE "+table+" ENABLE TRIGGER ALL;\n"
    cr_dst.execute(SQL)
    cnx_dst.commit()
    for table in tables:
        SetSequence(cr_dst,cnx_dst,table)
    cnx_dst.rollback()        # SetSequence laisse la transaction en erreur sur une table sans id (table de relation)
    cnx_dst.autocommit = True # VACUUM ne peut pas s'exécuter dans une transaction
    for table in tables:
        cr_dst.execute("VACUUM (ANALYZE) "+table)
    cnx_dst.autocommit = False


def GetTypesChamps(cr,table):
    """Dictionnaire {colonne: type postgresql} d'une table (vide si la table n'existe pas)"""
    SQL="select column_name,data_type from information_schema.columns where table_schema='public' and table_name=%s"
    cr.execute(SQL,[table])
    return {row['column_name']: row['data_type'] for row in cr.fetchall()}


def MigrationTableJsonb(db_src,db_dst,table,rename={}):
    """Copie ligne à ligne d'une petite table dont des champs texte sont devenus traduisibles (jsonb) :
    valeur => {"en_US": valeur, "fr_FR": traduction ou valeur}. La traduction est lue dans ir_translation
    si elle existe dans la source (v14, v15). Remplace MigrationTable(text2jsonb=True) quand la source est
    en v16 ou plus (ir_translation supprimée). rename : {colonne source: colonne destination}"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    types_src = GetTypesChamps(cr_src,table)
    types_dst = GetTypesChamps(cr_dst,table)
    if not types_src or not types_dst:
        return
    communs = [c for c in types_src if rename.get(c,c) in types_dst]
    jsons   = [c for c in communs if types_dst[rename.get(c,c)]=='jsonb' and types_src[c]!='jsonb']
    ir_translation = bool(GetTypesChamps(cr_src,'ir_translation'))
    cr_src.execute("select "+','.join(communs)+" from "+table)
    rows = cr_src.fetchall()
    cr_dst.execute("alter table "+table+" disable trigger all; delete from "+table+";")
    for row in rows:
        for c in jsons:
            if row[c] is not None:
                fr = row[c]
                if ir_translation and 'id' in row:
                    fr = GetTraduction(cr_src,table.replace('_','.'),c,row['id']) or row[c]
                row[c] = json.dumps({"en_US": row[c], "fr_FR": fr})
        SQL="insert into "+table+" ("+','.join(rename.get(c,c) for c in communs)+") values ("+','.join(['%s']*len(communs))+")"
        cr_dst.execute(SQL,[row[c] for c in communs])
    cr_dst.execute("alter table "+table+" enable trigger all")
    cnx_dst.commit()
    SetSequence(cr_dst,cnx_dst,table)


def MigrationHrEmployee(db_src,db_dst,hr_responsible_id=2):
    """Migration des employés d'une v14, v15 ou v16 vers une v19 ou v20.
    Depuis la v19, hr.employee hérite de hr.version (_inherits) : une partie des champs de l'employé (département,
    poste, calendrier, situation familiale, adresse privée...) est dans hr_version, et chaque employé a une
    version courante (current_version_id). Cette fonction :
    - copie resource_resource, hr_department, hr_job, hr_employee_category, employee_category_rel et hr_employee
      avec leurs ids (à appeler après res_partner, res_users et res_company)
    - crée une hr_version par employé à partir des champs de la source, datée de la création de l'employé
    - parent_path des départements (absent en v14/v15) recalculé
    - work_contact_id (v16+) absent en v14/v15 : repris du partenaire de l'utilisateur lié s'il y en a un
    - hr_responsible_id : utilisateur responsable RH des versions (obligatoire en v20, inexistant avant)
    - work_location_id : obligatoire dans la fiche en v20 => "Office" (hr.home_work_office) si absent de la source
    Non repris (affiché en fin de traitement s'il y a des données) : contrats (hr_contract), départs,
    lieux de travail (hr_work_location, ou texte libre work_location en v14), calendriers absents de la destination
    (remplacés par le calendrier de la société)."""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    cr_dst.execute("select id,resource_calendar_id from res_company order by id limit 1")
    company = cr_dst.fetchone()
    cr_dst.execute("select id from resource_calendar")
    calendriers_dst = [row['id'] for row in cr_dst.fetchall()]
    cr_dst.execute("select id from hr_work_location order by id")
    lieux_dst = [row['id'] for row in cr_dst.fetchall()]
    # Lieu de travail obligatoire dans la fiche employé en v20 (vide => champ en rouge) : "Office" par défaut
    lieu_defaut = ExternalId2Id(cr_dst,'home_work_office',module='hr',model='hr.work.location') or (lieux_dst and lieux_dst[0]) or None

    # ** Tables liées ************************************************************
    MigrationTable(db_src,db_dst,'resource_resource')
    SQL="update resource_resource set calendar_id=%s where calendar_id is null or calendar_id not in (select id from resource_calendar)"
    cr_dst.execute(SQL,[company['resource_calendar_id']])
    cnx_dst.commit()
    MigrationTableJsonb(db_src,db_dst,'hr_department')
    # parent_path absent en v14/v15 : vide => erreur du panneau des départements de la liste des employés
    # ('bool' object has no attribute 'split' dans _operator_parent_of_domain)
    parent_store_compute(cr_dst,cnx_dst,'hr_department','parent_id')
    MigrationTableJsonb(db_src,db_dst,'hr_job')
    cr_dst.execute("update hr_job set company_id=%s where company_id is null",[company['id']]) # obligatoire en v20
    cnx_dst.commit()
    MigrationTableJsonb(db_src,db_dst,'hr_employee_category')
    if 'emp_id' in GetTypesChamps(cr_src,'employee_category_rel'):
        MigrationTableJsonb(db_src,db_dst,'employee_category_rel',rename={'emp_id':'employee_id'})
    else:
        MigrationTableJsonb(db_src,db_dst,'employee_category_rel')

    # ** Employés ****************************************************************
    MigrationTable(db_src,db_dst,'hr_employee')
    SQL="""
        update hr_employee e set work_contact_id=u.partner_id
        from res_users u where u.id=e.user_id and e.work_contact_id is null
    """
    cr_dst.execute(SQL)
    cnx_dst.commit()

    # ** Employé manager ou coach de lui-même : toléré avant, message "Certains employés apparaissent dans une boucle" en v20
    cr_dst.execute("select id,name from hr_employee where parent_id=id or coach_id=id")
    for row in cr_dst.fetchall():
        print("MigrationHrEmployee : %s (id %s) était son propre manager ou coach : lien retiré"%(row['name'],row['id']))
    cr_dst.execute("update hr_employee set parent_id=null where parent_id=id")
    cr_dst.execute("update hr_employee set coach_id=null where coach_id=id")
    cnx_dst.commit()
    SQL="""
        with recursive chaine(depart, courant, chemin, boucle) as (
            select id, parent_id, array[id], false from hr_employee where parent_id is not null
          union all
            select c.depart, e.parent_id, c.chemin || c.courant, c.courant = any(c.chemin)
            from chaine c join hr_employee e on e.id = c.courant
            where not c.boucle and e.parent_id is not null
        )
        select distinct depart from chaine where boucle order by depart
    """
    cr_dst.execute(SQL)
    for row in cr_dst.fetchall():
        print("MigrationHrEmployee : boucle de managers à corriger à la main, employé id %s"%row['depart'])

    # ** Une version par employé *************************************************
    champs_src = GetTypesChamps(cr_src,'hr_employee')
    cr_dst.execute("delete from hr_version")
    SQL="""
        select e.*, r.tz as resource_tz, p.street, p.street2, p.zip, p.city, p.state_id,
               p.country_id as private_country_id, p.email as partner_email, p.phone as partner_phone
        from hr_employee e join resource_resource r on r.id=e.resource_id
                           left join res_partner p on p.id=e.address_home_id
        order by e.id
    """
    cr_src.execute(SQL)
    for row in cr_src.fetchall():
        v = lambda champ: row[champ] if champ in champs_src else None
        employee_type = v('employee_type') or 'employee'
        employee_type_id = ExternalId2Id(cr_dst,'contract_type_'+employee_type,module='hr',model='hr.employee.type') or None
        calendar_id = v('resource_calendar_id')
        if calendar_id not in calendriers_dst:
            calendar_id = company['resource_calendar_id']
        work_location_id = v('work_location_id') if v('work_location_id') in lieux_dst else lieu_defaut
        create_date = row['create_date'] or datetime.now()
        vals = {
            'employee_id'            : row['id'],
            'company_id'             : row['company_id'],
            'active'                 : True,
            'date_version'           : create_date.date(),
            'last_modified_date'     : datetime.now(),
            'last_modified_uid'      : hr_responsible_id,
            'hr_responsible_id'      : hr_responsible_id,
            'resource_calendar_id'   : calendar_id,
            'tz'                     : row['resource_tz'] or 'Europe/Paris',
            'marital'                : v('marital') or 'single',
            'distance_home_work_unit': 'kilometers',
            'distance_home_work'     : v('km_home_work'),
            'km_home_work'           : v('km_home_work'),
            'department_id'          : v('department_id'),
            'job_id'                 : v('job_id'),
            'job_title'              : v('job_title'),
            'address_id'             : v('address_id'),
            'work_location_id'       : work_location_id,
            'country_id'             : v('country_id'),
            'identification_id'      : v('identification_id'),
            'passport_id'            : v('passport_id'),
            'children'               : v('children'),
            'spouse_complete_name'   : v('spouse_complete_name'),
            'spouse_birthdate'       : v('spouse_birthdate'),
            'sex'                    : v('gender') if v('gender') in ('male','female') else None,
            'employee_type_id'       : employee_type_id,
            'private_street'         : row['street'],
            'private_street2'        : row['street2'],
            'private_zip'            : row['zip'],
            'private_city'           : row['city'],
            'private_state_id'       : row['state_id'],
            'private_country_id'     : row['private_country_id'],
            'create_uid'             : row['create_uid'],
            'create_date'            : create_date,
            'write_uid'              : row['write_uid'],
            'write_date'             : row['write_date'],
        }
        SQL="insert into hr_version ("+','.join(vals)+") values ("+','.join(['%s']*len(vals))+") returning id"
        cr_dst.execute(SQL,list(vals.values()))
        version_id = cr_dst.fetchone()['id']
        SQL="""
            update hr_employee set current_version_id=%s,
                   private_email=coalesce(private_email,%s), private_phone=coalesce(private_phone,%s)
            where id=%s
        """
        cr_dst.execute(SQL,[version_id,row['partner_email'],row['partner_phone'],row['id']])
    cnx_dst.commit()
    SetSequence(cr_dst,cnx_dst,'hr_version')

    # ** Données non reprises ****************************************************
    controles = [
        ("Contrats (hr_contract)"                , "select count(*) as nb from hr_contract"),
        ("Employés avec une date de départ"      , "select count(*) as nb from hr_employee where departure_date is not null"),
        ("Lieux de travail (hr_work_location)"   , "select count(*) as nb from hr_work_location"),
        ("Lieux de travail en texte libre (v14)" , "select count(*) as nb from hr_employee where coalesce(work_location,'')<>''"),
    ]
    for libelle,SQL in controles:
        try:
            cr_src.execute(SQL)
            nb = cr_src.fetchone()['nb']
            if nb:
                print("MigrationHrEmployee : non repris : %s : %s"%(libelle,nb))
        except psycopg2.Error:
            cnx_src.rollback() # colonne ou table absente dans cette version
    SQL="""
        select c.id, c.name, count(*) as nb from hr_employee e join resource_calendar c on c.id=e.resource_calendar_id
        group by c.id, c.name order by c.id
    """
    cr_src.execute(SQL)
    for row in cr_src.fetchall():
        if row['id'] not in calendriers_dst:
            print("MigrationHrEmployee : calendrier %s (%s) absent de la destination : %s employés passés sur le calendrier de la société"%(row['id'],row['name'],row['nb']))


def SubtypeId2SubtypeId(cr_src,cr_dst):
    """Correspondance {id sous-type source: id sous-type destination} des mail_message_subtype par identifiant externe"""
    SQL="select d.module, d.name, d.res_id from ir_model_data d where d.model='mail.message.subtype'"
    cr_dst.execute(SQL)
    dst = {(row['module'],row['name']): row['res_id'] for row in cr_dst.fetchall()}
    cr_src.execute(SQL)
    return {row['res_id']: dst.get((row['module'],row['name'])) for row in cr_src.fetchall()}


def TrackingValues2Html(cr_src,message_id):
    """Suivi des modifications d'un message (table mail_tracking_value, v14 à v18) au format HTML de la v20
    (gabarit mail.mail_tracking_template : "ancienne valeur → <b>nouvelle valeur</b> <i>(libellé)</i>").
    En v20, mail_tracking_value n'existe que si le module mail_tracking est installé : le suivi est dans le corps."""
    cr_src.execute("select * from mail_tracking_value where mail_message_id=%s order by tracking_sequence, id",[message_id])
    lignes=[]
    for t in cr_src.fetchall():
        valeurs=[]
        for sens in ('old','new'):
            v=None
            for suffixe in ('char','text','integer','float','monetary','datetime'):
                x = t.get(sens+'_value_'+suffixe)
                if x not in (None,'') and not (suffixe=='integer' and t['field_type'] in ('many2one','char','selection')):
                    v=x
                    break
            if isinstance(v,float):
                v = int(v) if v.is_integer() else round(v,2)
            valeurs.append('' if v is None else html.escape(str(v)))
        old,new=valeurs
        ligne = (old+' ' if old else '')+'→ <b>'+new+'</b> <i>('+html.escape(t['field_desc'] or '')+')</i>'
        lignes.append(ligne)
    if not lignes:
        return ''
    return '<div>'+'<br>'.join(lignes)+'</div>'


def MigrationChatter(db_src,db_dst,models):
    """Migration du chatter (messages et abonnés) des modèles donnés, d'une v14, v15 ou v16 vers une v19 ou v20 :
    - les messages et abonnés existants de ces modèles dans la destination sont supprimés, puis ceux de la source
      sont insérés avec de nouveaux ids (parent_id recalculé)
    - sous-types (subtype_id) : correspondance par identifiant externe
    - suivi des modifications (mail_tracking_value) : ajouté au corps du message, comme le fait la v20
    Les notifications ne sont pas reprises. Pièces jointes des messages (message_attachment_rel) : non reprises ici ;
    la fonction retourne la correspondance {id message source: id message destination} pour les recoller ensuite."""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    subtypes = SubtypeId2SubtypeId(cr_src,cr_dst)
    champs = [c for c in GetChampsCommuns(cr_src,cr_dst,'mail_message') if c not in ('id','parent_id','subtype_id','mail_server_id')]
    tracking = bool(GetTypesChamps(cr_src,'mail_tracking_value'))

    # ** Messages ****************************************************************
    cr_dst.execute("delete from mail_message where model in %s",[tuple(models)])
    cr_src.execute("select * from mail_message where model in %s order by id",[tuple(models)])
    ids={}
    nb=0
    for row in cr_src.fetchall():
        vals = {c: row[c] for c in champs}
        vals['subtype_id'] = subtypes.get(row['subtype_id'])
        vals['parent_id']  = ids.get(row['parent_id'])
        if tracking:
            html_tracking = TrackingValues2Html(cr_src,row['id'])
            if html_tracking:
                vals['body'] = (row['body'] or '')+html_tracking
        SQL="insert into mail_message ("+','.join(vals)+") values ("+','.join(['%s']*len(vals))+") returning id"
        cr_dst.execute(SQL,list(vals.values()))
        ids[row['id']] = cr_dst.fetchone()['id']
        nb+=1
    cnx_dst.commit()

    # ** Abonnés *****************************************************************
    cr_dst.execute("delete from mail_followers where res_model in %s",[tuple(models)])
    cr_src.execute("select * from mail_followers where res_model in %s and partner_id is not null order by id",[tuple(models)])
    nb_followers=0
    for row in cr_src.fetchall():
        SQL="""
            insert into mail_followers (res_model,res_id,partner_id) values (%s,%s,%s)
            on conflict do nothing returning id
        """
        cr_dst.execute(SQL,[row['res_model'],row['res_id'],row['partner_id']])
        res = cr_dst.fetchone()
        if not res:
            continue
        nb_followers+=1
        cr_src.execute("select mail_message_subtype_id from mail_followers_mail_message_subtype_rel where mail_followers_id=%s",[row['id']])
        for rel in cr_src.fetchall():
            subtype_id = subtypes.get(rel['mail_message_subtype_id'])
            if subtype_id:
                SQL="insert into mail_followers_mail_message_subtype_rel (mail_followers_id,mail_message_subtype_id) values (%s,%s) on conflict do nothing"
                cr_dst.execute(SQL,[res['id'],subtype_id])
    cnx_dst.commit()
    print("MigrationChatter : %s messages et %s abonnés repris"%(nb,nb_followers))
    return ids


def MigrationPiecesJointes(db_src,db_dst,where,filestore="/home/odoo/.local/share/Odoo/filestore",copier_fichiers=True):
    """Copie des pièces jointes (ir_attachment) sélectionnées par la clause where (sur la source) avec de nouveaux ids,
    et de leurs fichiers d'un filestore à l'autre (<filestore>/<db_src>/xx/... => <filestore>/<db_dst>/xx/...).
    Les pièces jointes de la destination qui ont le même res_model, res_field et res_id sont d'abord supprimées
    (une seule fois, avant les copies : un enregistrement peut avoir plusieurs pièces jointes).
    copier_fichiers=False : données seulement (store_fname conservé : fichiers à copier ensuite, ex : filestore de
    production copié tel quel). Sinon, les fichiers absents du filestore source sont affichés.
    Retourne la correspondance {id source: id destination} (tables de relation, pièce jointe principale...)."""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    champs = [c for c in GetChampsCommuns(cr_src,cr_dst,'ir_attachment') if c!='id']
    cr_src.execute("select * from ir_attachment where "+where+" order by id")
    rows = cr_src.fetchall()
    cles = {(row['res_model'],row['res_id'],row['res_field'] or '') for row in rows}
    for res_model,res_id,res_field in cles:
        SQL="delete from ir_attachment where res_model=%s and res_id=%s and coalesce(res_field,'')=%s"
        cr_dst.execute(SQL,[res_model,res_id,res_field])
    ids={}
    manquants=[]
    for row in rows:
        SQL="insert into ir_attachment ("+','.join(champs)+") values ("+','.join(['%s']*len(champs))+") returning id"
        cr_dst.execute(SQL,[row[c] for c in champs])
        ids[row['id']] = cr_dst.fetchone()['id']
        if copier_fichiers and row['store_fname']:
            src = os.path.join(filestore,db_src,row['store_fname'])
            dst = os.path.join(filestore,db_dst,row['store_fname'])
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dst),exist_ok=True)
                shutil.copy2(src,dst)
            else:
                manquants.append(row['store_fname'])
    cnx_dst.commit()
    print("MigrationPiecesJointes : %s pièces jointes reprises"%len(rows))
    if manquants:
        print("MigrationPiecesJointes : %s fichiers absents de %s, à copier dans %s :"%(len(manquants),os.path.join(filestore,db_src),os.path.join(filestore,db_dst)))
        for f in manquants:
            print("  "+f)
    return ids


def MigrationIrFilters(db_src,db_dst,modules={}):
    """Migration des filtres favoris (ir_filters) :
    - action_id : l'id des actions change d'une version à l'autre => on retrouve l'action de la base destination
      par son identifiant externe (ir_model_data). modules permet de gérer les modules renommés
      (ex : {'is_kmymoney18': 'is_kmymoney20'}). Si l'action n'est pas retrouvée, action_id est vidé
      (le filtre, et surtout un filtre par défaut, s'applique alors à tous les menus du modèle)
    - utilisateur : correspondance par login. À partir d'Odoo 19, user_id est remplacé par la table
      de liaison ir_filters_res_users_rel (sans cette reprise, les filtres personnels deviennent partagés)
    """
    MigrationTable(db_src,db_dst,'ir_filters')
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)

    # ** action_id ************************************************************
    SQL="""
        select f.id, d.module, d.name
        from ir_filters f inner join ir_model_data d on d.model like 'ir.actions.%%' and d.res_id=f.action_id
        where f.action_id is not null
    """
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    cr_dst.execute("update ir_filters set action_id=NULL")
    for row in rows:
        module = modules.get(row['module'], row['module'])
        SQL="""
            update ir_filters set action_id=(
                select res_id from ir_model_data where model like 'ir.actions.%%' and module=%s and name=%s limit 1
            )
            where id=%s
        """
        cr_dst.execute(SQL,(module,row['name'],row['id']))
    cnx_dst.commit()

    # ** Utilisateur ***********************************************************
    if 'user_id' in GetChamps(cr_src,'ir_filters'):
        # Source < 19 : colonne user_id
        SQL="""
            select f.id, u.login
            from ir_filters f inner join res_users u on f.user_id=u.id
        """
    else:
        # Source >= 19 : table de liaison ir_filters_res_users_rel
        SQL="""
            select r.ir_filters_id as id, u.login
            from ir_filters_res_users_rel r inner join res_users u on r.res_users_id=u.id
        """
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    if 'user_id' in GetChamps(cr_dst,'ir_filters'):
        # Destination < 19 : colonne user_id
        cr_dst.execute("update ir_filters set user_id=NULL")
        for row in rows:
            SQL="update ir_filters set user_id=(select id from res_users where login=%s) where id=%s"
            cr_dst.execute(SQL,(row['login'],row['id']))
    else:
        # Destination >= 19 : table de liaison ir_filters_res_users_rel
        cr_dst.execute("delete from ir_filters_res_users_rel")
        for row in rows:
            SQL="""
                insert into ir_filters_res_users_rel (ir_filters_id, res_users_id)
                select %s, id from res_users where login=%s
            """
            cr_dst.execute(SQL,(row['id'],row['login']))
    cnx_dst.commit()


def MigrationIsSetColumnWidth(db_src,db_dst,modules={}):
    """Migration des largeurs de colonnes mémorisées (module is_set_column_width) :
    - view_key = "modèle,list,id_vue[,champ relationnel,list],champs triés..." : l'id de la vue (3e élément)
      change d'une version à l'autre => on retrouve la vue de la base destination par son identifiant externe.
      modules permet de gérer les modules renommés (ex : {'is_kmymoney18': 'is_kmymoney20'})
    - utilisateur : correspondance par login
    - Mise à jour ou création par (utilisateur, view_key) : les lignes déjà présentes en destination sont conservées
    """
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    # Module absent de la source ou pas encore installé dans la destination => rien à faire
    if not GetChamps(cr_src,'is_set_column_width') or not GetChamps(cr_dst,'is_set_column_width'):
        print("MigrationIsSetColumnWidth : table is_set_column_width absente de %s ou %s => ignoré"%(db_src,db_dst))
        return
    SQL="""
        select w.view_key, w.column_widths, u.login
        from is_set_column_width w inner join res_users u on u.id=w.user_id
    """
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for row in rows:
        parts = row['view_key'].split(',')
        if len(parts)>2 and parts[2].isdigit():
            SQL="select module, name from ir_model_data where model='ir.ui.view' and res_id=%s limit 1"
            cr_src.execute(SQL,(int(parts[2]),))
            xmlid = cr_src.fetchone()
            view_id = False
            if xmlid:
                module = modules.get(xmlid['module'], xmlid['module'])
                SQL="select res_id from ir_model_data where model='ir.ui.view' and module=%s and name=%s limit 1"
                cr_dst.execute(SQL,(module,xmlid['name']))
                res = cr_dst.fetchone()
                if res:
                    view_id = res['res_id']
            if not view_id:
                print("MigrationIsSetColumnWidth : vue %s non retrouvée => ignorée (%s)"%(parts[2],row['view_key']))
                continue
            parts[2] = str(view_id)
        view_key = ','.join(parts)
        cr_dst.execute("select id from res_users where login=%s",(row['login'],))
        user = cr_dst.fetchone()
        if not user:
            print("MigrationIsSetColumnWidth : utilisateur %s non trouvé => ignoré"%row['login'])
            continue
        cr_dst.execute("delete from is_set_column_width where user_id=%s and view_key=%s",(user['id'],view_key))
        SQL="""
            insert into is_set_column_width (user_id, view_key, column_widths, create_uid, create_date, write_uid, write_date)
            values (%s, %s, %s, %s, now() at time zone 'UTC', %s, now() at time zone 'UTC')
        """
        cr_dst.execute(SQL,(user['id'],view_key,row['column_widths'],user['id'],user['id']))
    cnx_dst.commit()


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


def MigrationDonneesTable(db_src,db_dst,table,exclure=[]): # ,text2jsonb=False):
    """Met à jour les champs communs (non jsonb) des lignes existantes de la destination avec les valeurs de la source.
    currency_id : les ids des devises changent d'une version à l'autre (ex : id 1 = EUR en v16, USD en v20)
    => correspondance par le code de la devise. exclure : colonnes à ne pas reprendre"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    champs = GetChampsCommuns(cr_src,cr_dst,table)
    for champ in champs:
        if champ in exclure:
            continue
        if champ=='currency_id':
            SQL="SELECT t.id, c.name FROM "+table+" t JOIN res_currency c ON c.id=t.currency_id"
            cr_src.execute(SQL)
            for row in cr_src.fetchall():
                SQL="UPDATE "+table+" SET currency_id=(SELECT id FROM res_currency WHERE name=%s) WHERE id=%s AND EXISTS (SELECT 1 FROM res_currency WHERE name=%s)"
                cr_dst.execute(SQL,[row['name'],row['id'],row['name']])
            continue
        json=False
        type_champ = GetChampsTable(cr_dst,table,champ)
        if type_champ:
            if type_champ[0][1]=="jsonb":
                json=True
        if not json:
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


def MigrationUtilisateursTechniques(db_src,db_dst):
    """Correctif des utilisateurs techniques décalés, à appeler après MigrationResGroups quand res_users est copiée
    d'une version ≤ 18 vers une version ≥ 19 (base.default_user supprimé en v19 => ids décalés d'un cran).
    Voir Documentation/migration-odoo/correctif-utilisateurs-techniques-odoo19-agenda.md
    - les identifiants externes base des utilisateurs et partenaires pointent sur les ids de la source
    - le paramètre base.template_portal_user_id reprend la valeur de la source
    - l'ancien utilisateur default (inexistant en destination) perd tous ses groupes (il avait les droits internes)
    - public et portaltemplate ne gardent que group_public et group_portal
    Les ids des utilisateurs ne changent pas : ils sont référencés partout.
    Redémarrer Odoo ensuite (identifiants externes en cache)."""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    SQL="select model,name,res_id from ir_model_data where module='base' and model in ('res.users','res.partner')"
    cr_src.execute(SQL)
    for row in cr_src.fetchall():
        SQL="update ir_model_data set res_id=%s where module='base' and model=%s and name=%s"
        cr_dst.execute(SQL,[row['res_id'],row['model'],row['name']])
    cr_src.execute("select value from ir_config_parameter where key='base.template_portal_user_id'")
    for row in cr_src.fetchall():
        cr_dst.execute("update ir_config_parameter set value=%s where key='base.template_portal_user_id'",[row['value']])
    default_user_id = ExternalId2Id(cr_src,'default_user',module='base',model='res.users')
    if default_user_id and not ExternalId2Id(cr_dst,'default_user',module='base',model='res.users'):
        cr_dst.execute("delete from res_groups_users_rel where uid=%s",[default_user_id])
        cr_dst.execute("update res_users set share=true where id=%s",[default_user_id]) # share est calculé par l'ORM
    for user,group in [('public_user','group_public'),('template_portal_user_id','group_portal')]:
        uid = ExternalId2Id(cr_dst,user,module='base',model='res.users')
        gid = ExternalId2GroupId(cr_dst,group,module='base')
        if uid and gid:
            cr_dst.execute("delete from res_groups_users_rel where uid=%s and gid<>%s",[uid,gid])
            cr_dst.execute("insert into res_groups_users_rel (gid,uid) values (%s,%s) on conflict do nothing",[gid,uid])
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



def SetDefaultValue(db,model,field_name,account_code):
    "Valeurs par défaut dans la nouvelle table de Odoo 18 ir_default"
    cnx,cr=GetCR(db)
    field_id = GetFielsdId(cr,model,field_name)
    account_id = JsonAccountCode2Id(cr,account_code) 
    SQL="UPDATE ir_default SET json_value=%s WHERE field_id=%s"

    cr.execute(SQL,[account_id,field_id])
    cnx.commit()


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


def getPropertyValue(db,model,property,id):
    cnx,cr=GetCR(db)
    fields_id = GetFielsdId(cr,model,property)
    res_id = "%s,%s"%(model,id)
    SQL="""
        select *
        from ir_property
        where fields_id=%s and res_id=%s
    """

    cr.execute(SQL,[fields_id,res_id])
    rows = cr.fetchall()
    value=False
    for r in rows:   
        if r["res_id"] and r["value_reference"]:
            value  = r["value_reference"].split(",")[1]
    return value



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


def MigrationIrProperty2JsonField(db_src,db_dst,model,property_src,field_dst,key="1"):
    """Migration des données d'une property vers un champ Json"""
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
            set_json_property(cr_dst,cnx_dst,table,res_id,field_dst,key,value)


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


# Cette fonction dans Odoo retourne les comptes (account_id) pas défaut en fonction de la localisation fiscale
# def _get_fr_template_data(self):
#     return {
#         'code_digits': 6,
#         'property_account_receivable_id': 'fr_pcg_recv',
#         'property_account_payable_id': 'fr_pcg_pay',
#         'property_account_expense_categ_id': 'pcg_607_account',
#         'property_account_income_categ_id': 'pcg_707_account',
#         'property_account_downpayment_categ_id': 'pcg_4191',
#     }
# J'ai résolu ce problème avec ir_default


def AccountCode2Id(cr,code):
    SQL="select id from account_account where code=%s limit 1"
    cr.execute(SQL,[code])
    rows = cr.fetchall()
    id=False
    for row in rows:
        id=row["id"]
    return id


def JsonAccountCode2Id(cr,code,key=1):
    "Depuis Odoo 18, les properties sont enregistrées en json directement dans les tables"
    SQL="select id from account_account where code_store->>'%s'='%s' limit 1"%(key,code)
    cr.execute(SQL)
    rows = cr.fetchall()
    id=False
    for row in rows:
        id=row["id"]
    return id


def set_json_property(cr,cnx,table,id,field_name,key,val):
    "Depuis Odoo 18, les properties sont enregistrées en json directement dans les tables"
    json_val=json.dumps({key: val})
    SQL="UPDATE "+table+" SET "+field_name+"=%s WHERE id=%s"
    cr.execute(SQL,[json_val,id])
    cnx.commit()


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


def init_res_id_ir_attachment_Many2many(cr_dst,cnx_dst,table_relation,doc_field,attachment_field):
    """
        Initialiser le res_id de ir_attachment pour les champs Many2many avec chat ('mail.thread') 
        pour résoudre le problème d'accès aux pieces jointes
    """
    SQL="SELECT %s, %s from %s"%(doc_field,attachment_field,table_relation)
    cr_dst.execute(SQL)
    rows = cr_dst.fetchall()
    for row in rows:
        SQL="UPDATE ir_attachment SET res_id=%s WHERE id=%s and res_id=0 and res_model is not null"
        cr_dst.execute(SQL,[row[doc_field],row[attachment_field]])
    cnx_dst.commit()





def MigrationIrModelData(db_src,db_dst,models,correspondances={}):
    """Identifiants externes des modèles repris avec les ids de la source (comptes, taxes, journaux...).
    Après la copie, les identifiants de la destination pointent sur les ids de la destination, qui désignent
    maintenant d'autres enregistrements (les ids se chevauchent). Comme une mise à niveau d'Odoo :
    - un identifiant de la destination reprend l'enregistrement de la source qui portait le même nom
      (module ignoré : l10n_fr.1_pcg_411 => account.1_pcg_411 ; préfixe de société 1_ ajouté si besoin :
      l10n_fr.tax_group_tva_20 => account.1_tax_group_tva_20), même s'il a été renommé depuis
    - un identifiant sans équivalent dans la source est supprimé (pour des données XML en noupdate,
      le -u du module recrée alors l'enregistrement standard)
    - les identifiants de la source absents de la destination ne sont pas ajoutés (au -u, Odoo supprime
      les enregistrements dont l'identifiant n'est plus dans les données du module)
    correspondances : {modèle: {nom de l'identifiant de la destination: id de la source}} pour les identifiants
    renommés entre les versions (ex : product.product_category_all en v15 => product.product_category_goods en v20)
    Voir Documentation/migration-odoo/migration-vers-odoo20.md § 5.4"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    for model in models:
        table = model.replace('.','_')
        cr_src.execute("select name,res_id from ir_model_data where model=%s order by id",[model])
        src = {}
        for row in cr_src.fetchall():
            src.setdefault(row['name'],row['res_id'])
        cr_dst.execute("select id from "+table)
        ids_dst = {row['id'] for row in cr_dst.fetchall()}
        cr_dst.execute("select id,name from ir_model_data where model=%s",[model])
        repris = supprimes = 0
        for row in cr_dst.fetchall():
            name = row['name']
            res_id = src.get(name)
            if res_id is None and name.startswith('1_'):
                res_id = src.get(name[2:])
            if name in correspondances.get(model,{}):
                res_id = correspondances[model][name]
            if res_id in ids_dst:
                cr_dst.execute("update ir_model_data set res_id=%s where id=%s",[res_id,row['id']])
                repris+=1
            else:
                cr_dst.execute("delete from ir_model_data where id=%s",[row['id']])
                supprimes+=1
        print("MigrationIrModelData : %s : %s identifiants repris, %s supprimés"%(model,repris,supprimes))
    cnx_dst.commit()


def AccountTypeParCode(codes,fichiers):
    """Type de compte v17+ (account_type) déduit du code : type du compte du plan comptable standard dont le
    code a le plus long début commun (ex : 411AUE => 411000 => asset_receivable, 512001 => asset_cash).
    codes : liste des codes ; fichiers : CSV du plan comptable de la localisation (colonnes code, account_type),
    ex : /opt/odoo20/addons/l10n_fr_account/data/template/account.account-fr.csv et account.account-fr_comp.csv.
    Retourne {code: account_type}"""
    modeles = []
    for fichier in fichiers:
        for row in csv.DictReader(open(fichier)):
            if row.get('code') and row.get('account_type'):
                modeles.append((row['code'],row['account_type']))
    res = {}
    for code in codes:
        meilleur = None
        for code_modele,account_type in modeles:
            n = len(os.path.commonprefix([code,code_modele]))
            if meilleur is None or n > meilleur[0]:
                meilleur = (n,account_type)
        res[code] = meilleur[1] if meilleur and meilleur[0] > 0 else 'income'
    return res


def MigrationDevisesParCode(db_src,db_dst,tables):
    """Conversion des devises des tables copiées avec MigrationTable : les ids de res_currency changent d'une version
    à l'autre (ex : EUR = 1 en v15, 126 en v20 ; 1 = USD en v20). Toutes les colonnes de la table qui référencent
    res_currency (currency_id, company_currency_id...) sont converties en une seule requête par colonne (pas d'effet
    de chaîne 1 => 126, 2 => 1), par le code de la devise"""
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    cr_src.execute("select id,name from res_currency")
    codes_src = {row['id']:row['name'] for row in cr_src.fetchall()}
    cr_dst.execute("select id,name from res_currency")
    ids_dst = {row['name']:row['id'] for row in cr_dst.fetchall()}
    correspondances = {id_src:ids_dst[code] for id_src,code in codes_src.items() if code in ids_dst}
    if not correspondances:
        return
    cas = ' '.join('when %s then %s'%(a,b) for a,b in correspondances.items())
    for table in tables:
        SQL="""
            select a.attname as colonne
            from pg_constraint c join pg_class t on t.oid=c.conrelid join pg_class cf on cf.oid=c.confrelid
            join pg_attribute a on a.attrelid=c.conrelid and a.attnum=c.conkey[1]
            where c.contype='f' and t.relname=%s and cf.relname='res_currency'
        """
        cr_dst.execute(SQL,[table])
        for row in cr_dst.fetchall():
            colonne = row['colonne']
            cr_dst.execute("update "+table+" set "+colonne+" = case "+colonne+" "+cas+" end where "+colonne+" is not null")
    cnx_dst.commit()
