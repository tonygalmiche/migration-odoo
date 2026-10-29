#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de DGET : Odoo 12 (is_dget) => Odoo 20 (is_dget20)
# Documentation : Documentation/migration-odoo/migration-is_dget12-vers-is_dget20.md
# Première partie : contacts, utilisateurs, société, unités, articles, conditions de paiement, tables du module qui ne
# dépendent pas de la comptabilité
# A faire ensuite : comptabilité (plan, taxes, positions fiscales, journaux), TVA DGET, contrats, lignes de contrats,
# heures, factures (account_invoice v12 => account_move), paiements, pièces jointes, chatter, filtres, contrôles
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit


#** Paramètres ****************************************************************
db_src = "dget12"
db_dst = "dget20"
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# dget20-vierge : base v20 avec is_dget20 installé, sans données (à créer par Tony)
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


# ** res_partner et res_users *************************************************
# Titres (res_partner_title, supprimé d'Odoo en v20) => is.titre du module, mêmes ids (90 titres, 1 030 contacts) ;
# nom et abréviation traduisibles (traduction de ir_translation)
MigrationTable(db_src,db_dst,'res_partner_title',table_dst='is_titre',text2jsonb=True)

# Contacts copiés avec les ids de la source (7 768, tous de type contact)
# Recréés dans le module (décisions de la doc) : customer => is_client (5 397), supplier => is_fournisseur (2 344),
# title => is_titre_id, mobile => is_mobile (1 921) ; is_company repris tel quel (case à cocher dans le module)
# barcode : texte en v12, jsonb (par société) en v20, jamais rempli => non repris ; credit_limit : toujours à 0
# autopost_bills : nouvelle colonne obligatoire en v20 (valeur par défaut d'Odoo)
# Propriétés comptables (comptes, conditions de paiement, positions fiscales) : reprises avec la comptabilité
MigrationTable(db_src,db_dst,'res_partner',
    rename={'customer':'is_client','supplier':'is_fournisseur','title':'is_titre_id','mobile':'is_mobile'},
    exclure=['credit_limit','barcode'],default={'autopost_bills':'ask'})
MigrationTable(db_src,db_dst,'res_users')
MigrationTable(db_src,db_dst,'res_company_users_rel')

# Dernière connexion de chaque utilisateur : sans elle, le statut des utilisateurs est « Invité » au lieu de « Confirmé »
MigrationTable(db_src,db_dst,'res_users_log')

# commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
cr_dst.execute("update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null")
cnx_dst.commit()

# complete_name n'existe pas en v12 => à calculer (même logique que _get_complete_name d'Odoo 20)
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

# SIRET : colonne siret en v12 => identifiant FR_SIRET de additional_identifiers en v20 (4 partenaires, dont la société :
# SIRET du pied de page des documents)
cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
cnx_dst.commit()

# Groupes : correspondance par nom d'identifiant externe (is_dget.is_gestionnaire_adjudicataire_group =>
# is_dget20.is_gestionnaire_adjudicataire_group) ; les groupes des modules absents en v20 sont ignorés
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20
# => les identifiants externes base pointent sur les ids de la source et l'ancien default perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)

# Utilisateur système __system__ : inactif, comme dans une base Odoo standard
cr_dst.execute("update res_users set active=false where id=1")
cnx_dst.commit()
#******************************************************************************


# ** res_company **************************************************************
# Champs simples (nom, e-mail, téléphone, APE...) ; company_registry (supprimé en v20) : texte écrit en dur dans le pied
# de page du module. Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents :
# non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Vérification des TVA par VIES : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont un n° de TVA
# => à réactiver après la bascule si besoin (Paramètres / Comptabilité)
cr_dst.execute("update res_company set vat_check_vies=false")
cnx_dst.commit()

# Mise en page des documents : web.external_layout_standard comme en v12 (bandeau DGET et pied de page du module) ;
# format A4 avec les marges de la v12 (haut 30, bas 25, gauche et droite 10, en-tête 25 mm). Format en noupdate : non
# écrasé par un -u base
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

# Inscription libre au portail fermée : sur invitation seulement
InscriptionSurInvitation(db_dst)

# Couleur de l'entreprise (is_theme_entreprise) : aucune en v12, à choisir avec Tony

# Comptes bancaires : IBAN écrit en dur sur la facture v12
#******************************************************************************


# ** Unités de mesure *********************************************************
# Copiées avec les ids de la v12 (19 unités) ; voir MigrationUnites
MigrationUnites(db_src,db_dst)
#******************************************************************************


