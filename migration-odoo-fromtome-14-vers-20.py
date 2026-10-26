#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Fromtome : Odoo 14 (is_fromtome14) => Odoo 20 (is_fromtome20)
# Documentation : Documentation/migration-odoo/migration-is_fromtome14-vers-is_fromtome20.md (§ 6 et § 7)
# Première partie (étape 1 de la reprise) : contacts, comptes bancaires, utilisateurs, groupes, société, mise en page, thème
# A faire ensuite : tables de paramétrage is_*, unités, articles, stock, ventes, achats, comptabilité, chatter, pièces jointes
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit


#** Paramètres ****************************************************************
db_src = "fromtome14"
db_dst = "fromtome20"
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# fromtome20-vierge : base v20 avec is_fromtome20 installé, sans données (étape 14 de la reprise, créée par Tony)
# Ni fromtome20 ni fromtome20-vierge ne doivent être ouvertes (Odoo arrêté ou sur une autre base) : sinon DROP / CREATE
# refusés (« is being accessed by other users »)
db_vierge = db_dst+'-vierge'
SQL='DROP DATABASE "'+db_dst+'";CREATE DATABASE "'+db_dst+'" WITH TEMPLATE "'+db_vierge+'"'
cde="""echo '"""+SQL+"""' | psql postgres"""
lines=os.popen(cde).readlines()
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)

# Mise à jour d'une table copiée sans contrôle des clés étrangères (comme la copie) : un update revérifie toutes les
# clés de la ligne, dont celles vers des tables reprises plus loin (ex : sale_order_line.is_purchase_line_id)
def UpdateSansControle(table,SQL,params=None):
    cr_dst.execute("alter table "+table+" disable trigger all")
    try:
        cr_dst.execute(SQL,params)
    finally:
        cr_dst.execute("alter table "+table+" enable trigger all")
    cnx_dst.commit()

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


# ** Tables de paramétrage is_* (étape 2) *************************************
# Mêmes colonnes en v14 et en v20 : copiées avec les ids de la source
# Liens vers les partenaires (enseigne, transporteur) : repris ci-dessus ; entrepôt de l'enseigne : configuration du
# stock reprise avec les ids de la source (étape 5) ; modèles de commande de l'enseigne : pièces jointes reprises avec
# leurs ids (étape 11)
# Tables liées aux articles (lignes des modèles de commande, remises particulières, contrats date client) : reprises
# avec les articles (étape 3)
# is_modele_commande.enseigne_id : colonne restée d'une version antérieure (related non stocké en v14) => non reprise
tables = [
    'is_enseigne_commerciale',                     # 3 enseignes (liées aux partenaires : res_partner.is_enseigne_id)
    'is_enseigne_commerciale_modele_commande_rel', # Modèles de commande client des enseignes (pièces jointes)
    'is_modele_commande',                          # 238 modèles de commande (liés aux partenaires : res_partner.is_modele_commande_id)
    'is_modele_commande_modele_commande_rel',      # Modèles de commande client (pièces jointes) ; lignes : étape 3
    'is_transporteur',                             # 74 tournées transporteur
    'is_heure_maxi',                               # 16 jours / heures limites d'envoi des commandes fournisseur
    'is_motif_absence',                            # 5 motifs d'absence (suivi du temps)
    'is_motif_avoir',                              # 33 motifs d'avoir
    'is_imprimante_etiquette',                     # 3 imprimantes d'étiquettes
    'is_bio',                                      # Fiche article : 7 labels bio
    'is_famille_fromage',                          # 28 familles de fromage
    'is_rayon_magasin',                            # 2 rayons magasin
    'is_region_origine',                           # 98 régions d'origine
    'is_germe',                                    # 34 germes
    'is_ingredient',                               # 204 ingrédients
    'is_valeur_nutritionnelle',                    # 45 valeurs nutritionnelles
    'milk_type',                                   # 15 types de lait
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** Unités de mesure (étape 3) ***********************************************
# Copiées avec les ids de la v14 (23 unités) ; noms traduits par ir_translation ; voir MigrationUnites
MigrationUnites(db_src,db_dst)
#******************************************************************************


# ** Articles (étape 3) *******************************************************
# Catégories (23) : nom texte en v14, traduisible en v20 ; comptes des catégories : repris avec la comptabilité
MigrationTableJsonb(db_src,db_dst,'product_category')
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

# Modèles d'articles (6 264 : 6 223 stockables, 18 consommables, 23 services) ; pas d'attributs ni de variantes
# Noms et descriptions : texte en v14, traduisibles en v20 (traductions de ir_translation)
# expense_policy => reinvoice_policy ; sale_delay : toujours à 0 en v14, entier jsonb par société en v20 => vidé
# Nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count (valeurs par défaut d'Odoo)
MigrationTableJsonb(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},
    default={'service_tracking':'no','base_unit_count':0})
