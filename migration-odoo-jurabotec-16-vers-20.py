#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Jurabotec : Odoo 16 (is_jurabotec) => Odoo 20 (is_jurabotec20)
# Documentation : Documentation/migration-odoo/migration-is_jurabotec16-vers-is_jurabotec20.md
from migration_fonction import *
from psycopg2.extras import execute_values


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
# is_emplacement_charge_id (3 partenaires, WH/JURAWOOD) : emplacements pas encore repris (ids différents en v20),
# sinon « Enregistrement inexistant ou supprimé (stock.location(56,)) » sur la fiche => à reprendre avec le stock
MigrationTable(db_src,db_dst,'res_partner',rename={'title':'is_civilite'},exclure=['is_emplacement_charge_id'],default={
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

# Vérification des TVA par VIES (activée en v16) : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont
# un n° de TVA (531, un appel à VIES toutes les 3 secondes, une seule transaction qui bloque les partenaires)
# => à réactiver après la bascule (Paramètres / Comptabilité) : les partenaires seront vérifiés au fil des modifications
cr_dst.execute("update res_company set vat_check_vies=false")
cnx_dst.commit()

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


# ** Unités de mesure *********************************************************
# Copiées avec les ids de la v16 (34 unités) : les tables qui les utilisent se copient ensuite sans conversion
# Chaque unité est rattachée à la référence de son ancienne catégorie (mlinéaire => 1 m, Boite (1600) => 1600 Unités...)
# Identifiants externes uom.* repointés ; Pack de 6, Minutes, ml et KWH (absents de la v16) recréés en 35 à 38 ;
# barcode_rule.associated_uom_id converti (voir MigrationUnites)
# Attention : l'unité « mètre » de la v16 est le yard (uom.product_uom_yard, 21 articles), gardée telle quelle (à décider)
MigrationUnites(db_src,db_dst)
#******************************************************************************


# ** Articles *****************************************************************
# Catégories (67) : nom texte en v16, traduisible en v20 ; comptes des catégories : à reprendre avec la comptabilité
MigrationTableJsonb(db_src,db_dst,'product_category')
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

# Étiquettes (25) : couleur entière en v16, code hexadécimal en v20 => non reprise
MigrationTable(db_src,db_dst,'product_tag',exclure=['color'])
MigrationTable(db_src,db_dst,'product_tag_product_template_rel')

# Attributs (Longueur, Traitement, Dimension) et valeurs (229) ; les 5 attributs d'exemple de la v20 sont remplacés
MigrationTable(db_src,db_dst,'product_attribute',default={'active':True})
MigrationTable(db_src,db_dst,'product_attribute_value',default={'active':True})

# Modèles d'articles (4 379)
# sale_delay : nombre en v16, jsonb en v20, toujours à 0 => non repris ; expense_policy => reinvoice_policy (tous à « no »)
# Nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count (valeurs par défaut d'Odoo)
MigrationTable(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},exclure=['sale_delay'],
    default={'service_tracking':'no','base_unit_count':0})
# Type « Article stockable » (product) supprimé en v18 => consommable (consu) avec la case « Suivre l'inventaire » (is_storable)
cr_dst.execute("update product_template set is_storable=(type='product'), type=case when type='product' then 'consu' else type end")
# Suivi « none » supprimé en v20 (seulement lot et serial) => vide ; sinon « Wrong value for product.template.store_by: 'none' »
cr_dst.execute("update product_template set tracking=null where tracking='none'")
# Favoris : priority='1' en v16 => is_favorite en v20 (469 articles)
cr_src.execute("select id from product_template where priority='1'")
ids = [row['id'] for row in cr_src.fetchall()]
cr_dst.execute("update product_template set is_favorite=(id = any(%s))",[ids])
cnx_dst.commit()

# Variantes (10 000)
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})
cr_dst.execute("update product_product p set is_favorite=t.is_favorite from product_template t where t.id=p.product_tmpl_id")
cnx_dst.commit()

# Attributs des articles et combinaisons des variantes
for table in [
    'product_attribute_product_template_rel',
    'product_template_attribute_line',
    'product_attribute_value_product_template_attribute_line_rel',
    'product_template_attribute_value',
    'product_variant_combination',
]:
    MigrationTable(db_src,db_dst,table)

