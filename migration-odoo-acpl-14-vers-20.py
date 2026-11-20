#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données d'ACPL : Odoo 14 (is_acpl14) => Odoo 20 (is_acpl20)
# Documentation : Documentation/migration-odoo/migration-is_acpl14-vers-is_acpl20.md
# Reprise 1 : contacts, utilisateurs, société, unités, articles, conditions de paiement, paramètres comptables
# Reprise 2 : ventes, stock, séquences ; reprise 3 : pièces comptables, lettrages, paiements ; reprise 4 : pièces
# jointes, filtres favoris, chatter, activités
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit
import hashlib
import subprocess


#** Paramètres ****************************************************************
db_src = "acpl14"
db_dst = "acpl20"
filestore = "/media/sf_dev_odoo/home/odoo/filestore"   # filestore d'Odoo sur ubuntu2604 (data_dir de acpl20.conf)
#******************************************************************************


# ** Repartir de la base vierge à chaque lancement ****************************
# acpl20-vierge : base v20 avec is_acpl20 installé (18/10/2026, mis à jour le 20/11/2026), sans données ; aucune option
# des Paramètres à cocher (§ 3 de la doc)
# Ni acpl20 ni acpl20-vierge ne doivent être ouvertes (Odoo arrêté) : sinon DROP / CREATE refusés
# Filestore : DROP DATABASE n'y touche pas => fichiers de la production copiés gardés ; fichiers de la base vierge
# ajoutés (cp --update=none : seuls les fichiers absents sont copiés, rien n'est écrasé ni supprimé)
db_vierge = db_dst+'-vierge'
for SQL in ['DROP DATABASE IF EXISTS "%s"'%db_dst, 'CREATE DATABASE "%s" WITH TEMPLATE "%s"'%(db_dst,db_vierge)]:
    if subprocess.run(['psql','-d','postgres','-c',SQL]).returncode:
        sys.exit("Arrêt : %s refusé (Odoo arrêté ?)"%SQL)
if subprocess.run(['cp','-r','--update=none','%s/%s/.'%(filestore,db_vierge),'%s/%s/'%(filestore,db_dst)]).returncode:
    sys.exit("Arrêt : copie du filestore de %s refusée"%db_vierge)
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

# Contrôle des clés étrangères désactivé sur une table le temps de la recaler, réactivé même en cas d'erreur
sans_controle = set()
def ControleCles(tables,actif):
    for table in tables:
        cr_dst.execute("alter table "+table+(" enable" if actif else " disable")+" trigger all")
        (sans_controle.discard if actif else sans_controle.add)(table)
    cnx_dst.commit()
@atexit.register
def RetablirControleCles():
    # Le script s'est arrêté (erreur) avant de réactiver les contrôles : réactivés avec une nouvelle connexion
    if sans_controle:
        cnx,cr = GetCR(db_dst)
        for table in sans_controle:
            cr.execute("alter table "+table+" enable trigger all")
        cnx.commit()
        print("Contrôles des clés étrangères réactivés : %s"%sorted(sans_controle))

# Mise à jour d'une table sans contrôle des clés étrangères (tables copiées par MigrationTable, contrôlées à la fin par
# ControleOrphelins)
def UpdateSansControle(table,SQL,params=None):
    ControleCles([table],False)
    cr_dst.execute(SQL,params)
    cnx_dst.commit()
    ControleCles([table],True)


# ** Thème de l'entreprise (is_theme_entreprise) ******************************
# Pas de thème en v14 : rouge adouci du logo ACPL (#D9534F ; rouge du logo, #EC0C04, jugé trop agressif par Tony le 18/10/2026)
def ThemeEntreprise():
    cr_dst.execute("update res_company set is_theme_couleur='#D9534F', is_theme_eclaircissement=80")
    cnx_dst.commit()
    print("Thème de l'entreprise : #D9534F")
#******************************************************************************


# ** res_partner et res_users *************************************************
# Copiés avec les ids de la source (486 partenaires, 7 utilisateurs dont 2 actifs dans acpl14)
# title (civilité, 3 partenaires) : supprimé d'Odoo en v20, non repris ; mobile : voir plus bas
# credit_limit : nombre en v14, jsonb (par société) en v20, toujours à 0 => non repris
# autopost_bills : nouvelle colonne obligatoire en v20 (valeur par défaut d'Odoo)
# Propriétés comptables (comptes, conditions de paiement, positions fiscales) : reprises avec la comptabilité
MigrationTable(db_src,db_dst,'res_partner',exclure=['credit_limit'],default={'autopost_bills':'ask'})
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

# Mobile : supprimé d'Odoo en v20 => dans le téléphone quand celui-ci est vide (6 partenaires sur 12 ; question 2 de
# la doc, accord de Tony)
cr_src.execute("select id,mobile from res_partner where coalesce(mobile,'')<>'' and coalesce(phone,'')=''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set phone=%s where id=%s",[row['mobile'],row['id']])
cnx_dst.commit()

# SIRET : colonne siret en v14 => identifiant FR_SIRET de additional_identifiers en v20 (15 partenaires, dont la société)
cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
cnx_dst.commit()

# Groupes : correspondance par nom d'identifiant externe (is_acpl14.xxx => is_acpl20.xxx, aucun groupe maison en v14)
# Les groupes des modules absents en v20 (purchase...) sont ignorés
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20
# => les identifiants externes base pointent sur les ids de la source et l'ancien default perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)

# Création des articles : en v14, droit des administrateurs Ventes, Stock, Comptabilité... ; en v20, seulement le
# nouveau groupe « Produits : Créer » => donné aux utilisateurs qui avaient ce droit en v14
MigrationCreationArticles(db_src,db_dst)

# Utilisateur système __system__ : inactif, comme dans une base Odoo standard
cr_dst.execute("update res_users set active=false where id=1")
cnx_dst.commit()
#******************************************************************************


# ** res_company **************************************************************
# Champs simples (nom, e-mail, téléphone, APE, registre du commerce...)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Vérification des TVA par VIES : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont un n° de TVA
# => à réactiver après la bascule si besoin (Paramètres / Comptabilité)
cr_dst.execute("update res_company set vat_check_vies=false")
cnx_dst.commit()

