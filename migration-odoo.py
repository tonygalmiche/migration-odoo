#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *

#** Paramètres *****************************************************************
db_src = "coheliance8"
db_dst = "coheliance14"
#*******************************************************************************


#** Paramètres *****************************************************************
if len(sys.argv)<2:
    print('action obligatoire en paramètre : ')
    print('- liste_bases : Liste des bases Odoo')
    print('- liste_tables db : Liste des tables de db')
    print('- contenu_table db table')
    print('- liste_champs db table')
    print('- compare_modules : Compare les modules disponibles et installés entre 2 bases')
    print('- compare_res_groups : Compare les groupes de la table res_groups entre 2 bases')
    print('- compare_tables : Compare les tables entre 2 bases')
    print('- compare_champs table : Compare les champs d\'une table entre 2 bases')
    print('- table2csv table : table de db_src dans /tmp/table.csv')
    print('- csv2screen table : Afficher /tmp/table.csv à l\'écran')
    print('- csv2table table : /tmp/table.csv dans table de db_dst')
    print('- migration_table table : table à migrer de db_src vers db_dst')
    print('- migration_res_groups : Migration des groupes par utilisateur de db_src vers db_dst')

    sys.exit()
action = sys.argv[1]
#*******************************************************************************


# ** Connexion aux 2 bases *****************************************************
cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)
# ******************************************************************************


if action=='liste_bases':
    cnx,cr=GetCR('postgres')
    SQL="""
        select datname,usename 
        from pg_database inner join pg_user on usesysid=datdba
        where usename='odoo'
        order by datname
    """
    cr.execute(SQL)
    rows = cr.fetchall()
    for row in rows:
        print('-',row['datname'])


if action=='liste_tables':
    if len(sys.argv)!=3:
        print('base obligatoire pour cette action')
        sys.exit()
    db = sys.argv[2]
    cnx,cr=GetCR(db)
    tables = ListeTables(cr)
    for table in tables:
        nb = CountRow(cr, table)
        print(s(table,50)+' : nb='+str(nb))


if action=='contenu_table':
    if len(sys.argv)!=4:
        print('base et table obligatoire pour cette action')
        sys.exit()
    db    = sys.argv[2]
    table = sys.argv[3]
    cnx,cr=GetCR(db)
    SQL="SELECT * FROM "+table
    cr.execute(SQL)
    rows = cr.fetchall()
    nb=len(rows)
    print('database', db,nb, 'tables')
    for row in rows:
        print(row)
    print("\n\n")


if action=='liste_champs':
    if len(sys.argv)!=4:
        print('base et table obligatoire pour cette action')
        sys.exit()
    db    = sys.argv[2]
    table = sys.argv[3]
    cnx,cr=GetCR(db)
    res = GetChampsTable(cr,table)
    for row3 in res:
        print('-',s(row3[0],30),row3[1])


if action=='compare_modules':
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    modules_src=GetModules(cr_src)
    modules_dst=GetModules(cr_dst)
    modules = modules_src + modules_dst # Concatener les 2 listes
    modules = list(set(modules))        # Supprimer les doublons
    modules.sort()                      # Trier
    for module in modules:
        ok_src = ok_dst = state_src = state_dst = ''
        if module in modules_src:
            ok_src='OK'
            state_src='state_src='+GetInfosModule(cr_src,module)['state']
        if module in modules_dst:
            ok_dst='OK'
            state_dst='state_dst='+GetInfosModule(cr_dst,module)['state']
        print('-',s(module,30),s(state_src,25),s(state_dst,25),s(ok_src,8),s(ok_dst,8))


if action=='compare_res_groups':
    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    groups_src=GetGroups(cr_src)
    groups_dst=GetGroups(cr_dst)
    groups = groups_src + groups_dst # Concatener les 2 listes
    groups = list(set(groups))        # Supprimer les doublons
    groups.sort()                      # Trier
    for group in groups:
        ok_src = ok_dst = test = ''
        if group in groups_src:
            ok_src='OK'
        if group in groups_dst:
            ok_dst='OK'
        if ok_src=='' or ok_dst=='':
            test='test'
        print('-',s(group,30),s(ok_src,8),s(ok_dst,8),s(test,8))