# Prix de vente des variantes (lst_price) : calculé et stocké en v20 (prix du modèle + suppléments des attributs)
SQL="""
    update product_product p set lst_price = t.list_price + coalesce((
        select sum(v.price_extra)
        from product_variant_combination c join product_template_attribute_value v on v.id=c.product_template_attribute_value_id
        where c.product_product_id=p.id
    ),0)
    from product_template t where t.id=p.product_tmpl_id
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Coût des variantes (1 754 valeurs) et responsable des articles : propriétés en v16, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price')
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','responsible_id')

# Listes de prix (12) et lignes : toutes à prix fixe ; discount_policy supprimé en v20
# Lignes archivées (248) non reprises : plus d'archivage des lignes en v20, elles redeviendraient actives
MigrationTable(db_src,db_dst,'product_pricelist')
MigrationTable(db_src,db_dst,'product_pricelist_item',where="t.active")
# Liste de prix des clients (5 872 partenaires) : propriété en v16, champ jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_product_pricelist','specific_property_product_pricelist')

# Prix fournisseurs (745) : unité d'achat de l'article (uom_po_id, supprimé en v20) => unité du prix fournisseur (obligatoire)
MigrationTable(db_src,db_dst,'product_supplierinfo',default={'uom_id':1,'discount':0})
cr_src.execute("select s.id,t.uom_po_id from product_supplierinfo s join product_template t on t.id=s.product_tmpl_id")
for row in cr_src.fetchall():
    cr_dst.execute("update product_supplierinfo set uom_id=%s where id=%s",[row['uom_po_id'],row['id']])
cnx_dst.commit()

# Nomenclatures (429, dont 333 de type « Commande client » d'is_jurabotec20) : product_uom_id => uom_id
# Non repris (supprimés en v20) : consumption (toutes à « warning »), manual_consumption (33 lignes)
MigrationTable(db_src,db_dst,'mrp_bom',rename={'product_uom_id':'uom_id'})
MigrationTable(db_src,db_dst,'mrp_bom_line',rename={'product_uom_id':'uom_id'})
MigrationTable(db_src,db_dst,'mrp_bom_byproduct',rename={'product_uom_id':'uom_id'})

# Tables is_* liées aux articles
for table in [
    'is_product_template_calculateur_operation',
    'is_qualite_bois_product_template_rel',
    'is_contrat_fournisseur',
    'is_contrat_fournisseur_ligne',
]:
    MigrationTable(db_src,db_dst,table)

# Ids des devises : ids de la v16 => ids de la v20 (EUR = 1 en v16, 126 en v20)
MigrationDevisesParCode(db_src,db_dst,['product_template','product_pricelist','product_pricelist_item','product_supplierinfo'])

# Identifiants externes : catégories renommées en v20 (product_category_all => product_category_goods...),
# attributs d'exemple de la v20 (pa_brand, pa_color...) supprimés
cr_src.execute("select name,res_id from ir_model_data where model='product.category'")
categories = {row['name']:row['res_id'] for row in cr_src.fetchall()}
MigrationIrModelData(db_src,db_dst,['product.category','product.attribute','product.pricelist'],correspondances={
    'product.category': {
        'product_category_goods'   : categories.get('product_category_all'),
        'product_category_expenses': categories.get('cat_expense'),
        'product_category_services': categories.get('product_category_1'),
    },
})

# A reprendre avec la comptabilité : taxes des articles (product_taxes_rel, product_supplier_taxes_rel : ids des taxes
# différents en v20), comptes des articles et des catégories
# A reprendre avec les pièces jointes : images, plans (product_template_is_plan_rel), FDS (product_template_is_fds_rel)
#******************************************************************************


# ** Configuration du stock ***************************************************
# Entrepôt, emplacements (60), types d'opérations (9), routes (7), règles (10) copiés avec les ids de la v16 (ids
# différents en v20 : WH/Stock = 8 en v16, 6 en v20) ; correspondance par rôle avec ceux créés par la v20 pour recaler
# ses références (société, emplacements par défaut, identifiants externes) ; types Contrôle qualité, Stockage et
# Correspondance de la v20 recréés (utilisés par l'entrepôt v20) ; séquences des types recalées sur la v16 (RCP, BL...)
# Emplacements vues Physical Locations, Partners, Virtual Locations (supprimés en v18) retirés
MigrationConfigurationStock(db_src,db_dst,correspondances_xmlids={'stock_location_inter_company':'stock_location_inter_wh'})
MigrationTable(db_src,db_dst,'stock_route_warehouse')
MigrationTable(db_src,db_dst,'stock_route_product')                               # routes des articles (4 428)
MigrationTable(db_src,db_dst,'stock_putaway_rule',default={'sublocation':'no'})   # règles de rangement (10)

# Emplacement des charges des partenaires (3, WH/JURAWOOD) : non repris avec les partenaires (emplacements pas encore là)
cr_src.execute("select id,is_emplacement_charge_id from res_partner where is_emplacement_charge_id is not null")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set is_emplacement_charge_id=%s where id=%s",[row['is_emplacement_charge_id'],row['id']])
cnx_dst.commit()
#******************************************************************************


# ** Lots et stock ************************************************************
# Lots (5 714) : product_uom_id supprimé en v20
MigrationTable(db_src,db_dst,'stock_lot')
# Quants (16 597, dont 80 avec une quantité réservée : à vérifier avec la reprise des mouvements)
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

# Règles de réapprovisionnement (370) : qty_to_order => qty_to_order_manual ; nouvelles colonnes obligatoires en v20 :
# valeurs par défaut d'Odoo ; vendor_id supprimé (même fournisseur que supplier_id)
# Non repris : qty_multiple (« Multiple » : unité en v20) : 2 règles à revoir (ROULEAU 330 POINTES par 20, EPICEA DU NORD 25*75 par 2)
MigrationTable(db_src,db_dst,'stock_warehouse_orderpoint',rename={'qty_to_order':'qty_to_order_manual'},default={
    'min_max_based_on'       : 'one_month',
    'min_max_based_on_factor': 100,
    'daily_demand'           : 0,
})

# Inventaires (module is_jurabotec20) et tables is_* du stock (charges, scans)
for table in [
    'is_inventaire',
    'stock_inventory',
    'stock_inventory_line',
    'is_creation_charge',
    'is_deplacement_charge',
    'is_scan_inventaire',
    'is_scan_inventaire_ligne',
    'is_scan_inventaire_ligne_stock_location_rel',
    'is_scan_deplacement_charge',
]:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** Équipes commerciales *****************************************************
# 4 équipes (Ventes, et 3 archivées) : ids identiques pour les 3 standard ; eBay en plus en v16
MigrationTable(db_src,db_dst,'crm_team')
MigrationTable(db_src,db_dst,'crm_team_member')
MigrationTable(db_src,db_dst,'crm_tag')
MigrationIrModelData(db_src,db_dst,['crm.team'])
#******************************************************************************


# ** Conditions de paiement ***************************************************
# 17 conditions (10 standard en v20, ids différents pour certaines) copiées avec les ids de la v16, échéances converties
# au format v20 (voir MigrationConditionsPaiement) : utilisées par les commandes, sinon « Enregistrement manquant »
MigrationConditionsPaiement(db_src,db_dst)
# Conditions des clients (5 116) et des fournisseurs (97) : propriétés en v16, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_payment_term_id')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_supplier_payment_term_id')
#******************************************************************************


# ** Ventes *******************************************************************
# Commandes (5 127) : aucune à l'état « done » (supprimé en v17) ; procurement_group_id => stock_reference (plus bas)
# document_tax_mode : obligatoire en v20, réglage de la société (prix hors taxe)
MigrationTable(db_src,db_dst,'sale_order',default={'document_tax_mode':'tax_excluded','locked':False})
# Lignes (21 048) : product_uom => product_uom_id ; customer_lead : décimal en v16, entier en v20, toujours à 0
# Taxes des lignes (account_tax_sale_order_line_rel) : avec la comptabilité (ids des taxes différents)
MigrationTable(db_src,db_dst,'sale_order_line',rename={'product_uom':'product_uom_id'},exclure=['customer_lead'],default={'customer_lead':0})
# Prix technique (nouveau, prix unitaire avant modification manuelle) et entrepôt de la ligne (stocké en v20)
cr_dst.execute("update sale_order_line set technical_price_unit=price_unit where technical_price_unit is null")
cr_dst.execute("update sale_order_line l set warehouse_id=o.warehouse_id from sale_order o where o.id=l.order_id")
cnx_dst.commit()
MigrationDevisesParCode(db_src,db_dst,['sale_order','sale_order_line'])

# Colis Hekipia (7 076) et composants (39 769)
MigrationTable(db_src,db_dst,'is_sale_order_colis')
MigrationTable(db_src,db_dst,'is_sale_order_colisage_composant')
#******************************************************************************


# ** Achats *******************************************************************
# Commandes (845) : notes => note ; état « done » (1 commande) => « purchase » verrouillée (locked)
MigrationTable(db_src,db_dst,'purchase_order',rename={'notes':'note'},default={'document_tax_mode':'tax_excluded','locked':False})
cr_dst.execute("update purchase_order set state='purchase', locked=true where state='done'")
cnx_dst.commit()
# Lignes (2 603) : product_uom => uom_id ; remise (nouvelle) à 0 ; prix technique = prix unitaire
MigrationTable(db_src,db_dst,'purchase_order_line',rename={'product_uom':'uom_id'},default={'discount':0})
SQL="""
    update purchase_order_line l set
        technical_price_unit   = l.price_unit,
        price_unit_product_uom = case when l.display_type is null then l.price_unit * pu.factor / lu.factor end,
        qty_to_invoice_raw     = l.product_qty - coalesce(l.qty_invoiced,0)
    from product_product p, product_template t, uom_uom pu, uom_uom lu
    where p.id=l.product_id and t.id=p.product_tmpl_id and pu.id=t.uom_id and lu.id=l.uom_id