# Mise en page des documents : agencement « Light » (web.external_layout_standard, celui de la v14 : aucun agencement
# choisi, Odoo prend alors le standard), sur lequel s'applique l'en-tête ACPL du module ; format A4 avec les marges de
# la v14 (haut 27, bas 23, gauche et droite 7, en-tête 22 mm ; 52 / 32 / 0 / 0 / 52 en v20). Format en noupdate :
# non écrasé par un -u base
# Marges CSS (css_margins, nouveau en v20, coché sur l'A4) désactivées : elles ajoutent 11 mm au-dessus de l'en-tête et à
# gauche et à droite du corps, en plus des marges de la v14 => en-tête sur le texte des pages suivantes, texte plus
# étroit et conditions générales sur 2 pages (une seule en v14)
cr_dst.execute("select res_id from ir_model_data where module='web' and name='external_layout_standard'")
layout_id = cr_dst.fetchone()['res_id']
cr_dst.execute("select res_id from ir_model_data where module='base' and name='paperformat_euro'")
paperformat_id = cr_dst.fetchone()['res_id']
# Tableaux « Gras » (report_tables_id bold, nouveau en v20 ; « Clair » par défaut, sans bordure entre les lignes) : un
# trait entre chaque ligne comme en v14 (choix de Tony du 20/11/2026)
cr_dst.execute("update res_company set external_report_layout_id=%s, paperformat_id=%s, report_tables_id='bold' where id=1",[layout_id,paperformat_id])
cr_src.execute("""
    select p.margin_top,p.margin_bottom,p.margin_left,p.margin_right,p.header_spacing
    from res_company c join report_paperformat p on p.id=c.paperformat_id where c.id=1
""")
format_src = cr_src.fetchone()
cr_dst.execute("update report_paperformat set margin_top=%s, margin_bottom=%s, margin_left=%s, margin_right=%s, header_spacing=%s, css_margins=false where id=%s",
    [format_src['margin_top'],format_src['margin_bottom'],format_src['margin_left'],format_src['margin_right'],format_src['header_spacing'],paperformat_id])
cnx_dst.commit()

# URL utilisée par wkhtmltopdf pour charger les CSS et images des rapports : web.base.url n'est pas joignable depuis
# le serveur => PDF sans mise en page ; non écrasée si déjà présente (port ou hébergement différent)
cr_dst.execute("insert into ir_config_parameter (key,value) values ('report.url','http://localhost:8069') on conflict (key) do nothing")
cnx_dst.commit()

# Digest périodique (mail récapitulatif d'Odoo, hebdomadaire par défaut en v20) : désactivé
cr_dst.execute("update digest_digest set state='deactivated'")
cnx_dst.commit()

# Couleur de l'entreprise (barre de menus, boutons, onglets)
ThemeEntreprise()

