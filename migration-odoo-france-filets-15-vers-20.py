#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de France Filets : Odoo 15 (is_france_filets15) => Odoo 20 (is_france_filets20)
# Documentation : Documentation/migration-odoo/migration-is_france_filets15-vers-is_france_filets20.md (étape 9)
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "france-filets15"
db_dst = "france-filets20"
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# france-filets20-vierge : base v20 avec is_france_filets20 installé, sans données (à créer par Tony)
# db_vierge = db_dst+'-vierge'
# SQL='DROP DATABASE "'+db_dst+'";CREATE DATABASE "'+db_dst+'" WITH TEMPLATE "'+db_vierge+'"'
# cde="""echo '"""+SQL+"""' | psql postgres"""
# lines=os.popen(cde).readlines()
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** 9.b Contacts, utilisateurs, société **************************************
# Civilités (supprimées d'Odoo en v20, recréées par is_france_filets20) : libellés français pris dans ir_translation
MigrationTable(db_src,db_dst,'res_partner_title')
cr_src.execute("select id from res_partner_title")
for row in cr_src.fetchall():
    for champ in ('name','shortcut'):
        fr = GetTraduction(cr_src,'res.partner.title',champ,row['id'])
        if fr:
            cr_dst.execute("update res_partner_title set "+champ+"=%s where id=%s",[fr,row['id']])
cnx_dst.commit()

# Partenaires (3 127), avec les ids de la source : is_company (case « Société »), mobile et title repris tels quels
# credit_limit : nombre en v15, jsonb (par société) en v20, toujours à 0 => non repris
# autopost_bills : nouvelle colonne obligatoire en v20 (valeur par défaut d'Odoo)
MigrationTable(db_src,db_dst,'res_partner',exclure=['credit_limit'],default={'autopost_bills':'ask'})
MigrationTable(db_src,db_dst,'res_users')
MigrationTable(db_src,db_dst,'res_company_users_rel')

# commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
cr_dst.execute("update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null")
cnx_dst.commit()

# complete_name n'existe pas en v15 => à calculer (même logique que _get_complete_name d'Odoo 20)
SQL="""
    update res_partner p set complete_name = case
        when p.parent_id is not null and not coalesce(p.is_company,false)
            then trim(coalesce(
                (select nullif(c.name,'') from res_partner c where c.id=p.commercial_partner_id),
                (select name from res_partner where id=p.parent_id),
                ''
            ) || ', ' || coalesce(p.name,''))
        else trim(coalesce(p.name,''))
    end;
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# SIRET : colonne siret en v15 => identifiant FR_SIRET de additional_identifiers en v20 (1 partenaire : la société)
cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
cnx_dst.commit()

# Groupes : correspondance par nom d'identifiant externe (is_france_filets15.xxx => is_france_filets20.xxx)
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : utilisateurs techniques décalés (anomalie 15 : l'ancien default perd ses droits)
MigrationUtilisateursTechniques(db_src,db_dst)

# Société : champs simples (nom, e-mail, téléphone, SMS, affacturage, conditions générales, APE, registre du commerce...)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Agencement des documents « Light » (web.external_layout_standard) : sinon l'en-tête France Filets ne s'applique pas
SQL="""
    update res_company set external_report_layout_id=(
        select res_id from ir_model_data where module='web' and name='external_layout_standard'
    )
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Anomalie 14 : inscription libre au portail fermée (b2c en v15)
SQL="""
    insert into ir_config_parameter (key,value) values ('auth_signup.invitation_scope','b2b')
    on conflict (key) do update set value='b2b'
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** 9.c Employés *************************************************************
#******************************************************************************


# ** 9.d Articles et paramètres de vente et de comptabilité *******************
#******************************************************************************


# ** 9.e Ventes ***************************************************************
#******************************************************************************


# ** 9.f Tables métier is_* ***************************************************
#******************************************************************************


# ** 9.g Comptabilité *********************************************************
#******************************************************************************


# ** 9.h Séquences, filtres, valeurs par défaut *******************************
#******************************************************************************


# ** 9.i Chatter **************************************************************
#******************************************************************************


# ** 9.j Pièces jointes (données seulement, fichiers à l'étape 11) ************
#******************************************************************************