"""
cr_dst.execute(SQL)
cnx_dst.commit()
MigrationTable(db_src,db_dst,'purchase_order_stock_picking_rel')
MigrationDevisesParCode(db_src,db_dst,['purchase_order','purchase_order_line'])
#******************************************************************************


# Les mises à jour qui suivent la copie se font sans contrôle des clés étrangères, comme la copie (MigrationTable) :
# PostgreSQL revérifie tous les liens d'une ligne modifiée deux fois dans la même transaction (ex : mouvement d'un OF
# pas encore copié) ; les liens orphelins sont contrôlés après le lancement
import atexit
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


# ** Fabrication **************************************************************
# Ordres de fabrication (268) : product_uom_id => uom_id ; date_planned_start / finished => date_start / date_finished
# (date_start obligatoire en v20) ; lot_producing_id => lot_producing_ids ; procurement_group_id => production_group_id
MigrationTable(db_src,db_dst,'mrp_production',rename={'product_uom_id':'uom_id'},default={'date_start':'1970-01-01'})
ControleCles(['mrp_production'],False)
cr_src.execute("select id, date_planned_start, date_planned_finished, date_start, date_finished, lot_producing_id, procurement_group_id, name from mrp_production")
productions = cr_src.fetchall()
cr_dst.execute("delete from mrp_production_stock_lot_rel; delete from mrp_production_group_rel; update mrp_production set production_group_id=null; delete from mrp_production_group;")
for p in productions:
    cr_dst.execute("update mrp_production set date_start=%s, date_finished=%s where id=%s",
        [p['date_start'] or p['date_planned_start'], p['date_finished'] or p['date_planned_finished'], p['id']])
    if p['lot_producing_id']:
        cr_dst.execute("insert into mrp_production_stock_lot_rel (mrp_production_id,stock_lot_id) values (%s,%s)",[p['id'],p['lot_producing_id']])
# Groupe de production (reliquats d'un même OF) : un par groupe d'approvisionnement de la v16 (même id, même nom)
cr_src.execute("select distinct g.id, g.name, g.create_uid, g.create_date, g.write_uid, g.write_date from procurement_group g join mrp_production p on p.procurement_group_id=g.id")
for g in cr_src.fetchall():
    cr_dst.execute("insert into mrp_production_group (id,name,create_uid,create_date,write_uid,write_date) values (%s,%s,%s,%s,%s,%s)",
        [g['id'],g['name'],g['create_uid'],g['create_date'],g['write_uid'],g['write_date']])
for p in productions:
    if p['procurement_group_id']:
        cr_dst.execute("update mrp_production set production_group_id=%s where id=%s",[p['procurement_group_id'],p['id']])
cnx_dst.commit()
ControleCles(['mrp_production'],True)
SetSequence(cr_dst,cnx_dst,'mrp_production_group')
#******************************************************************************


# ** Transferts et mouvements de stock ****************************************
# Transferts (10 837) : group_id => stock_reference (plus bas), date et immediate_transfer supprimés
MigrationTable(db_src,db_dst,'stock_picking')
# Retour de (return_id, nouveau en v20) : transfert d'origine des mouvements retournés (93 mouvements)
SQL="""
    update stock_picking p set return_id=r.picking_id
    from (
        select m.picking_id as id, min(om.picking_id) as picking_id
        from stock_move m join stock_move om on om.id=m.origin_returned_move_id
        where m.picking_id is not null and om.picking_id is not null group by m.picking_id
    ) r
    where r.id=p.id