# Inscription libre au portail (b2c en v14) fermée : sur invitation seulement (question 4 de la doc, accord de Tony)
SQL="""
    insert into ir_config_parameter (key,value) values ('auth_signup.invitation_scope','b2b')
    on conflict (key) do update set value='b2b'
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Paiement en ligne des factures : coché par défaut en v20 => décoché si aucun moyen de paiement n'était activé en v14
MigrationPaiementEnLigne(db_src,db_dst)
# En v14, seul « Virement bancaire » était activé (réglage par défaut d'Odoo 14), d'où True ci-dessus ; aucun moyen de
# paiement en v20 => décoché (décision de Tony du 20/11/2026)
cr_dst.execute("update ir_config_parameter set value='False' where key='account_payment.enable_portal_payment'")
cnx_dst.commit()

# Comptes bancaires : aucun dans la source (IBAN écrit en dur sur la facture)
#******************************************************************************


# ** Précisions décimales *****************************************************
# Précisions de la v14 (2 par défaut en v20) ; avant les calculs qui lisent la précision « Product Unit »
# (quantités des mouvements de stock)
MigrationPrecisionsDecimales(db_src,db_dst)
#******************************************************************************


# ** Unités de mesure *********************************************************
# Copiées avec les ids de la v14 (22 unités, une seule utilisée par les articles : Units) ; noms traduits par
# ir_translation ; voir MigrationUnites
MigrationUnites(db_src,db_dst)
#******************************************************************************


# ** Équipes commerciales *****************************************************
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


# ** Articles *****************************************************************
# Catégories (3) : nom texte en v14, traduisible en v20 ; comptes des catégories : repris avec la comptabilité
MigrationTableJsonb(db_src,db_dst,'product_category')
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

# Modèles d'articles (3 865 : 3 253 consommables, 607 stockables, 5 services) ; pas d'attributs ni de variantes
# Noms et descriptions : texte en v14, traduisibles en v20 (traductions de ir_translation)
# expense_policy => reinvoice_policy ; sale_delay : toujours à 0 en v14, entier jsonb par société en v20 => vidé
# (MigrationTableJsonb le copierait comme un texte traduisible)
# Nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count (valeurs par défaut d'Odoo)
MigrationTableJsonb(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},
    default={'service_tracking':'no','base_unit_count':0})
cr_dst.execute("update product_template set sale_delay=null")
# Type « Article stockable » (product, 607 articles) supprimé en v18 => consommable (consu) avec « Suivre l'inventaire » (is_storable)
cr_dst.execute("update product_template set is_storable=(type='product'), type=case when type='product' then 'consu' else type end")
# Suivi « none » supprimé en v20 (seulement lot et serial) => vide ; sinon « Wrong value for product.template.store_by: 'none' »
cr_dst.execute("update product_template set tracking=null where tracking='none'")
cnx_dst.commit()

# Variantes (3 865, une par modèle) ; prix de vente des variantes (lst_price) : calculé et stocké en v20 (sans
# attributs : prix du modèle)
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})
cr_dst.execute("update product_product p set lst_price=t.list_price from product_template t where t.id=p.product_tmpl_id")
cnx_dst.commit()

# Coût des variantes (1 787 valeurs) et responsable des articles (3 865) : propriétés en v14, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price')
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','responsible_id')

# Liste de prix (1, « Public Pricelist », sans règles) : nom texte en v14, traduisible en v20
# Liste de prix des clients (35 partenaires, toutes sur cette liste) : propriété en v14, champ jsonb par société en v20
MigrationTableJsonb(db_src,db_dst,'product_pricelist')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_product_pricelist','specific_property_product_pricelist')
# Fonctionnalité « Listes de prix » désactivée en v14 (product.group_product_pricelist non impliqué) : la v20 avertit à
# l'ouverture des Paramètres (« Vous êtes sur le point de désactiver la fonctionnalité liste de prix… ») et archive les
# listes actives à l'enregistrement => archivée ici, comme le ferait Odoo (sans règle : prix inchangés ; commandes et
# clients la gardent) ; fonctionnalité laissée désactivée comme en v14 (décision de Tony du 20/11/2026)
cr_dst.execute("update product_pricelist set active=false")
cnx_dst.commit()

# Prix fournisseurs (607, un seul fournisseur) : name => partner_id ; unité d'achat de l'article (uom_po_id, supprimé
# en v20) => unité du prix fournisseur (obligatoire)
MigrationTable(db_src,db_dst,'product_supplierinfo',rename={'name':'partner_id'},default={'uom_id':1,'discount':0})
cr_src.execute("select s.id,t.uom_po_id from product_supplierinfo s join product_template t on t.id=s.product_tmpl_id")
execute_values(cr_dst,"update product_supplierinfo s set uom_id=v.uom_id from (values %s) as v(id,uom_id) where v.id=s.id",
    [(row['id'],row['uom_po_id']) for row in cr_src.fetchall()])
cnx_dst.commit()

# Ids des devises : ids de la v14 (EUR = 1) => ids de la v20 (EUR = 126)
MigrationDevisesParCode(db_src,db_dst,['product_template','product_pricelist','product_supplierinfo'])

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

# A reprendre avec les pièces jointes : images des articles
#******************************************************************************


# ** Conditions de paiement ***************************************************
# 10 conditions copiées avec les ids de la v14 ; nom et note : texte en v14, traduisibles en v20
# Échéances (format v14 : days + option) => delay_type et nb_days de la v20 :
# - day_after_invoice_date : N jours après la date de facture => days_after, N
# - after_invoice_month    : N jours après la fin du mois de la facture => days_after_end_of_month, N
# - day_following_month    : le jour N du mois suivant => days_end_of_month_on_the, 0, N (même calcul en v20 : jour N
#   du mois suivant, ramené au dernier jour du mois ; « End of Following Month » : N = 31 => fin du mois suivant)
#   N = 0 : la v14 donne le même jour du mois suivant (« 30 jours nets », 1 811 factures : 15/10 => 15/11), sans
#   équivalent en v20 => 30 jours (question 3 de la doc, accord de Tony)
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

# Conditions des clients (168) et des fournisseurs (6) : propriétés en v14, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_payment_term_id')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_supplier_payment_term_id')
#******************************************************************************


# ** Paramètres comptables ****************************************************
# Plan comptable (1 175 comptes, dont un compte client 411xxx par client : code client des factures et du module),
# groupes de taxes (12), taxes (55), positions fiscales (4) et journaux (7) de la v14 copiés avec leurs ids à la place
# de ceux créés par l10n_fr_account en v20 (ids différents) ; colonnes ajoutées par la v20 reprises de
# l'enregistrement v20 équivalent (même identifiant externe) ; références de la v20 recalées
# Voir Documentation/migration-odoo/migration-vers-odoo20.md § 3.7 et § 5.4

# Lignes v20 et correspondance par identifiant externe, avant la copie
# Taxes TTC de la v14 (18, jamais utilisées), supprimées de l10n_fr_account : codes Factur-X de la taxe HT correspondante
avant, corr = {}, {}
for table,suffixes in [('account_account',[]),('account_tax_group',[]),('account_tax',['_TTC','_ttc']),('account_fiscal_position',[])]:
    avant[table], corr[table] = LireAvantCopie(db_src,db_dst,table,suffixes)
# Taxes de vente utilisées sans identifiant de même nom en v20 : en v20, les taxes à 0 % sont séparées en biens et
# services (codes Factur-X différents) => taxes « biens » (lignes de fournitures, livraisons) ; « 20% Prestations »,
# créée à la main en v14 (3 977 factures) => taxe à 20 % de la v20. Sans cette correspondance, ces taxes n'ont pas de
# catégorie de TVA Factur-X (ubl_cii_tax_category_code)
taxes_renommees = {
    '1_tva_0'        : '1_tva_sale_good_0',         # TVA 0% autres opérations non imposables (vente) => E, VATEX-EU-F
    '1_tva_export_0' : '1_tva_sale_good_export_0',  # TVA 0% export (vente) => G, VATEX-EU-G
    '1_tva_intra_0'  : '1_tva_sale_good_intra_0',   # TVA 0% livraisons intracommunautaires (vente) => K, VATEX-EU-IC
    'account_tax_41' : '1_tva_normale',             # 20% Prestations => S
}
cr_src.execute("select name,res_id from ir_model_data where model='account.tax' and name = any(%s)",[list(taxes_renommees)])
taxes_src = {row['name']:row['res_id'] for row in cr_src.fetchall()}
cr_dst.execute("select name,res_id from ir_model_data where model='account.tax' and name = any(%s)",[list(taxes_renommees.values())])
taxes_dst = {row['name']:row['res_id'] for row in cr_dst.fetchall()}
for nom_src,nom_dst in taxes_renommees.items():
    if nom_src in taxes_src and nom_dst in taxes_dst:
        corr['account_tax'][taxes_src[nom_src]] = taxes_dst[nom_dst]
    else:
        print("Taxe %s => %s : identifiant absent (base acpl20 pas vierge ?)"%(nom_src,nom_dst))
avant['account_journal'], _ = LireAvantCopie(db_src,db_dst,'account_journal')
# Journaux : pas d'identifiant externe en v14 => correspondance par code (FAC, OD, EXCH, CABA, BNK1, STJ), sinon par type
# s'il n'y en a qu'un (achats : FACTU en v14, FACTURE en v20)
cr_src.execute("select id,code,type from account_journal")
journaux_src = cr_src.fetchall()
corr['account_journal'] = {}
for j20 in avant['account_journal'].values():
    j14 = [j for j in journaux_src if j['code']==j20['code']] or [j for j in journaux_src if j['type']==j20['type']]
    if len(j14)==1 and j14[0]['id'] not in corr['account_journal']:
        corr['account_journal'][j14[0]['id']] = j20['id']
print("Journaux (id v14 : id v20) : %s"%corr['account_journal'])
inverse = {t:{id20:id_src for id_src,id20 in sorted(c.items(),reverse=True)} for t,c in corr.items()} # id v20 => id v14

# Tables de la v20 liées aux anciens comptes et taxes, sans équivalent repris
for table in [
    'account_tax_filiation_rel',                # taxes groupées (aucune en v14)
    'account_fiscal_position_account',          # correspondances de comptes (aucune en v14)
    'account_fiscal_position_account_tax_rel',  # recréées plus bas à partir de la v14
    'account_tax_alternatives',                 # recréées plus bas à partir de la v14
    'account_reconcile_model_line',             # modèles de rapprochement : ceux de la v14 (2) n'existent plus en v20
    'account_reconcile_model',
]:
    cr_dst.execute("delete from "+table)
cnx_dst.commit()

# Comptes : nom traduisible, code => code_store (par société), deprecated => active, société => account_account_res_company_rel
# Type : user_type_id (account.account.type, supprimé en v16) => account_type, d'après l'identifiant externe du type
# group_id, root_id, internal_type, is_off_balance : supprimés en v20 (groupes de comptes supprimés)
MigrationTableJsonb(db_src,db_dst,'account_account',default={'account_type':'income'})
# Colonnes ajoutées par la v20 (description, comptes de stock...) d'abord : code_store, active et account_type sont posés juste après
CompleterColonnesV20(db_src,db_dst,'account_account',avant['account_account'],corr['account_account'],inverse)
types_comptes = {
    'data_account_type_receivable'             : 'asset_receivable',
    'data_account_type_payable'                : 'liability_payable',
    'data_account_type_liquidity'              : 'asset_cash',
    'data_account_type_credit_card'            : 'liability_credit_card',
    'data_account_type_current_assets'         : 'asset_current',
    'data_account_type_non_current_assets'     : 'asset_non_current',
    'data_account_type_prepayments'            : 'asset_prepayments',
    'data_account_type_fixed_assets'           : 'asset_fixed',
    'data_account_type_current_liabilities'    : 'liability_current',
    'data_account_type_non_current_liabilities': 'liability_non_current',
    'data_account_type_equity'                 : 'equity',
    'data_unaffected_earnings'                 : 'equity_unaffected',
    'data_account_type_revenue'                : 'income',
    'data_account_type_other_income'           : 'income_other',
    'data_account_type_expenses'               : 'expense',
    'data_account_type_depreciation'           : 'expense_depreciation',
    'data_account_type_direct_costs'           : 'expense_direct_cost',
    'data_account_off_sheet'                   : 'off_balance',
}
cr_src.execute("""
    select a.id,a.code,a.deprecated,a.company_id,d.name as type
    from account_account a left join ir_model_data d on d.model='account.account.type' and d.res_id=a.user_type_id
