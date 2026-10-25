#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Fromtome : Odoo 14 (is_fromtome14) => Odoo 20 (is_fromtome20)
# Documentation : Documentation/migration-odoo/migration-is_fromtome14-vers-is_fromtome20.md (§ 6 et § 7)
# Première partie (étape 1 de la reprise) : contacts, comptes bancaires, utilisateurs, groupes, société, mise en page, thème
# A faire ensuite : tables de paramétrage is_*, unités, articles, stock, ventes, achats, comptabilité, chatter, pièces jointes
from migration_fonction import *
import atexit


#** Paramètres ****************************************************************
db_src = "fromtome14"
db_dst = "fromtome20"
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# fromtome20-vierge : base v20 avec is_fromtome20 installé, sans données (étape 14 de la reprise, à créer par Tony)
# db_vierge = db_dst+'-vierge'
# SQL='DROP DATABASE "'+db_dst+'";CREATE DATABASE "'+db_dst+'" WITH TEMPLATE "'+db_vierge+'"'
# cde="""echo '"""+SQL+"""' | psql postgres"""
# lines=os.popen(cde).readlines()
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)

# Heures de début et de fin, durée : affichées aussi en cas d'arrêt (sys.exit, erreur)
debut = datetime.now()
print("Début : %s"%debut.strftime('%d/%m/%Y %H:%M:%S'))
@atexit.register
def AfficherDuree():
    fin = datetime.now()
    print("Fin   : %s"%fin.strftime('%d/%m/%Y %H:%M:%S'))
    print("Durée : %s"%str(fin-debut).split('.')[0])


# ** Thème de l'entreprise (is_theme_entreprise) ******************************
# Pas de thème en v14 : rouge adouci du logo Fromtome (#C24762, même teinte moins saturée ; rouge du logo, #D91943,
# jugé trop agressif par Tony le 25/10/2026)
couleur_theme = '#C24762'
def ThemeEntreprise():
    if not couleur_theme:
        print("Thème de l'entreprise : couleur non choisie, non réglé")
        return
    cr_dst.execute("update res_company set is_theme_couleur=%s, is_theme_eclaircissement=80",[couleur_theme])
    cnx_dst.commit()
    print("Thème de l'entreprise : %s"%couleur_theme)
#******************************************************************************


# ** res_partner et res_users *************************************************
# Copiés avec les ids de la source (2 106 partenaires, 28 utilisateurs dans fromtome14)
# mobile et is_company (case « Société ») : recréés tels quels par is_fromtome20 => colonnes communes, copiées
# title (civilité, 204 partenaires) : supprimé d'Odoo en v20, non repris
# company_registry (9 partenaires), siren et nic : supprimés en v20 ; le SIRET est repris plus bas
# credit_limit : nombre en v14, jsonb (par société) en v20, toujours à 0 => non repris
# Nouvelles colonnes en v20 : valeurs par défaut d'Odoo (autopost_bills, group_rfq et group_on sont obligatoires)
# Liens vers des tables reprises ensuite (enseignes, tournées, entrepôts, frais de port...) : copiés avec les ids de la
# source, les tables liées sont reprises avec les mêmes ids
# Propriétés comptables (comptes, conditions de paiement, positions fiscales) : reprises avec la comptabilité
MigrationTable(db_src,db_dst,'res_partner',exclure=['credit_limit'],default={
    'autopost_bills': 'ask',
    'group_rfq'     : 'default',
    'group_on'      : 'default',
})
MigrationTable(db_src,db_dst,'res_users')
MigrationTable(db_src,db_dst,'res_company_users_rel')

# Dernière connexion de chaque utilisateur : sans elle, le statut des utilisateurs est « Invité » au lieu de « Confirmé »
MigrationTable(db_src,db_dst,'res_users_log')

# commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
cr_dst.execute("update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null")
cnx_dst.commit()

# complete_name n'existe pas en v14 => à calculer (même logique que _get_complete_name d'Odoo 20)
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

# SIRET : colonne siret en v14 (OCA l10n_fr_siret) => identifiant FR_SIRET de additional_identifiers en v20
# (568 partenaires, dont la société)
cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
cnx_dst.commit()

# Groupes : correspondance par nom d'identifiant externe (is_fromtome14.xxx => is_fromtome20.xxx, is_llm2odoo.xxx)
# Les groupes des modules absents en v20 (OCA...) sont ignorés
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20
# => les identifiants externes base pointent sur les ids de la source et l'ancien default perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)

# Utilisateur système __system__ : inactif, comme dans une base Odoo standard
cr_dst.execute("update res_users set active=false where id=1")
cnx_dst.commit()
#******************************************************************************


# ** res_company **************************************************************
# Champs simples (nom, e-mail, téléphone, champs is_* : coefficients et ports des prix, GLN, configuration IA...)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Vérification des TVA par VIES : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont un n° de TVA
# => à réactiver après la bascule si besoin (Paramètres / Comptabilité)
cr_dst.execute("update res_company set vat_check_vies=false")
cnx_dst.commit()

# Mise en page des documents : agencement « Boxed » en v14 (web.external_layout_boxed), supprimé en v20 => « Light »
# (web.external_layout_standard) en attendant la reprise des rapports du module (report/external_layout_boxed.xml) ;
# format A4 avec les marges de la v14 (haut 40, bas 32, gauche et droite 7, en-tête 35 mm). Format en noupdate :
# non écrasé par un -u base
cr_dst.execute("select res_id from ir_model_data where module='web' and name='external_layout_standard'")
layout_id = cr_dst.fetchone()['res_id']
cr_dst.execute("select res_id from ir_model_data where module='base' and name='paperformat_euro'")
paperformat_id = cr_dst.fetchone()['res_id']
cr_dst.execute("update res_company set external_report_layout_id=%s, paperformat_id=%s where id=1",[layout_id,paperformat_id])
cr_src.execute("""
    select p.margin_top,p.margin_bottom,p.margin_left,p.margin_right,p.header_spacing
    from res_company c join report_paperformat p on p.id=c.paperformat_id where c.id=1
""")
format_src = cr_src.fetchone()
cr_dst.execute("update report_paperformat set margin_top=%s, margin_bottom=%s, margin_left=%s, margin_right=%s, header_spacing=%s where id=%s",
    [format_src['margin_top'],format_src['margin_bottom'],format_src['margin_left'],format_src['margin_right'],format_src['header_spacing'],paperformat_id])
cnx_dst.commit()

# URL utilisée par wkhtmltopdf pour charger les CSS et images des rapports : web.base.url n'est pas joignable depuis
# le serveur => PDF sans mise en page ; non écrasée si déjà présente (port ou hébergement différent)
cr_dst.execute("insert into ir_config_parameter (key,value) values ('report.url','http://localhost:8069') on conflict (key) do nothing")
cnx_dst.commit()

# Digest périodique (mail récapitulatif d'Odoo, hebdomadaire par défaut en v20) : désactivé
cr_dst.execute("update digest_digest set state='deactivated'")
cnx_dst.commit()

# Inscription libre au portail (b2c en v14) fermée : sur invitation seulement (point 4 du § 5 de la doc)
InscriptionSurInvitation(db_dst)

# Couleur de l'entreprise (barre de menus, boutons, onglets)
ThemeEntreprise()

# Comptes bancaires (317 comptes, 96 banques) : res.bank supprimé en v20 => nom et BIC de la banque sur le compte
# clearing_label_id : nouvelle colonne obligatoire en v20 => libellé par défaut (base.clearing_label_all)
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
