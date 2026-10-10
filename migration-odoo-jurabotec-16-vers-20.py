#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Jurabotec : Odoo 16 (is_jurabotec) => Odoo 20 (is_jurabotec20)
# Documentation : Documentation/migration-odoo/migration-is_jurabotec16-vers-is_jurabotec20.md
from migration_fonction import *


#** Paramètres ****************************************************************
db_src = "jurabotec16"
db_dst = "jurabotec20"
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** res_partner et res_users *************************************************
# Copiés avec les ids de la source (6 064 partenaires, 27 utilisateurs dans jurabotec16)
# mobile (2 336 partenaires) et title (civilité, 20 partenaires) : supprimés d'Odoo en v20, remis par is_jurabotec20
# (civilité : res.partner.title => is.civilite, title => is_civilite)
# company_registry (2 partenaires, dont la société : « R.C.S. 810 944 835 ») : supprimé en v20, non repris
# Nouvelles colonnes en v20 : valeurs par défaut d'Odoo (autopost_bills, group_rfq et group_on sont obligatoires)
# Propriétés comptables (comptes, conditions de paiement, positions fiscales) : à reprendre avec la comptabilité
MigrationTable(db_src,db_dst,'res_partner_title','is_civilite')
MigrationTable(db_src,db_dst,'res_partner',rename={'title':'is_civilite'},default={
    'autopost_bills'  : 'ask',
    'group_rfq'       : 'default',
    'group_on'        : 'default',
    'suggest_based_on': '30_days',
    'suggest_days'    : 7,
    'suggest_percent' : 100,
})
MigrationTable(db_src,db_dst,'res_users')
MigrationTable(db_src,db_dst,'res_company_users_rel')

# Dernière connexion de chaque utilisateur (une ligne par utilisateur, Odoo ne garde que la dernière) :
# sans elle, le statut des utilisateurs est « Invité » au lieu de « Confirmé » (calculé d'après login_date)
MigrationTable(db_src,db_dst,'res_users_log')

# Type d'adresse « private » (adresse privée d'employé) supprimé en v17 => contact (1 partenaire)
cr_dst.execute("update res_partner set type='contact' where type='private'")
cnx_dst.commit()

# commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
cr_dst.execute("update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null")
cnx_dst.commit()

# complete_name n'existe pas en v16 => à calculer (même logique que _get_complete_name d'Odoo 20)
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

# SIRET : colonne siret en v16 => identifiant FR_SIRET de additional_identifiers en v20 (47 partenaires, dont la société)
cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
cnx_dst.commit()

# Étiquettes des partenaires (distribution, menuiserie, SETT)
MigrationTable(db_src,db_dst,'res_partner_category')
MigrationTable(db_src,db_dst,'res_partner_res_partner_category_rel')

# Groupes : correspondance par nom d'identifiant externe
# Les groupes des modules absents en v20 (hr, project, is_vllm2odoo) sont ignorés
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20 (3 et 4 au lieu de 4 et 5)
# => les identifiants externes base pointent sur les ids de la source et l'ancien default (id 3) perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)
#******************************************************************************


# ** res_company **************************************************************
# Champs simples (nom, e-mail, téléphone, APE...) ; devise retrouvée par son code (EUR)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Adresse de la société dans les en-têtes, slogan (texte en v16, traduisible en v20) et pied de page (déjà traduisible)
cr_src.execute("select id,company_details,report_header,report_footer from res_company")
for row in cr_src.fetchall():
    for champ in ('company_details','report_header'):
        if row[champ]:
            cr_dst.execute("update res_company set "+champ+"=jsonb_build_object('en_US',%s::text,'fr_FR',%s::text) where id=%s",[row[champ],row[champ],row['id']])
    if row['report_footer']:
        cr_dst.execute("update res_company set report_footer=%s where id=%s",[json.dumps(row['report_footer']),row['id']])
cnx_dst.commit()

# Compte bancaire de la société (IBAN de la facture) : res.bank supprimé en v20 => nom et BIC de la banque sur le compte
# clearing_label_id : nouvelle colonne obligatoire en v20 => libellé par défaut (base.clearing_label_all, aucun libellé pour la France)
# country_id : nouvelle colonne en v20 => pays du partenaire (même calcul qu'Odoo)
clearing_label_id = ExternalId2Id(cr_dst,'clearing_label_all',module='base',model='clearing.label')
MigrationTable(db_src,db_dst,'res_partner_bank',rename={
    'acc_number'          : 'account_number',
    'sanitized_acc_number': 'sanitized_account_number',
    'acc_holder_name'     : 'holder_name',
},default={'clearing_label_id': clearing_label_id})
cr_src.execute("select pb.id,b.name,b.bic from res_partner_bank pb join res_bank b on b.id=pb.bank_id")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner_bank set bank_name=%s,bank_bic=%s where id=%s",[row['name'],row['bic'],row['id']])
cr_dst.execute("update res_partner_bank b set country_id=p.country_id from res_partner p where p.id=b.partner_id and b.country_id is null")
cnx_dst.commit()
#******************************************************************************


# ** Tables de paramétrage is_* ***********************************************
# Colonnes identiques en v16 et en v20, pas de lien vers les tables standard (sauf create_uid / write_uid)
tables=[
    "is_bareme_valobat",        #   4 lignes
    "is_bois",                  #  23 lignes
    "is_calculateur_operation", #  15 lignes
    "is_qualite_bois",          # 404 lignes
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** Thème de l'entreprise (is_theme_entreprise) ******************************
# Couleurs choisies dans jurabotec20 le 10/10/2026 (pas de thème en v16)
SQL="""
    update res_company set is_theme_couleur='#007859', is_theme_eclaircissement=80;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************