""")
comptes = cr_src.fetchall()
sans_type = [row['code'] for row in comptes if row['type'] not in types_comptes]
if sans_type:
    print("Comptes sans type connu (laissés en produit) : %s"%sans_type)
cr_dst.execute("delete from account_account_res_company_rel")
execute_values(cr_dst,"""
    update account_account a set code_store=jsonb_build_object('1',s.code), active=not s.deprecated, account_type=s.account_type
    from (values %s) as s(id,code,deprecated,account_type) where s.id=a.id
""",[(row['id'],row['code'],bool(row['deprecated']),types_comptes.get(row['type'],'income')) for row in comptes],page_size=5000)
execute_values(cr_dst,"insert into account_account_res_company_rel (account_account_id,res_company_id) values %s",
    [(row['id'],row['company_id'] or 1) for row in comptes])
cnx_dst.commit()
parent_store_compute(cr_dst,cnx_dst,'account_account','parent_id') # hiérarchie des comptes (aucun parent : parent_path = id/)
# Taxes par défaut des comptes (268) : copiées après les taxes (ci-dessous)

# Groupes de taxes (société obligatoire en v20) et taxes : price_include => price_include_override (vide = réglage de la société)
# country_id : nouvelle colonne obligatoire en v20 => France (pays de la société)
cr_dst.execute("select id from res_country where code='FR'")
pays_fr = cr_dst.fetchone()['id']
MigrationTableJsonb(db_src,db_dst,'account_tax_group',default={'company_id':1})
CompleterColonnesV20(db_src,db_dst,'account_tax_group',avant['account_tax_group'],corr['account_tax_group'],inverse)
MigrationTableJsonb(db_src,db_dst,'account_tax',default={'country_id':pays_fr})
# Colonnes ajoutées par la v20 (codes Factur-X, mentions) d'abord : price_include_override posé juste après,
# is_domestic recalculé avec les positions fiscales
CompleterColonnesV20(db_src,db_dst,'account_tax',avant['account_tax'],corr['account_tax'],inverse)
cr_src.execute("select id from account_tax where price_include")
cr_dst.execute("update account_tax set price_include_override=case when id = any(%s) then 'tax_included' end",[[row['id'] for row in cr_src.fetchall()]])
cnx_dst.commit()
# Lignes de répartition : invoice_tax_id / refund_tax_id => tax_id + document_type
MigrationTable(db_src,db_dst,'account_tax_repartition_line',default={'document_type':'invoice'})
cr_src.execute("select id,invoice_tax_id,refund_tax_id from account_tax_repartition_line")
execute_values(cr_dst,"""
    update account_tax_repartition_line r set tax_id=s.tax_id, document_type=s.document_type
    from (values %s) as s(id,tax_id,document_type) where s.id=r.id