if action=='compare_champs':
    if len(sys.argv)!=3:
        print('table obligatoire pour cette action')
        sys.exit()
    table = sys.argv[2]
    champs_src = GetChamps(cr_src,table)
    champs_dst = GetChamps(cr_dst,table)
    champs = champs_src + champs_dst # Concatener les 2 listes
    champs = list(set(champs))       # Supprimer les doublons
    champs.sort()                    # Trier
    print('-',s('champ',30),s('type_src',30),s('type_dst',30),s('ok_src',8),s('ok_dst',8))
    for champ in champs:
        ok_src = ok_dst = type_src = type_dst = ''
        if champ in champs_src:
            ok_src='ok_src'
            type_src = GetChampsTable(cr_src,table,champ)[0][1]
        if champ in champs_dst:
            ok_dst='ok_dst'
            type_dst = GetChampsTable(cr_dst,table,champ)[0][1]
        print('-',s(champ,30),s(type_src,30),s(type_dst,30),s(ok_src,8),s(ok_dst,8))


if action=='compare_tables':
    tables_src = ListeTables(cr_src)
    tables_dst = ListeTables(cr_dst)
    tables = tables_src + tables_dst # Concatener les 2 listes
    tables = list(set(tables))       # Supprimer les doublons
    tables.sort()                    # Trier
    nb=len(tables)
    ct=0
    print(s('ct/nb',10),s('table',60),s('nb_src',10),s('nb_dst',10),s('nb_champs_src',15),s('nb_champs_dst',15),s('test1',10),s('test2',10))
    for table in tables:
        ct+=1
        nb_src = nb_dst = nb_champs_src = nb_champs_dst = ''
        if table in tables_src:
            nb_src = CountRow(cr_src, table)
            nb_champs_src = NbChampsTable(cr_src, table)
        if table in tables_dst:
            nb_dst = CountRow(cr_dst, table)
            nb_champs_dst = NbChampsTable(cr_dst, table)

        test1=test2=test3=test4=''
        if nb_src=='' or nb_dst=='':
            test1='test1'
        if str(nb_src)!=str(nb_dst):
            test2='test2'
        if str(nb_src)!='' and nb_src>0 and nb_dst=='':
            test3='test3'
        if str(nb_src)!='' and nb_src>0 and str(nb_dst)!='':
            test4='test4'
        print(s(str(ct)+'/'+str(nb),10),s(table,50),s(nb_src,8),s(nb_dst,8),s(nb_champs_src,8),s(nb_champs_dst,8),s(test1,6),s(test2,6),s(test3,6),s(test4,6))
    print("test1 : nb_src=='' or nb_dst==''")
    print("test2 : str(nb_src)!=str(nb_dst)")
    print("test3 : nb_src>0 and nb_dst=='' => Données dans la table source et table de destination inexistante")
    print("test4 : str(nb_src)!='' and nb_src>0 and str(nb_dst)!='' => La table existe dans les 2 bases et contient des données dans src")


if action=='table2csv':
    if len(sys.argv)!=3:
        print('table obligatoire pour cette action')
        sys.exit()
    table = sys.argv[2]
    Table2CSV(cr_src,table)


if action=='csv2screen':
    #Source : https://docs.python.org/fr/3.6/library/csv.html
    if len(sys.argv)!=3:
        print('table obligatoire pour cette action')
        sys.exit()
    table = sys.argv[2]
    path = "/tmp/"+table+".csv"
    with open(path, newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in spamreader:
            print('|'.join(row))


if action=='csv2table':
    if len(sys.argv)!=3:
        print('table obligatoire pour cette action')
        sys.exit()
    table = sys.argv[2]
    path = "/tmp/"+table+".csv"
    CSV2Table(cnx_dst,cr_dst,table)


if action=='migration_table':
    """Migre uniquement les champs communs aux 2 bases"""
    if len(sys.argv)!=3:
        print('table obligatoire pour cette action')
        sys.exit()
    table = sys.argv[2]
    MigrationTable(db_src,db_dst,table)


if action=='migration_res_groups':
    """Migration des groupes par utilisateur de db_src vers db_dst"""
    MigrationResGroups(db_src,db_dst)