cr_dst.execute("update product_template set sale_delay=null")
# Type « Article stockable » (product) supprimé en v18 => consommable (consu) avec « Suivre l'inventaire » (is_storable)
cr_dst.execute("update product_template set is_storable=(type='product'), type=case when type='product' then 'consu' else type end")
# Suivi « none » supprimé en v20 (seulement lot et serial) => vide ; sinon « Wrong value for product.template.store_by: 'none' »
cr_dst.execute("update product_template set tracking=null where tracking='none'")
cnx_dst.commit()

# Variantes (6 264, une par modèle) ; prix de vente des variantes (lst_price) : calculé et stocké en v20 (sans
# attributs : prix du modèle)
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})
cr_dst.execute("update product_product p set lst_price=t.list_price from product_template t where t.id=p.product_tmpl_id")
cnx_dst.commit()

# Coût des variantes et responsable des articles : propriétés en v14, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price')
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','responsible_id')

# Fiche technique et classement des articles : mêmes colonnes en v14 et en v20
for table in [
    'product_milk_type_rel',          # Types de lait des articles (5 966)
    'product_is_fiche_technique_rel', # Fiches techniques (pièces jointes, reprises avec leurs ids à l'étape 11)
    'is_ingredient_line',             # Ingrédients des articles (2 056)
    'is_germe_line',                  # Germes (990)
    'is_valeur_nutritionnelle_line',  # Valeurs nutritionnelles (2 962)
    'contrat_date_client',            # Contrats date client (13)
    'is_remise_particuliere',         # Remises particulières des clients (71)
    'is_modele_commande_ligne',       # Lignes des modèles de commande (14 504)
]:
    MigrationTable(db_src,db_dst,table)

# Listes de prix (154, dont 62 archivées) : nom texte en v14, traduisible en v20 ; discount_policy supprimé en v20
# Liste de prix des clients : propriété en v14, champ jsonb par société en v20
MigrationTableJsonb(db_src,db_dst,'product_pricelist')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_product_pricelist','specific_property_product_pricelist')

# Règles de prix (106 557) : active supprimé en v20 (en v14, copie de celui de la liste de prix ; les règles des
# listes archivées restent masquées par le domaine de is_pricelist_item_ids, voir étape 7 du module)
# compute_price : « formula » (13 règles, remise de -8 % à +5 %) et « percentage » (1 règle, 37,619 %) supprimés en
# v20 => « discount » avec la même remise (price_discount ; pour percentage : percent_price)
MigrationTable(db_src,db_dst,'product_pricelist_item')
cr_dst.execute("update product_pricelist_item set compute_price='discount' where compute_price='formula'")
cr_src.execute("select id,percent_price from product_pricelist_item where compute_price='percentage'")
for row in cr_src.fetchall():
    cr_dst.execute("update product_pricelist_item set compute_price='discount', price_discount=%s where id=%s",[row['percent_price'],row['id']])
cnx_dst.commit()

# Prix fournisseurs (14 448) : name => partner_id ; unité d'achat de l'article (uom_po_id, supprimé en v20) => unité
# du prix fournisseur (obligatoire) ; remises fournisseurs par période (14 191) : mêmes colonnes
# 69 prix sans article (ni modèle ni variante) en v14 : article obligatoire en v20 => non repris
MigrationTable(db_src,db_dst,'product_supplierinfo',rename={'name':'partner_id'},default={'uom_id':1,'discount':0},
    where="product_tmpl_id is not null")
cr_src.execute("select s.id,t.uom_po_id from product_supplierinfo s join product_template t on t.id=s.product_tmpl_id")
execute_values(cr_dst,"update product_supplierinfo s set uom_id=v.uom_id from (values %s) as v(id,uom_id) where v.id=s.id",
    [(row['id'],row['uom_po_id']) for row in cr_src.fetchall()])
cnx_dst.commit()
# Remises des 69 prix sans article (80) : non reprises ; remises sans prix fournisseur (2 165, promos) : reprises
MigrationTable(db_src,db_dst,'product_supplierdiscount',
    where="t.supplier_info_id is null or t.supplier_info_id in (select id from product_supplierinfo where product_tmpl_id is not null)")