""",[(row['id'],row['invoice_tax_id'] or row['refund_tax_id'],'invoice' if row['invoice_tax_id'] else 'refund') for row in cr_src.fetchall()])
cnx_dst.commit()
MigrationTable(db_src,db_dst,'account_account_tax_default_rel')

# Positions fiscales (4) ; correspondances de taxes (50) : en v20, portées par la taxe de remplacement
MigrationTableJsonb(db_src,db_dst,'account_fiscal_position')
CompleterColonnesV20(db_src,db_dst,'account_fiscal_position',avant['account_fiscal_position'],corr['account_fiscal_position'],inverse)
cr_src.execute("select position_id,tax_src_id,tax_dest_id from account_fiscal_position_tax where tax_dest_id is not null")
for row in cr_src.fetchall():
    cr_dst.execute("insert into account_fiscal_position_account_tax_rel (account_tax_id,account_fiscal_position_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['position_id']])
    cr_dst.execute("insert into account_tax_alternatives (dest_tax_id,src_tax_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['tax_src_id']])
cr_dst.execute("update account_tax t set is_domestic = not exists (select 1 from account_fiscal_position_account_tax_rel r where r.account_tax_id=t.id)")
cr_dst.execute("update account_fiscal_position set is_domestic=false")
cnx_dst.commit()

# Journaux (7) : alias de messagerie non repris
MigrationTableJsonb(db_src,db_dst,'account_journal',default={'invoice_reference_type':'invoice','invoice_reference_model':'odoo'})
cr_dst.execute("update account_journal set alias_id=null")
cnx_dst.commit()
CompleterColonnesV20(db_src,db_dst,'account_journal',avant['account_journal'],corr['account_journal'],inverse)
# Modes de paiement des journaux : table account_payment_method_line créée en v15 (en v14 : modes manuels du journal de
# banque, comme en v20) => lignes créées par la v20 gardées, journal recalé sur l'id v14 ; lignes d'un journal sans
# équivalent supprimées
cr_dst.execute("select id,journal_id from account_payment_method_line")
for row in cr_dst.fetchall():
    id14 = inverse['account_journal'].get(row['journal_id'])
    if id14:
        cr_dst.execute("update account_payment_method_line set journal_id=%s where id=%s",[id14,row['id']])
    else:
        cr_dst.execute("delete from account_payment_method_line where id=%s",[row['id']])
# Compte d'attente de chaque mode : comptes des encaissements et des décaissements du journal v14 (payment_debit_account_id
# 512003, payment_credit_account_id 512004, supprimés en v20), utilisés par les 253 paiements
cr_src.execute("select id,payment_debit_account_id,payment_credit_account_id from account_journal where type in ('bank','cash')")
for row in cr_src.fetchall():
    cr_dst.execute("""
        update account_payment_method_line l
        set payment_account_id = case when m.payment_type='inbound' then %s else %s end
        from account_payment_method m
        where m.id=l.payment_method_id and l.journal_id=%s
    """,[row['payment_debit_account_id'],row['payment_credit_account_id'],row['id']])
cnx_dst.commit()

# Étiquettes des comptes et des lignes de taxes (déclaration de TVA) : étiquettes de la v20, liens convertis par nom
MigrationEtiquettesTaxes(db_src,db_dst,[
    ('account_account_account_tag','account_account_id'),
    ('account_account_tag_account_tax_repartition_line_rel','account_tax_repartition_line_id'),
])

# Devises (EUR = 1 en v14, 126 en v20)
MigrationDevisesParCode(db_src,db_dst,['account_account','account_journal'])

# Champs comptables de la société et valeurs par défaut (comptes clients / fournisseurs, comptes des catégories...) :
# valeur de la v14 (colonne de la société, propriété sans res_id), sinon valeur de la v20 convertie par la
# correspondance (champs ajoutés en v20), sinon vidée
tables_compta = {'account_account','account_tax','account_journal','account_fiscal_position','account_tax_group'}
colonnes_src = GetTypesChamps(cr_src,'res_company')
cr_src.execute("select * from res_company where id=1")
societe_src = cr_src.fetchone()
cr_dst.execute("select * from res_company where id=1")
societe_dst = cr_dst.fetchone()
# Sans contrôle des clés pendant ces mises à jour : la société est modifiée plusieurs fois dans la même transaction et
# PostgreSQL revérifie alors toutes ses clés, y compris les colonnes pas encore recalées (comptes v20 supprimés)
ControleCles(['res_company'],False)
for colonne,ref in GetClesEtrangeres(cr_dst,'res_company').items():
    if ref in tables_compta:
        valeur = societe_src[colonne] if colonne in colonnes_src else inverse.get(ref,{}).get(societe_dst[colonne])
        cr_dst.execute("update res_company set "+colonne+"=%s where id=1",[valeur])
cnx_dst.commit()
ControleCles(['res_company'],True)
SQL="""
    select d.id, f.model, f.name, f.relation, d.json_value
    from ir_default d join ir_model_fields f on f.id=d.field_id
    where f.relation in ('account.account','account.journal','account.tax','account.fiscal.position')