"""

# Mouvements (41 091) : product_uom => uom_id ; quantity_done => quantity + picked (calculés plus bas avec les lignes) ;
# scrapped => is_scrap ; description_picking => description_picking_manual (libellé saisi, ex : ligne de commande)
# Non repris (supprimés en v20) : name, product_packaging_id, created_purchase_line_id, manual_consumption
MigrationTable(db_src,db_dst,'stock_move',rename={'product_uom':'uom_id','scrapped':'is_scrap','description_picking':'description_picking_manual'})

# Lignes de mouvement (42 789) : product_uom_id => uom_id ; qty_done (fait) et reserved_uom_qty (réservé) => quantity,
# picked si une quantité est faite (en v20, une seule quantité : réservée tant que picked est faux)
MigrationTable(db_src,db_dst,'stock_move_line',rename={'product_uom_id':'uom_id'})
ControleCles(['stock_picking','stock_move','stock_move_line'],False)
cr_dst.execute(SQL) # return_id des transferts (mouvements nécessaires)
cnx_dst.commit()
cr_src.execute("select id, qty_done, reserved_uom_qty from stock_move_line")
lignes = cr_src.fetchall()
execute_values(cr_dst,"""
    update stock_move_line l set
        quantity = case when s.qty_done<>0 then s.qty_done else s.reserved_uom_qty end,
        picked   = s.qty_done<>0
    from (values %s) as s(id, qty_done, reserved_uom_qty)
    where s.id=l.id