# Ids des devises : ids de la v14 (EUR = 1) => ids de la v20
MigrationDevisesParCode(db_src,db_dst,['product_template','product_pricelist','product_pricelist_item','product_supplierinfo'])

# Identifiants externes : catégories renommées en v20 (product_category_all => product_category_goods...)
cr_src.execute("select name,res_id from ir_model_data where model='product.category'")
categories = {row['name']:row['res_id'] for row in cr_src.fetchall()}
MigrationIrModelData(db_src,db_dst,['product.category','product.pricelist'],correspondances={
    'product.category': {
        'product_category_goods'   : categories.get('product_category_all'),
        'product_category_expenses': categories.get('cat_expense'),
        'product_category_services': categories.get('product_category_1'),
    },
})

# A reprendre avec la comptabilité : taxes des articles (product_taxes_rel, product_supplier_taxes_rel)
# A reprendre avec les pièces jointes : images des articles
#******************************************************************************


# ** Équipes commerciales (étape 4) *******************************************
# 4 équipes (Sales, et Website, Point of Sale, eBay archivées) : nom texte en v14, traduisible en v20
# Membres : sale_team_id de l'utilisateur en v14 (1 utilisateur) => crm_team_member en v20
MigrationTableJsonb(db_src,db_dst,'crm_team')
cr_dst.execute("delete from crm_team_member")
cr_src.execute("select id,sale_team_id from res_users where sale_team_id is not null")
for row in cr_src.fetchall():
    cr_dst.execute("insert into crm_team_member (crm_team_id,user_id,active,create_uid,create_date,write_uid,write_date) values (%s,%s,true,1,now(),1,now())",[row['sale_team_id'],row['id']])
cnx_dst.commit()
MigrationIrModelData(db_src,db_dst,['crm.team'])
#******************************************************************************


# ** Conditions de paiement (étape 4) *****************************************
# 14 conditions copiées avec les ids de la v14 ; nom et note : texte en v14, traduisibles en v20
# Échéances (format v14 : days + option) => delay_type et nb_days de la v20 :
# - day_after_invoice_date : N jours après la date de facture => days_after, N
# - after_invoice_month    : N jours après la fin du mois de la facture => days_after_end_of_month, N (non utilisé)
# - day_following_month    : le jour N du mois suivant => days_end_of_month_on_the, 0, N (« End of Following Month » :
#   N = 31 => fin du mois suivant, 4 partenaires)
# - fin_de_decade (option ajoutée par is_fromtome14, « 30 jours fin de décade », 41 clients, 810 factures) : delay_type
#   fin_de_decade ajouté par is_fromtome20 (étape 11 du module), même calcul : N jours puis fin de la décade
#   (le 10, le 20 ou la fin du mois)
# - value « balance » (solde) supprimé : pourcentage = 100 - les autres pourcentages de la condition
MigrationTableJsonb(db_src,db_dst,'account_payment_term')
cr_src.execute("select * from account_payment_term_line order by payment_id, sequence, id")
lignes = cr_src.fetchall()
pourcentages = {}
for l in lignes:
    if l['value']=='percent':
        pourcentages[l['payment_id']] = pourcentages.get(l['payment_id'],0) + float(l['value_amount'] or 0)