"""
cr_dst.execute(SQL)
for row in cr_dst.fetchall():
    cr_src.execute("""
        select p.value_reference from ir_property p join ir_model_fields f on f.id=p.fields_id
        where f.model=%s and f.name=%s and p.res_id is null and p.value_reference is not null
    """,[row['model'],row['name']])
    prop = cr_src.fetchone()
    valeur = int(prop['value_reference'].split(',')[1]) if prop else inverse.get(row['relation'].replace('.','_'),{}).get(json.loads(row['json_value']))
    if valeur:
        cr_dst.execute("update ir_default set json_value=%s where id=%s",[json.dumps(valeur),row['id']])
    else:
        cr_dst.execute("delete from ir_default where id=%s",[row['id']])
cnx_dst.commit()

# Propriétés par enregistrement (ir_property en v14 => colonnes jsonb par société en v20)
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_receivable_id')    # 372 comptes clients 411xxx
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_payable_id')       # 26
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_position_id')      # 13
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_income_id')   # 490
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_expense_id')  # 440

# Taxes des articles (ids des taxes de la v14)
for table in ['product_taxes_rel','product_supplier_taxes_rel']:
    MigrationTable(db_src,db_dst,table)

# Identifiants externes des modèles repris (journaux : par la correspondance par code, sans identifiant en v14)
# Taxes à 0 % : identifiants « biens » de la v20 gardés sur les taxes v14 correspondantes (voir taxes_renommees)
MigrationIrModelData(db_src,db_dst,['account.account','account.tax.group','account.tax','account.fiscal.position'],correspondances={
    'account.tax': {nom_dst:taxes_src[nom_src] for nom_src,nom_dst in taxes_renommees.items() if nom_src in taxes_src and nom_dst!='1_tva_normale'},
})
cr_dst.execute("select id,res_id from ir_model_data where model='account.journal'")
for row in cr_dst.fetchall():
    id14 = inverse['account_journal'].get(row['res_id'])
    if id14:
        cr_dst.execute("update ir_model_data set res_id=%s where id=%s",[id14,row['id']])
    else:
        cr_dst.execute("delete from ir_model_data where id=%s",[row['id']])
cr_dst.execute("delete from ir_model_data where model in ('account.reconcile.model','account.reconcile.model.line')")
cnx_dst.commit()
#******************************************************************************


# ** Reprise 2 : ventes ********************************************************
# Commandes (664 : 74 devis, 589 commandes, 1 annulée ; aucune « done ») ; procurement_group_id => références de stock
# (MigrationReferencesStock, plus bas) ; document_tax_mode : obligatoire en v20, réglage de la société (hors taxe)
MigrationTable(db_src,db_dst,'sale_order',default={'document_tax_mode':'tax_excluded','locked':False})
# Lignes (3 726) : product_uom => product_uom_id ; customer_lead : décimal en v14, entier en v20, toujours à 0 => 0
# Non repris (supprimés en v20) : price_reduce, product_packaging, qty_delivered_manual (vides), route_id (vide)
MigrationTable(db_src,db_dst,'sale_order_line',rename={'product_uom':'product_uom_id'},exclure=['customer_lead'],default={'customer_lead':0})
# Prix technique (nouveau, prix unitaire avant modification manuelle) et entrepôt de la ligne (stocké en v20)
cr_dst.execute("update sale_order_line set technical_price_unit=price_unit where technical_price_unit is null")
cr_dst.execute("update sale_order_line l set warehouse_id=o.warehouse_id from sale_order o where o.id=l.order_id")
cnx_dst.commit()
# Taxes des lignes (ids des taxes de la v14, reprises avec la comptabilité)
MigrationTable(db_src,db_dst,'account_tax_sale_order_line_rel')
MigrationDevisesParCode(db_src,db_dst,['sale_order','sale_order_line'])
# Lien entre les lignes de commande et les lignes de factures (sale_order_line_invoice_rel) : avec les factures
#******************************************************************************


# ** Reprise 2 : stock *********************************************************
# Le stock n'est utilisé que pour un inventaire (juin-juillet 2025 : 616 lignes, 1 550 unités, 5 609,80 €) : les
# 594 livraisons créées par les ventes depuis 2021 ne sont jamais validées (toutes « Prêt », 121,64 unités réservées).
# Tout est repris à l'identique (décision de Tony du 18/10/2026)

# Configuration : entrepôt WH, emplacements, types d'opérations, routes (stock_location_route en v14), règles, copiés
# avec les ids de la v14 ; correspondance par rôle avec ceux créés par la v20 (voir MigrationConfigurationStock)
MigrationConfigurationStock(db_src,db_dst)
# Routes des entrepôts (2) et des articles (3 865)
MigrationTable(db_src,db_dst,'stock_route_warehouse')
MigrationTable(db_src,db_dst,'stock_route_product')

# Quants (1 210 : 605 sur WH/Stock, les autres sur l'emplacement d'ajustement d'inventaire) ; pas de lots ni de colis
MigrationTable(db_src,db_dst,'stock_quant')

# Transferts (597), mouvements (4 011 : 620 faits par l'inventaire, 3 369 réservés ou en attente, 22 annulés) et lignes
# (3 982) ; voir MigrationTransfertsStock
MigrationTransfertsStock(db_src,db_dst)

# Valorisation : stock_valuation_layer (626 couches, supprimé en v20) => valeur des mouvements (stock_move.value) ;
# 6 couches sans mouvement (changements de coût) non reprises ; voir MigrationValorisationStock
MigrationValorisationStock(db_src,db_dst)

# Groupes d'approvisionnement (596, supprimés en v20) => références de stock, liens avec les mouvements et les commandes
MigrationReferencesStock(db_src,db_dst)
#******************************************************************************


# ** Reprise 3 : pièces comptables, lettrages, paiements ***********************
# Même méthode que Fromtome (v14 aussi, migration-odoo-fromtome-14-vers-20.py, étape 7)
# 4 824 pièces (4 553 factures, 18 avoirs dont 1 annulé, 253 pièces de paiements), 40 339 lignes ; journaux FAC et BNK1
# v14 : aucune pièce « à vérifier » ni comptabilisation automatique, pas de TVA sur encaissements, de relevés bancaires
# ni d'analytique
# auto_post (booléen, toujours faux) => 'no' ; to_check => review_state ; payment_id => origin_payment_id (après la copie
# des paiements) ; document_tax_mode : obligatoire pour les factures et avoirs, vide pour les autres pièces
# message_main_attachment_id (PDF des factures) : avec les pièces jointes (reprise 4)
# 8 avoirs (2024-2025) numérotés comme une facture du journal FAC (FAC/2024/0001 à 0007, FAC/2025/0001) : doublons
# refusés par l'index unique (name, journal_id) de la v20 => suffixe -AV (FAC/2024/0001-AV...), comme Fromtome ; même
# suffixe sur move_name des lignes
avoir_en_double = """
    t.move_type in ('out_refund','in_refund') and exists (
        select 1 from account_move f
        where f.journal_id=t.journal_id and f.name=t.name and f.id<>t.id and f.move_type not in ('out_refund','in_refund')
    )
"""
MigrationTable(db_src,db_dst,'account_move',rename={'tax_cash_basis_move_id':'tax_cash_basis_origin_move_id'},exclure=['auto_post','message_main_attachment_id'],
    expressions={
        'name'             : "case when "+avoir_en_double+" then t.name||'-AV' else t.name end",
        'auto_post'        : "'no'",
        'review_state'     : "'no_review'",
        # contrôlé dès le COPY (contrainte account_move_check_document_tax_mode_set) ; recalé juste après
        'document_tax_mode': "case when t.move_type in ('out_invoice','out_refund','out_receipt','in_invoice','in_refund','in_receipt') then 'tax_excluded' end",
    })
UpdateSansControle('account_move',"""
    update account_move set
        amount_untaxed_in_currency_signed = amount_untaxed_signed,
        amount_total_in_currency_signed   = amount_total_signed,
        invoice_currency_rate = 1,
        document_tax_mode = case when move_type in ('out_invoice','out_refund','out_receipt','in_invoice','in_refund','in_receipt')
                                 then (select account_price_include from res_company c where c.id=account_move.company_id) end