# ** Articles *****************************************************************
# 3 articles, mêmes ids qu'en v12 : ils sont écrits en dur dans la génération des factures (1 « Service » : lignes du
# contrat, 2 « Facture » : factures précédentes) et « Révisions » est reconnu par son nom
# Catégories (3) : nom texte en v12, traduisible en v20
MigrationTableJsonb(db_src,db_dst,'product_category')
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

# Modèles d'articles : noms et descriptions traduisibles en v20 (traductions de ir_translation)
# expense_policy => reinvoice_policy ; nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count
MigrationTableJsonb(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},
    default={'service_tracking':'no','base_unit_count':0})
cnx_dst.commit()

# Variantes (une par modèle) ; prix de vente des variantes (lst_price) : calculé et stocké en v20 (prix du modèle)
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})
cr_dst.execute("update product_product p set lst_price=t.list_price from product_template t where t.id=p.product_tmpl_id")
cnx_dst.commit()

# Coût des variantes : propriété en v12, champ jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price')

# Identifiants externes : catégories renommées en v20 (product_category_all => product_category_goods...)
cr_src.execute("select name,res_id from ir_model_data where model='product.category'")
categories = {row['name']:row['res_id'] for row in cr_src.fetchall()}
MigrationIrModelData(db_src,db_dst,['product.category'],correspondances={
    'product.category': {
        'product_category_goods'   : categories.get('product_category_all'),
        'product_category_expenses': categories.get('cat_expense'),
        'product_category_services': categories.get('product_category_1'),
    },
})
# Taxes et comptes des articles : repris avec la comptabilité
#******************************************************************************


# ** Conditions de paiement ***************************************************
# 5 conditions copiées avec les ids de la v12 ; nom et note : texte en v12, traduisibles en v20
# Échéances v12 : toutes « solde » à N jours après la date de facture (day_after_invoice_date) => days_after, N jours,
# 100 % (value « balance » supprimé en v20)
MigrationTableJsonb(db_src,db_dst,'account_payment_term')
cr_src.execute("select * from account_payment_term_line order by payment_id, sequence, id")
lignes = cr_src.fetchall()
autres = [l for l in lignes if l['value']!='balance' or l['option']!='day_after_invoice_date']
if autres:
    print("Échéances non prévues par le script (à convertir) : %s"%[(l['payment_id'],l['value'],l['option']) for l in autres])
cr_dst.execute("alter table account_payment_term_line disable trigger all; delete from account_payment_term_line;")
for l in lignes:
    SQL="""
        insert into account_payment_term_line (id,payment_id,value,value_amount,delay_type,nb_days,days_next_month,create_uid,create_date,write_uid,write_date)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cr_dst.execute(SQL,[l['id'],l['payment_id'],'percent',100,'days_after',l['days'] or 0,'10',l['create_uid'],l['create_date'],l['write_uid'],l['write_date']])
cr_dst.execute("alter table account_payment_term_line enable trigger all")
cnx_dst.commit()
SetSequence(cr_dst,cnx_dst,'account_payment_term_line')
MigrationIrModelData(db_src,db_dst,['account.payment.term'])

# Conditions des clients (7 743 propriétés) : propriétés en v12, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_payment_term_id')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_supplier_payment_term_id')
#******************************************************************************


# ** Tables du module (sans lien avec la comptabilité) ************************
# Mêmes colonnes qu'en v12 (sauf is_dossier_contrat_detail.facture, calculé non stocké en v20), copiées avec leurs ids
# dans l'ordre des dépendances. TVA DGET (is_tva : taxe et compte), contrats, lignes de contrats et heures : après la
# comptabilité
for table in [
    'is_classement',                    # contacts
    'is_specialite',
    'is_classement_fournisseur',
    'res_partner_is_specialite_rel',
    'is_dossier_reference',             # tables des dossiers
    'is_dossier_contrat_traitance',
    'is_dossier_contrat_phase',
    'is_dossier_code_assurance',
    'is_dossier',                       # dossiers (2 427), références, notes, adjudicataires
    'is_dossier_is_reference_rel',
    'is_dossier_note',
    'is_dossier_adjudicataire',
    'is_concours',                      # concours (2 738)
    'is_concours_qui',
    'is_declaration_maf',               # déclarations MAF (7)
]:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** Contrôle (lecture seule) **************************************************
# Clés étrangères qui ne pointent sur rien (tables copiées sans contrôle des clés)
ControleOrphelins(db_dst)
#******************************************************************************