cr_dst.execute("alter table account_payment_term_line disable trigger all; delete from account_payment_term_line;")
for l in lignes:
    jours = l['days'] or 0
    if l['option']=='after_invoice_month':
        delay_type, nb_days, days_next_month = 'days_after_end_of_month', jours, '10'
    elif l['option']=='day_following_month' and jours>0:
        delay_type, nb_days, days_next_month = 'days_end_of_month_on_the', 0, str(jours)
    elif l['option']=='day_following_month':
        delay_type, nb_days, days_next_month = 'days_after', 30, '10'
    elif l['option']=='fin_de_decade':
        delay_type, nb_days, days_next_month = 'fin_de_decade', jours, '10'
    else:
        delay_type, nb_days, days_next_month = 'days_after', jours, '10'
    value, montant = l['value'], l['value_amount']
    if value=='balance':
        value, montant = 'percent', 100 - pourcentages.get(l['payment_id'],0)
    SQL="""
        insert into account_payment_term_line (id,payment_id,value,value_amount,delay_type,nb_days,days_next_month,create_uid,create_date,write_uid,write_date)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cr_dst.execute(SQL,[l['id'],l['payment_id'],value,montant,delay_type,nb_days,days_next_month,l['create_uid'],l['create_date'],l['write_uid'],l['write_date']])
cr_dst.execute("alter table account_payment_term_line enable trigger all")
cnx_dst.commit()
SetSequence(cr_dst,cnx_dst,'account_payment_term_line')
MigrationIrModelData(db_src,db_dst,['account.payment.term'])

# Conditions des clients (1 147) et des fournisseurs (409) : propriétés en v14, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_payment_term_id')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_supplier_payment_term_id')
#******************************************************************************


# ** Configuration du stock (étape 5) *****************************************
# Entrepôts FT (1) et LC (2), emplacements, types d'opérations, routes, règles : copiés avec les ids de la v14 ;
# correspondance par rôle avec ceux créés par la v20 (voir MigrationConfigurationStock)
MigrationConfigurationStock(db_src,db_dst)
# Routes des entrepôts (6) et des articles (6 262)
MigrationTable(db_src,db_dst,'stock_route_warehouse')
MigrationTable(db_src,db_dst,'stock_route_product')

# Entrepôts multiples : option automatique en v20 à la création d'un 2e entrepôt (stock_warehouse.py), non déclenchée
# par une copie en SQL => groupe impliqué par Utilisateur interne et donné à ses membres, comme le fait Odoo (_apply_group)
SQL="""
    insert into res_groups_implied_rel (gid,hid)
    select u.res_id, w.res_id from ir_model_data u, ir_model_data w
    where u.module='base' and u.name='group_user' and w.module='stock' and w.name='group_stock_multi_warehouses'
    on conflict do nothing;
    insert into res_groups_users_rel (gid,uid)
    select w.res_id, r.uid from ir_model_data w, ir_model_data u join res_groups_users_rel r on r.gid=u.res_id
    where u.module='base' and u.name='group_user' and w.module='stock' and w.name='group_stock_multi_warehouses'
    on conflict do nothing;
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Règles de réapprovisionnement (29) : qty_to_order => qty_to_order_manual ; nouvelles colonnes obligatoires en v20 :
# valeurs par défaut d'Odoo ; qty_multiple (0 ou 1 partout), group_id, bom_id, product_category_id supprimés
MigrationTable(db_src,db_dst,'stock_warehouse_orderpoint',rename={'qty_to_order':'qty_to_order_manual'},default={
    'min_max_based_on'       : 'one_month',
    'min_max_based_on_factor': 100,
    'daily_demand'           : 0,
})
#******************************************************************************


# ** Lots, colis et quants (étape 5) ******************************************
# Lots (88 806, tous avec DLC/DDM) : stock_production_lot => stock_lot ; product_uom_id supprimé en v20
MigrationTable(db_src,db_dst,'stock_production_lot','stock_lot')

# Colis (13) : stock_quant_package => stock_package ; packaging_id supprimé (conditionnements supprimés en v20)
# complete_name et parent_path (nouveaux, hiérarchie des colis) : colis sans parent => son nom et son id
MigrationTable(db_src,db_dst,'stock_quant_package','stock_package')
cr_dst.execute("update stock_package set complete_name=name, parent_path=id||'/'")
cnx_dst.commit()

# Quants (175 294 : 328 internes, 23 en transit, les autres sur les emplacements virtuels clients, fournisseurs et
# ajustement d'inventaire ; 61 avec une quantité réservée : à vérifier avec la reprise des mouvements)
MigrationTable(db_src,db_dst,'stock_quant')

# Emplacement du lot (nouveau en v20, stocké) : l'emplacement de ses quantités positives s'il n'y en a qu'un (calcul d'Odoo)
SQL="""
    update stock_lot l set location_id=q.location_id
    from (
        select lot_id, min(location_id) as location_id from stock_quant
        where quantity>0 and lot_id is not null group by lot_id having count(distinct location_id)=1
    ) q
    where q.lot_id=l.id
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Ventes (étape 6) *********************************************************
# Commandes (20 004 : 17 807 confirmées, 2 185 annulées, 12 devis ; aucune « done ») ; procurement_group_id =>
# références de stock (MigrationReferencesStock, plus bas) ; document_tax_mode : obligatoire en v20, réglage de la
# société (hors taxe) ; payment_mode_id (OCA) non repris au 1er temps
MigrationTable(db_src,db_dst,'sale_order',default={'document_tax_mode':'tax_excluded','locked':False})
# Lignes (395 751) : product_uom => product_uom_id ; customer_lead : décimal en v14, entier en v20 (toujours 0)
# Non repris (supprimés en v20) : price_reduce, product_packaging, qty_delivered_manual, route_id (vides)
MigrationTable(db_src,db_dst,'sale_order_line',rename={'product_uom':'product_uom_id'})
# Prix technique (nouveau, prix unitaire avant modification manuelle) et entrepôt de la ligne (stocké en v20)
UpdateSansControle('sale_order_line',"""
    update sale_order_line l set technical_price_unit=coalesce(l.technical_price_unit,l.price_unit), warehouse_id=o.warehouse_id
    from sale_order o where o.id=l.order_id