""")

# Lignes : display_type obligatoire en v20 (v14 : vide, sauf sections et notes ; exclude_from_invoice_tab pour les lignes
# de taxes et d'échéances des factures) et invoice_date stockée sur la ligne en v20 : calculés dans la requête du COPY
MigrationTable(db_src,db_dst,'account_move_line',expressions={
    'display_type': """
        case
            when t.display_type in ('line_section','line_note') then t.display_type
            when t.tax_line_id is not null then 'tax'
            when t.exclude_from_invoice_tab and (select m.move_type from account_move m where m.id=t.move_id)<>'entry' then 'payment_term'
            else 'product'
        end
    """,
    'invoice_date': "(select m.invoice_date from account_move m where m.id=t.move_id)",
    'move_name'   : "(select case when "+avoir_en_double+" then t.name||'-AV' else t.name end from account_move t where t.id=move_id)",
})
MigrationTable(db_src,db_dst,'account_move_line_account_tax_rel')
MigrationEtiquettesTaxes(db_src,db_dst,[('account_account_tag_account_move_line_rel','account_move_line_id')])

# Pièces toujours exigibles (nouveau en v20, stocké, comme _compute_always_tax_exigible) : pas une facture et aucune
# taxe sur encaissements
UpdateSansControle('account_move',"""
    update account_move m set always_tax_exigible = m.move_type='entry' and not exists (
        select 1 from account_move_line l
        left join account_move_line_account_tax_rel r on r.account_move_line_id=l.id
        join account_tax t on t.id in (l.tax_line_id, r.account_tax_id)
        where l.move_id=m.id and t.tax_exigibility='on_payment'
    )
""")

# Lettrages (456 partiels, 259 complets)
MigrationTable(db_src,db_dst,'account_full_reconcile')
MigrationTable(db_src,db_dst,'account_partial_reconcile')

# Paiements (253 : 247 encaissements, 6 remboursements, mode manuel, journal BNK1) : nom, date, journal, société et mémo
# portés par la pièce en v14 ; mode de paiement du journal et son compte d'attente (512003 / 512004)
MigrationTable(db_src,db_dst,'account_payment',exclure=['message_main_attachment_id'],default={'company_id':1,'date':'2000-01-01','journal_id':1,'state':'draft'})
UpdateSansControle('account_payment',"""
    update account_payment p set
        name       = m.name,
        date       = m.date,
        journal_id = m.journal_id,
        company_id = m.company_id,
        memo       = m.ref,
        currency_id = m.currency_id,
        commercial_partner_id = (select commercial_partner_id from res_partner r where r.id=p.partner_id),
        amount_company_currency_signed = case when p.payment_type='outbound' then -m.amount_total_signed else m.amount_total_signed end,
        is_sent    = false
    from account_move m
    where m.id=p.move_id
""")
UpdateSansControle('account_payment',"""
    update account_payment p set payment_method_line_id=l.id, outstanding_account_id=l.payment_account_id
    from account_payment_method_line l
    where l.journal_id=p.journal_id and l.payment_method_id=p.payment_method_id
""")
# État : draft / canceled selon la pièce, sinon comme Odoo 20 (_compute_state) : reconciled si les lignes de liquidité
# sont soldées, sinon paid
UpdateSansControle('account_payment',"""
    update account_payment p set state = case
        when m.state='draft'  then 'draft'
        when m.state='cancel' then 'canceled'
        when coalesce((
            select sum(l.amount_residual) from account_move_line l join account_journal j on j.id=m.journal_id
            where l.move_id=m.id and l.account_id=coalesce(p.outstanding_account_id,j.default_account_id)
        ),0)=0 then 'reconciled'
        else 'paid'
    end
    from account_move m
    where m.id=p.move_id
""")

# Pièce de chaque paiement : payment_id de la pièce en v14 => origin_payment_id
cr_src.execute("select id,payment_id from account_move where payment_id is not null")
execute_values(cr_dst,"update account_move m set origin_payment_id=s.payment_id from (values %s) as s(id,payment_id) where s.id=m.id",
    [(row['id'],row['payment_id']) for row in cr_src.fetchall()],page_size=5000)
cnx_dst.commit()

# Factures réglées par chaque paiement (invoice_ids du paiement) : d'après les lettrages de la v14
cr_dst.execute("delete from account_move__account_payment")
SQL="""
    select distinct l_facture.move_id invoice_id, m.payment_id
    from account_partial_reconcile r
    join account_move_line ld on ld.id=r.debit_move_id
    join account_move_line lc on lc.id=r.credit_move_id
    join account_move m on m.id in (ld.move_id,lc.move_id) and m.payment_id is not null
    join account_move_line l_facture on l_facture.id in (ld.id,lc.id) and l_facture.move_id<>m.id
    join account_move f on f.id=l_facture.move_id and f.move_type<>'entry'
"""
cr_src.execute(SQL)
execute_values(cr_dst,"insert into account_move__account_payment (invoice_id,payment_id) values %s on conflict do nothing",
    [(row['invoice_id'],row['payment_id']) for row in cr_src.fetchall()],page_size=5000)
cnx_dst.commit()

# Paiements « paid » => « reconciled » comme Odoo 20 (_compute_state) quand le compte d'attente n'est pas un compte de
# trésorerie et que toutes les factures réglées par le paiement sont payées
UpdateSansControle('account_payment',"""
    update account_payment p set state='reconciled'
    from account_journal j
    where j.id=p.journal_id and p.state='paid'
    and (select account_type from account_account a where a.id=coalesce(p.outstanding_account_id,j.default_account_id))<>'asset_cash'
    and exists (select 1 from account_move__account_payment r where r.payment_id=p.id)
    and not exists (select 1 from account_move__account_payment r join account_move f on f.id=r.invoice_id
                    where r.payment_id=p.id and f.payment_state<>'paid')
""")

# Liens entre les lignes de commande et les lignes de factures (3 358)
MigrationTable(db_src,db_dst,'sale_order_line_invoice_rel')

# Devises : EUR = 1 en v14
MigrationDevisesParCode(db_src,db_dst,['account_move','account_move_line','account_payment','account_partial_reconcile','account_full_reconcile'])

# Documents Factur-X de la v14 (account_edi_document, 4 571, XML en pièces jointes sans res_model) : supprimés en v20,
# non repris ; PDF des factures (4 574, avec le XML Factur-X intégré) : avec les pièces jointes (reprise 4)
#******************************************************************************


# ** Reprise 2 : séquences *****************************************************
# Commandes de vente (les transferts ont la séquence de leur type d'opération, recalée par MigrationConfigurationStock)
cr_src.execute("select id from ir_sequence where code='sale.order' order by id limit 1")
seq_src = cr_src.fetchone()
cr_dst.execute("select id from ir_sequence where code='sale.order' order by id limit 1")
seq_dst = cr_dst.fetchone()
MigrationIrSequence(db_src,db_dst,id_src=seq_src['id'],id_dst=seq_dst['id'])
#******************************************************************************


# ** Reprise 4 : pièces jointes ************************************************
# Même méthode que Dynamic Motion et Jurabotec
# Filestore de la production copié tel quel dans le filestore d'acpl20 => données seulement, store_fname conservé
# (copier_fichiers=False) ; ids de la v14 conservés (garder_ids), sauf collision avec les pièces jointes techniques de
# la v20
# Repris : factures (4 574 PDF, avec le XML Factur-X intégré) et partenaires (50), avec les images ; et les pièces
# jointes éventuelles des commandes, transferts et articles
# Non repris : pièces jointes techniques (vues, menus, icônes et moyens de paiement, langues, discussions), XML
# Factur-X des documents EDI de la v14 (4 570, sans res_model, déjà intégrés aux PDF), export compta (supprimé)
modeles = ('account.move','sale.order','stock.picking','product.template','product.product','res.partner')
cr_dst.execute("delete from ir_attachment where res_model in %s",[modeles]) # pièces jointes de la v20 (images par défaut, essais)
cnx_dst.commit()
where = """
    res_model in %s and coalesce(res_id,0)<>0
    and coalesce(res_field,'') in ('','image_1920','image_1024','image_512','image_256','image_128')