""",[(r['id'],r['qty_done'] or 0,r['reserved_uom_qty'] or 0) for r in lignes],page_size=5000)
cnx_dst.commit()
# Mouvements : quantité = quantité faite si le mouvement est fait, sinon somme de ses lignes (dans l'unité du mouvement)
cr_src.execute("select id, quantity_done from stock_move where state='done'")
execute_values(cr_dst,"""
    update stock_move m set quantity=s.quantity_done, picked=true
    from (values %s) as s(id, quantity_done) where s.id=m.id
""",[(r['id'],r['quantity_done'] or 0) for r in cr_src.fetchall()],page_size=5000)
SQL="""
    update stock_move m set
        quantity = coalesce((select sum(l.quantity * lu.factor / mu.factor)
                             from stock_move_line l join uom_uom lu on lu.id=l.uom_id where l.move_id=m.id),0),
        picked   = exists (select 1 from stock_move_line l where l.move_id=m.id and l.picked)
    from uom_uom mu
    where mu.id=m.uom_id and m.state<>'done'
"""
cr_dst.execute(SQL)
# Quantités dans l'unité de l'article (stockées en v20)
precision = "(select digits from decimal_precision where name='Product Unit')"
for table in ['stock_move','stock_move_line']:
    SQL="""
        update """+table+""" x set quantity_product_uom = round((x.quantity * xu.factor / pu.factor)::numeric, """+precision+""")
        from uom_uom xu, product_product p, product_template t, uom_uom pu
        where xu.id=x.uom_id and p.id=x.product_id and t.id=p.product_tmpl_id and pu.id=t.uom_id
    """
    cr_dst.execute(SQL)
cnx_dst.commit()
ControleCles(['stock_picking','stock_move','stock_move_line'],True)
MigrationTable(db_src,db_dst,'stock_move_move_rel')
MigrationTable(db_src,db_dst,'stock_move_line_consume_rel')
# Non repris pour l'instant : valorisation des mouvements (is_in, is_out, value, stock_valuation_layer) : avec la comptabilité
#******************************************************************************


# ** Groupes d'approvisionnement => références de stock ***********************
# procurement_group (5 633, supprimé en v20) => stock_reference (mêmes ids) et ses liens avec les mouvements, les
# commandes de vente et d'achat et les ordres de fabrication
MigrationTable(db_src,db_dst,'procurement_group','stock_reference')
cr_dst.execute("delete from stock_reference_move_rel; delete from stock_reference_sale_rel; delete from stock_reference_purchase_rel; delete from stock_reference_production_rel;")
liens = [
    ("stock_reference_move_rel",       "move_id",       "select id, group_id from stock_move where group_id is not null"),
    ("stock_reference_sale_rel",       "sale_id",       "select id, procurement_group_id from sale_order where procurement_group_id is not null union select sale_id, id from procurement_group where sale_id is not null"),
    ("stock_reference_purchase_rel",   "purchase_id",   "select id, group_id from purchase_order where group_id is not null"),
    ("stock_reference_production_rel", "production_id", "select id, procurement_group_id from mrp_production where procurement_group_id is not null"),
]
for table,colonne,SQL in liens:
    cr_src.execute(SQL)
    lignes = [tuple(row.values()) for row in cr_src.fetchall()]
    execute_values(cr_dst,"insert into "+table+" ("+colonne+",reference_id) values %s on conflict do nothing",lignes,page_size=5000)
    print("%s : %s liens"%(table,len(lignes)))
cnx_dst.commit()
#******************************************************************************


# ** Séquences ****************************************************************
# Commandes de vente (CDE), d'achat (P), lots, contrats fournisseurs, export compta, inventaires
for code in ['sale.order','purchase.order','stock.lot.serial','is.contrat.fournisseur','is.export.compta','is.inventaire']:
    cr_src.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
    seq_src = cr_src.fetchone()
    cr_dst.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
    seq_dst = cr_dst.fetchone()
    if seq_src and seq_dst:
        MigrationIrSequence(db_src,db_dst,id_src=seq_src['id'],id_dst=seq_dst['id'])
    else:
        print("Séquence %s : absente (source %s, destination %s)"%(code,seq_src,seq_dst))
#******************************************************************************


# ** Paramètres comptables ****************************************************
# Plan comptable (1 905 comptes), groupes de taxes, taxes (69), positions fiscales, journaux (10) de la v16 copiés avec
# leurs ids à la place de ceux créés par l10n_fr en v20 (ids différents) ; colonnes ajoutées par la v20 (codes Factur-X
# des taxes, comptes de stock...) reprises de l'enregistrement v20 équivalent ; références de la v20 recalées
# Voir Documentation/migration-odoo/migration-vers-odoo20.md § 3.7 et § 5.4

# Lignes v20 et correspondance par identifiant externe, avant la copie
avant, corr = {}, {}
for table,suffixes in [('account_account',[]),('account_tax_group',[]),('account_tax',['_TTC','_ttc']),('account_fiscal_position',[])]:
    avant[table], corr[table] = LireAvantCopie(db_src,db_dst,table,suffixes)
avant['account_journal'], _ = LireAvantCopie(db_src,db_dst,'account_journal')
# Journaux : pas d'identifiant externe en v16 => correspondance par code (FAC, OD, EXCH, CABA, BNK1, STJ), sinon par type
# s'il n'y en a qu'un (achats : FACTU en v16, FACTURE en v20)
cr_src.execute("select id,code,type from account_journal")
journaux_src = cr_src.fetchall()
corr['account_journal'] = {}
for j20 in avant['account_journal'].values():
    j16 = [j for j in journaux_src if j['code']==j20['code']] or [j for j in journaux_src if j['type']==j20['type']]
    if len(j16)==1 and j16[0]['id'] not in corr['account_journal']:
        corr['account_journal'][j16[0]['id']] = j20['id']
print("Journaux (id v16 : id v20) : %s"%corr['account_journal'])
inverse = {t:{id20:id_src for id_src,id20 in sorted(c.items(),reverse=True)} for t,c in corr.items()} # id v20 => id v16

# Tables de la v20 liées aux anciens comptes et taxes, sans équivalent repris
for table in [
    'account_tax_filiation_rel',                # taxes groupées (aucune)
    'account_fiscal_position_account',          # correspondances de comptes (aucune)
    'account_fiscal_position_account_tax_rel',  # recréées plus bas à partir de la v16
    'account_tax_alternatives',                 # recréées plus bas à partir de la v16
    'account_reconcile_model_line',             # modèles de rapprochement : format changé, pas de relevés bancaires
    'account_reconcile_model',
]:
    cr_dst.execute("delete from "+table)
cnx_dst.commit()

# Comptes : nom traduisible, code => code_store (par société), deprecated => active, société => account_account_res_company_rel
MigrationTableJsonb(db_src,db_dst,'account_account')
# Colonnes ajoutées par la v20 (description, comptes de stock...) d'abord : code_store et active sont posés juste après
CompleterColonnesV20(db_src,db_dst,'account_account',avant['account_account'],corr['account_account'],inverse)
cr_src.execute("select id,code,deprecated,company_id from account_account")
comptes = cr_src.fetchall()
cr_dst.execute("delete from account_account_res_company_rel")
execute_values(cr_dst,"""
    update account_account a set code_store=jsonb_build_object('1',s.code), active=not s.deprecated
    from (values %s) as s(id,code,deprecated) where s.id=a.id