""")
# Taxes des lignes (ids des taxes de la v14, reprises avec la comptabilité) ; fichiers Excel importés des commandes
# (pièces jointes reprises avec leurs ids)
MigrationTable(db_src,db_dst,'account_tax_sale_order_line_rel')
MigrationTable(db_src,db_dst,'sale_order_is_import_excel_ids_rel')
MigrationDevisesParCode(db_src,db_dst,['sale_order','sale_order_line'])
# Lien entre les lignes de commande et les lignes de factures (sale_order_line_invoice_rel) : avec les factures
#******************************************************************************


# ** Achats (étape 6) *********************************************************
# Commandes (22 092 : 13 551 confirmées, 8 530 annulées, 9 terminées, 2 brouillons) : notes => note ;
# document_tax_mode obligatoire en v20 (hors taxe) ; état « done » supprimé en v20 => « purchase » verrouillée
# group_id => références de stock ; payment_mode_id, supplier_partner_bank_id (OCA) non repris au 1er temps
MigrationTable(db_src,db_dst,'purchase_order',rename={'notes':'note'},default={'document_tax_mode':'tax_excluded','locked':False})
UpdateSansControle('purchase_order',"update purchase_order set state='purchase', locked=true where state='done'")
# Lignes (297 927) : product_uom => uom_id ; state, currency_id (calculés), sale_order_id, account_analytic_id (vides)
# non repris
MigrationTable(db_src,db_dst,'purchase_order_line',rename={'product_uom':'uom_id'})
# Prix technique et prix dans l'unité de l'article (nouveaux, stockés en v20 : même calcul qu'Odoo, _compute_price)
UpdateSansControle('purchase_order_line',"""
    update purchase_order_line l set
        technical_price_unit = l.price_unit,
        price_unit_product_uom = case when l.display_type is null then l.price_unit * pu.factor / lu.factor else 0 end
    from uom_uom lu, product_product p, product_template t, uom_uom pu
    where lu.id=l.uom_id and p.id=l.product_id and t.id=p.product_tmpl_id and pu.id=t.uom_id
""")
# Taxes des lignes (ids des taxes de la v14, reprises avec la comptabilité) ; transferts liés aux commandes (module)
MigrationTable(db_src,db_dst,'account_tax_purchase_order_line_rel')
MigrationTable(db_src,db_dst,'purchase_order_stock_picking_rel')
MigrationDevisesParCode(db_src,db_dst,['purchase_order','purchase_order_line'])
# Lien entre les commandes et les factures (account_move_purchase_order_rel) : avec les factures
#******************************************************************************


# ** Transferts, mouvements et rebuts (étape 6) *******************************
# Transferts (41 612), mouvements (415 161) et lignes (819 591) ; rebuts : scrapped => is_scrap (666 rebuts,
# stock.scrap supprimé en v20) ; description_picking => description_picking_manual ; voir MigrationTransfertsStock
# Inventaires (31, stock.inventory supprimé depuis la v15) : en-têtes et lignes non repris (décision du 25/10/2026),
# leurs mouvements sont repris
MigrationTransfertsStock(db_src,db_dst)

# Valorisation : stock_valuation_layer (313 092 couches) non reprise, valorisation manuelle (§ 6 de la doc)

# Groupes d'approvisionnement (43 864, supprimés en v20) => références de stock, liens avec les mouvements et les
# commandes de vente et d'achat
MigrationReferencesStock(db_src,db_dst)
#******************************************************************************


# ** Séquences (étape 6) ******************************************************
# Commandes de vente (CC) et d'achat (CF) ; les transferts ont la séquence de leur type d'opération, recalée par
# MigrationConfigurationStock
for code in ['sale.order','purchase.order']:
    cr_src.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
    seq_src = cr_src.fetchone()
    cr_dst.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
    seq_dst = cr_dst.fetchone()
    MigrationIrSequence(db_src,db_dst,id_src=seq_src['id'],id_dst=seq_dst['id'])
#******************************************************************************