"""%str(modeles)
ids_pj = MigrationPiecesJointes(db_src,db_dst,where,copier_fichiers=False,garder_ids=True)

# Pièce jointe principale des factures (4 571 : leur PDF) ; supprimée en v20 sur les autres modèles
cr_src.execute("select id, message_main_attachment_id from account_move where message_main_attachment_id is not null")
execute_values(cr_dst,"update account_move m set message_main_attachment_id=s.attachment_id from (values %s) as s(id, attachment_id) where s.id=m.id",
    [(row['id'],ids_pj[row['message_main_attachment_id']]) for row in cr_src.fetchall() if row['message_main_attachment_id'] in ids_pj])
cnx_dst.commit()

# Ids qui auraient changé (collision avec les pièces jointes techniques de la v20) : remplacés partout
RemplacerIdsPiecesJointes(db_dst,ids_pj)

# PDF Factur-X des factures et avoirs clients validés (4 570) : en v14, gardés par le rapport (FAC_2026_0680.pdf) et pièce
# jointe principale de la facture ; en v20, PDF officiel = pièce jointe du champ invoice_pdf_report_file (envoi, portail,
# téléchargement : pas régénéré). Retrouvés par la pièce jointe principale et non par le nom : les 8 avoirs suffixés -AV
# ont le PDF de même nom que leur facture
SQL="""
    update ir_attachment a set res_field='invoice_pdf_report_file'
    from account_move m
    where a.id=m.message_main_attachment_id and a.res_model='account.move' and a.res_id=m.id and a.res_field is null
    and a.mimetype='application/pdf' and m.move_type in ('out_invoice','out_refund') and m.state='posted'
"""
cr_dst.execute(SQL)
print("PDF des factures (invoice_pdf_report_file) : %s"%cr_dst.rowcount)
cnx_dst.commit()

# Logo de l'application (logo_web : barre de navigation, page de connexion), calculé à partir du logo de la société à
# l'enregistrement de la société : colonne en base64 en v14, pièce jointe en v20 => logo de la v14 dans la pièce jointe
# de la v20 (contenu en base, db_datas : rien à écrire dans le filestore)
cr_src.execute("select logo_web from res_company where id=1")
logo = cr_src.fetchone()['logo_web']
if logo:
    contenu = base64.b64decode(bytes(logo))
    SQL="""
        update ir_attachment set store_fname=null, db_datas=%s, file_size=%s, checksum=%s, mimetype='image/png'
        where res_model='res.company' and res_field='logo_web' and res_id=1
    """
    cr_dst.execute(SQL,[psycopg2.Binary(contenu),len(contenu),hashlib.sha1(contenu).hexdigest()])
    cnx_dst.commit()
#******************************************************************************


# ** Reprise 4 : filtres favoris ***********************************************
# Actions retrouvées par identifiant externe ; is_acpl14 => is_acpl20 ; filtre sans action retrouvée : pour tous les
# menus du modèle, plus par défaut (voir MigrationIrFilters)
MigrationIrFilters(db_src,db_dst,modules={'is_acpl14':'is_acpl20'})
#******************************************************************************


# ** Reprise 4 : chatter et activités ******************************************
# Abonnés, messages et activités des enregistrements créés pendant les essais dans acpl20, supprimés par la relance
# (sinon « Erreur, un partenaire ne peut pas suivre deux fois le même objet »)
SupprimerChatterOrphelin(db_dst)

# Messages et abonnés des modèles repris avec les ids de la v14 ; nouveaux ids de messages ; suivi des modifications
# ajouté au corps (format v20)
# Non repris : modèles absents ou non repris en v20 (export compta, documents EDI...), discussions (mail.channel), mails
# sans modèle, notifications
ids_messages = MigrationChatter(db_src,db_dst,[
    'account.move',
    'account.payment',
    'sale.order',
    'stock.picking',
    'product.template',
    'product.product',
    'res.partner',
    'res.company',
    'crm.team',
    'account.journal',
    'account.account',
])

# Type « snailmail » (courrier) : module snailmail non installé en v20 => notification
cr_dst.execute("update mail_message set message_type='notification' where message_type='snailmail'")
cnx_dst.commit()

# Pièces jointes des messages (factures envoyées par mail...) : reprises plus haut avec leur enregistrement
cr_src.execute("select message_id,attachment_id from message_attachment_rel")
execute_values(cr_dst,"insert into message_attachment_rel (message_id,attachment_id) values %s on conflict do nothing",
    [(ids_messages[row['message_id']],ids_pj[row['attachment_id']]) for row in cr_src.fetchall()
     if row['message_id'] in ids_messages and row['attachment_id'] in ids_pj])
cnx_dst.commit()

# Activités (sale.mail_act_sale_upsell, supprimé en v20 => « À faire »)
MigrationActivites(db_src,db_dst,['account.move','sale.order','stock.picking','res.partner','product.template'],types={'sale.mail_act_sale_upsell':'mail.mail_activity_data_todo'})
#******************************************************************************


# ** Champs v20 à valeur par défaut ********************************************
# Déductibilité des lignes de pièces (100 %, sinon duplication d'une facture refusée) et bouton « Retour » des transferts
ValeursParDefautV20(db_dst)
#******************************************************************************


# ** Contrôle (lecture seule) **************************************************
# Clés étrangères qui ne pointent sur rien (tables copiées sans contrôle des clés)
ControleOrphelins(db_dst)
#******************************************************************************
