#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données d'ACPL : Odoo 14 (is_acpl14) => Odoo 20 (is_acpl20)
# Documentation : Documentation/migration-odoo/migration-is_acpl14-vers-is_acpl20.md
# Première partie : contacts, utilisateurs, société, unités, articles, conditions de paiement, paramètres comptables
# A faire ensuite : commandes, livraisons et stock, factures et paiements, séquences, chatter, pièces jointes
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit


#** Paramètres ****************************************************************
db_src = "acpl14"
db_dst = "acpl20"
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# acpl20-vierge : base v20 avec is_acpl20 installé, sans données (à créer par Tony)
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


# ** res_partner et res_users *************************************************
# Copiés avec les ids de la source (486 partenaires, 7 utilisateurs dont 2 actifs dans acpl14)
# mobile (12 partenaires, dont 6 sans téléphone) et title (civilité, 3 partenaires) : supprimés d'Odoo en v20, non
# repris (question 2 de la doc)
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

# Comptes bancaires : aucun dans la source (IBAN écrit en dur sur la facture)
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
#   équivalent en v20 => 30 jours (question 3 de la doc)
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
avant, corr = {}, {}
for table in ['account_account','account_tax_group','account_tax','account_fiscal_position']:
    avant[table], corr[table] = LireAvantCopie(db_src,db_dst,table)
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
MigrationIrModelData(db_src,db_dst,['account.account','account.tax.group','account.tax','account.fiscal.position'])
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