""",[(row['id'],row['code'],bool(row['deprecated'])) for row in comptes],page_size=5000)
execute_values(cr_dst,"insert into account_account_res_company_rel (account_account_id,res_company_id) values %s",
    [(row['id'],row['company_id'] or 1) for row in comptes])
cnx_dst.commit()
parent_store_compute(cr_dst,cnx_dst,'account_account','parent_id') # hiérarchie des comptes (parent_path avec les ids v16)
MigrationTable(db_src,db_dst,'account_account_tax_default_rel')

# Groupes de taxes (société obligatoire en v20) et taxes : price_include => price_include_override (vide = réglage de la société)
MigrationTableJsonb(db_src,db_dst,'account_tax_group',default={'company_id':1})
CompleterColonnesV20(db_src,db_dst,'account_tax_group',avant['account_tax_group'],corr['account_tax_group'],inverse)
MigrationTableJsonb(db_src,db_dst,'account_tax')
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

# Journaux (10) : alias de messagerie non repris ; modes de paiement des journaux
MigrationTableJsonb(db_src,db_dst,'account_journal',default={'invoice_reference_type':'invoice','invoice_reference_model':'odoo'})
cr_dst.execute("update account_journal set alias_id=null")
cnx_dst.commit()
CompleterColonnesV20(db_src,db_dst,'account_journal',avant['account_journal'],corr['account_journal'],inverse)
MigrationTable(db_src,db_dst,'account_payment_method_line')

# Étiquettes des comptes et des lignes de taxes (déclaration de TVA) : étiquettes de la v20, liens convertis par nom
MigrationEtiquettesTaxes(db_src,db_dst,[
    ('account_account_account_tag','account_account_id'),
    ('account_account_tag_account_tax_repartition_line_rel','account_tax_repartition_line_id'),
])

# Devises : EUR = 1 en v16, 126 en v20
MigrationDevisesParCode(db_src,db_dst,['account_account','account_journal'])

# Champs comptables de la société et valeurs par défaut (comptes clients / fournisseurs, comptes des catégories,
# journal de stock...) : valeur de la v16 (colonne de la société, propriété sans res_id), sinon valeur de la v20
# convertie par la correspondance (champs ajoutés en v20 : arrondis l10n_fr, acompte...), sinon vidée
tables_compta = {'account_account','account_tax','account_journal','account_fiscal_position','account_tax_group'}
colonnes_src = GetTypesChamps(cr_src,'res_company')
cr_src.execute("select * from res_company where id=1")
societe_src = cr_src.fetchone()
cr_dst.execute("select * from res_company where id=1")
societe_dst = cr_dst.fetchone()
for colonne,ref in GetClesEtrangeres(cr_dst,'res_company').items():
    if ref in tables_compta:
        valeur = societe_src[colonne] if colonne in colonnes_src else inverse.get(ref,{}).get(societe_dst[colonne])
        cr_dst.execute("update res_company set "+colonne+"=%s where id=1",[valeur])
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

# Propriétés par enregistrement (ir_property en v16 => colonnes jsonb par société en v20)
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_receivable_id')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_payable_id')
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_position_id')   # 16 partenaires
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_income_id')
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_expense_id')
MigrationIrPropertyJsonb(db_src,db_dst,'product.category','property_account_income_categ_id')   # 54 catégories
MigrationIrPropertyJsonb(db_src,db_dst,'product.category','property_account_expense_categ_id')  # 49 catégories

# Taxes des articles, des lignes de commande de vente et d'achat (ids des taxes de la v16)
for table in ['product_taxes_rel','product_supplier_taxes_rel','account_tax_sale_order_line_rel','account_tax_purchase_order_line_rel']:
    MigrationTable(db_src,db_dst,table)

# Identifiants externes des modèles repris (journaux : par la correspondance par code, sans identifiant en v16)
MigrationIrModelData(db_src,db_dst,['account.account','account.tax.group','account.tax','account.fiscal.position'])
cr_dst.execute("select id,res_id from ir_model_data where model='account.journal'")
for row in cr_dst.fetchall():
    id16 = inverse['account_journal'].get(row['res_id'])
    if id16:
        cr_dst.execute("update ir_model_data set res_id=%s where id=%s",[id16,row['id']])
    else:
        cr_dst.execute("delete from ir_model_data where id=%s",[row['id']])
cr_dst.execute("delete from ir_model_data where model in ('account.reconcile.model','account.reconcile.model.line')")
cnx_dst.commit()
#******************************************************************************


# ** Pièces comptables ********************************************************
# 5 593 pièces (2 751 factures, 43 avoirs, 4 factures fournisseurs, 2 793 pièces de paiement), 33 407 lignes
# v16 : aucune pièce « à vérifier », aucune extourne (storno), aucune comptabilisation automatique, aucun litige (blocked)
# to_check => review_state ; payment_id => origin_payment_id (après la copie des paiements) ; document_tax_mode :
# obligatoire pour les factures et avoirs, vide pour les autres pièces (comme _compute_document_tax_mode)
MigrationTable(db_src,db_dst,'account_move',default={'review_state':'no_review','document_tax_mode':'tax_excluded'})
SQL="""
    update account_move set
        amount_untaxed_in_currency_signed = amount_untaxed_signed,
        invoice_currency_rate = 1,
        document_tax_mode = case when move_type in ('out_invoice','out_refund','out_receipt','in_invoice','in_refund','in_receipt')
                                 then (select account_price_include from res_company c where c.id=account_move.company_id) end
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Lignes : display_type déjà renseigné en v16 ; invoice_date stockée sur la ligne en v20
MigrationTable(db_src,db_dst,'account_move_line')
cr_dst.execute("update account_move_line l set invoice_date=m.invoice_date from account_move m where m.id=l.move_id")
cnx_dst.commit()
MigrationTable(db_src,db_dst,'account_move_line_account_tax_rel')
MigrationEtiquettesTaxes(db_src,db_dst,[('account_account_tag_account_move_line_rel','account_move_line_id')])

# Lettrages
MigrationTable(db_src,db_dst,'account_full_reconcile')
MigrationTable(db_src,db_dst,'account_partial_reconcile')

# Paiements (2 793) : nom, date, journal, société et mémo portés par la pièce en v16 ; état : draft / canceled selon la
# pièce, sinon comme Odoo 20 (_compute_state) : reconciled si les lignes de liquidité sont soldées, sinon paid
MigrationTable(db_src,db_dst,'account_payment',default={'company_id':1,'date':'2000-01-01','journal_id':1,'state':'draft'})
SQL="""
    update account_payment p set
        name       = m.name,
        date       = m.date,
        journal_id = m.journal_id,
        company_id = m.company_id,
        memo       = m.ref,
        currency_id = m.currency_id,
        commercial_partner_id = (select commercial_partner_id from res_partner r where r.id=p.partner_id),
        amount_company_currency_signed = case when p.payment_type='outbound' then -m.amount_total_signed else m.amount_total_signed end,
        is_sent    = false,
        state = case
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
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Pièce de chaque paiement : payment_id de la pièce en v16 => origin_payment_id
cr_src.execute("select id,payment_id from account_move where payment_id is not null")
execute_values(cr_dst,"update account_move m set origin_payment_id=s.payment_id from (values %s) as s(id,payment_id) where s.id=m.id",
    [(row['id'],row['payment_id']) for row in cr_src.fetchall()])
cnx_dst.commit()

# Factures réglées par chaque paiement (invoice_ids du paiement) : d'après les lettrages de la v16
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
    [(row['invoice_id'],row['payment_id']) for row in cr_src.fetchall()])
cnx_dst.commit()

# Paiements « paid » => « reconciled » comme Odoo 20 (_compute_state) quand le compte d'attente n'est pas un compte de
# trésorerie et que toutes les factures réglées par le paiement sont payées
SQL="""
    update account_payment p set state='reconciled'
    from account_journal j
    where j.id=p.journal_id and p.state='paid'
    and (select account_type from account_account a where a.id=coalesce(p.outstanding_account_id,j.default_account_id))<>'asset_cash'
    and exists (select 1 from account_move__account_payment r where r.payment_id=p.id)
    and not exists (select 1 from account_move__account_payment r join account_move f on f.id=r.invoice_id
                    where r.payment_id=p.id and f.payment_state<>'paid')
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Pièce jointe principale des pièces (323) : vidée tant que les pièces jointes ne sont pas reprises (elle pointerait sur
# une pièce jointe absente ou sur une autre pièce jointe de la v20) => à remettre avec les pièces jointes
cr_dst.execute("update account_move set message_main_attachment_id=null")
cnx_dst.commit()

# Liens avec les commandes : lignes de commande de vente => lignes de factures, commandes d'achat => factures
MigrationTable(db_src,db_dst,'sale_order_line_invoice_rel')
MigrationTable(db_src,db_dst,'account_move_purchase_order_rel')

# Devises : EUR = 1 en v16, 126 en v20
MigrationDevisesParCode(db_src,db_dst,['account_move','account_move_line','account_payment','account_partial_reconcile','account_full_reconcile'])

# Export compta (119 exports, 10 565 lignes) et éco-contribution Valobat des factures (42)
# Pièces jointes des exports (is_export_compta_attachment_rel) : avec les pièces jointes
for table in ['is_export_compta','is_export_compta_ligne','is_account_move_valobat']:
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
