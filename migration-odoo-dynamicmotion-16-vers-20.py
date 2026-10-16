#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Dynamic Motion : Odoo 16 (is_dynamicmotion) => Odoo 20 (is_dynamicmotion20)
# Documentation : Documentation/migration-odoo/migration-is_dynamicmotion16-vers-is_dynamicmotion20.md
from migration_fonction import *
import atexit


#** Paramètres ****************************************************************
db_src = "dynamicmotion16"
db_dst = "dynamicmotion20"
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
# Copiés avec les ids de la source (749 partenaires, 16 utilisateurs dans dynamicmotion16)
# mobile (44 partenaires, dont 20 sans téléphone) et title (civilité, 163 partenaires) : supprimés d'Odoo en v20, non repris
# siret, company_registry : vides dans la source
# Nouvelle colonne obligatoire en v20 : autopost_bills (valeur par défaut d'Odoo)
# Propriétés comptables (comptes, conditions de paiement, positions fiscales) : à reprendre avec la comptabilité
MigrationTable(db_src,db_dst,'res_partner',default={
    'autopost_bills': 'ask',
})
MigrationTable(db_src,db_dst,'res_users')

# Société 2 « Delta Line » non reprise : aucune commande, aucun OF, aucune pièce comptable (1 utilisateur y a accès)
MigrationTable(db_src,db_dst,'res_company_users_rel',where="cid=1")

# Dernière connexion de chaque utilisateur (une ligne par utilisateur, Odoo ne garde que la dernière) :
# sans elle, le statut des utilisateurs est « Invité » au lieu de « Confirmé » (calculé d'après login_date)
MigrationTable(db_src,db_dst,'res_users_log')

# Type d'adresse « private » (adresse privée d'employé) supprimé en v17 => contact (4 partenaires)
# Un contact doit avoir un nom (contrainte res_partner_check_name) : adresse privée sans nom (1 partenaire)
# => nom de l'employé lié (employés non repris, hors périmètre)
cr_src.execute("""
    select p.id,e.name from res_partner p join hr_employee e on e.address_home_id=p.id
    where p.type='private' and coalesce(p.name,'')=''
""")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set name=%s where id=%s",[row['name'],row['id']])
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

# Étiquettes des partenaires (39 étiquettes, 580 liens)
MigrationTable(db_src,db_dst,'res_partner_category')
MigrationTable(db_src,db_dst,'res_partner_res_partner_category_rel')

# Groupes : correspondance par nom d'identifiant externe
# Les groupes des modules absents en v20 (purchase, crm, hr, project, repair, is_vllm2odoo...) sont ignorés
# Hors périmètre (chiffrage) : feuilles de temps, employés, présences, congés et tracker de liens, à ne pas reprendre
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20
# => les identifiants externes base pointent sur les ids de la source et l'ancien default perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)
#******************************************************************************


# ** res_company **************************************************************
# Champs simples (nom, e-mail, téléphone...) ; devise retrouvée par son code (CHF)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Vérification des TVA par VIES : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont un n° de TVA
# => à réactiver après la bascule si besoin (Paramètres / Comptabilité)
cr_dst.execute("update res_company set vat_check_vies=false")
cnx_dst.commit()

# Adresse de la société dans les en-têtes, slogan (texte en v16, traduisible en v20) et pied de page (déjà traduisible)
cr_src.execute("select id,company_details,report_header,report_footer from res_company where id=1")
for row in cr_src.fetchall():
    for champ in ('company_details','report_header'):
        if row[champ]:
            cr_dst.execute("update res_company set "+champ+"=jsonb_build_object('en_US',%s::text,'fr_FR',%s::text) where id=%s",[row[champ],row[champ],row['id']])
    if row['report_footer']:
        cr_dst.execute("update res_company set report_footer=%s where id=%s",[json.dumps(row['report_footer']),row['id']])
cnx_dst.commit()

# URL utilisée par wkhtmltopdf pour charger les CSS et images des rapports : web.base.url n'est pas joignable depuis
# le serveur => PDF sans mise en page ; non écrasée si déjà présente (port ou hébergement différent)
cr_dst.execute("insert into ir_config_parameter (key,value) values ('report.url','http://localhost:8069') on conflict (key) do nothing")
cnx_dst.commit()

# Digest périodique (mail récapitulatif d'Odoo, hebdomadaire par défaut en v20) : désactivé
cr_dst.execute("update digest_digest set state='deactivated'")
cnx_dst.commit()

# Comptes bancaires de la société (2 comptes, Banque Cantonale Neuchâteloise) : res.bank supprimé en v20
# => nom et BIC de la banque sur le compte
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


# ** Unités de mesure *********************************************************
# Copiées avec les ids de la v16 (27 unités) : les tables qui les utilisent se copient ensuite sans conversion
# Chaque unité est rattachée à la référence de son ancienne catégorie ; identifiants externes uom.* repointés,
# unités v20 absentes de la v16 recréées (voir MigrationUnites)
# Longueurs : la référence est le mm en v16 (m = 1000 mm), nom français du mm = « m » (15 articles) : repris tels quels
# Unité maison « Unités » (id 27, catégorie « Unsorted/Imported Units ») : unité racine à part
MigrationUnites(db_src,db_dst)
#******************************************************************************


# ** Articles *****************************************************************
# Devises : EUR active en v16 (2 listes de prix en euros), inactive dans une base v20 suisse => activée
cr_src.execute("select name from res_currency where active")
devises = [row['name'] for row in cr_src.fetchall()]
cr_dst.execute("update res_currency set active=true where name = any(%s)",[devises])
cnx_dst.commit()

# Catégories (8) : nom texte en v16, traduisible en v20 ; comptes des catégories : à reprendre avec la comptabilité
MigrationTableJsonb(db_src,db_dst,'product_category')
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

# Étiquettes (2, sur aucun article) : couleur = n° de la palette d'Odoo (0 à 11) en v16, code hexadécimal en v20
# => code de la palette v20 ($o-colors de web/static/src/scss/primary_variables.scss) ; 0 (sans couleur) => vide
MigrationTable(db_src,db_dst,'product_tag',exclure=['color'])
MigrationTable(db_src,db_dst,'product_tag_product_template_rel')
palette = ['#a2a2a2','#ee2d2d','#dc8534','#e8bb1d','#5794dd','#9f628f','#db8865','#41a9a2','#304be0','#ee2f8a','#61c36e','#9872e6']
cr_src.execute("select id, color from product_tag where color between 1 and 11")
for row in cr_src.fetchall():
    cr_dst.execute("update product_tag set color=%s where id=%s",[palette[row['color']],row['id']])
cnx_dst.commit()

# Attributs (1) et valeurs (4) ; les attributs d'exemple de la v20 sont remplacés
MigrationTable(db_src,db_dst,'product_attribute',default={'active':True})
MigrationTable(db_src,db_dst,'product_attribute_value',default={'active':True})

# Modèles d'articles (741), pas de favoris en v16
# sale_delay (délai de livraison client, 28 articles) : nombre en v16, entier jsonb par société en v20 => repris ci-dessous
# expense_policy => reinvoice_policy (tous à « no »)
# Nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count (valeurs par défaut d'Odoo)
MigrationTable(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},exclure=['sale_delay'],
    default={'service_tracking':'no','base_unit_count':0})
cr_src.execute("select id,sale_delay from product_template where coalesce(sale_delay,0)<>0")
for row in cr_src.fetchall():
    cr_dst.execute("update product_template set sale_delay=jsonb_build_object('1',%s::int) where id=%s",[int(row['sale_delay']),row['id']])
# Type « Article stockable » (product, 564 articles) supprimé en v18 => consommable (consu) avec « Suivre l'inventaire » (is_storable)
cr_dst.execute("update product_template set is_storable=(type='product'), type=case when type='product' then 'consu' else type end")
# Suivi « none » supprimé en v20 (seulement lot et serial) => vide ; sinon « Wrong value for product.template.store_by: 'none' »
cr_dst.execute("update product_template set tracking=null where tracking='none'")
cnx_dst.commit()

# Variantes (741, une par modèle)
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})

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

# Coût des variantes (233 valeurs, 3 autres sur des variantes supprimées en v16) et responsable des articles (741) : propriétés en v16, champs jsonb par société en v20
# Propriétés de la société 2 (Delta Line, non reprise) ignorées
MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price',where="p.company_id=1")
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','responsible_id',where="p.company_id=1")

# Listes de prix (5 : 3 en CHF, 2 en EUR) et lignes (148, toutes actives) ; discount_policy supprimé en v20
# Odoo 20 recrée une liste « Par défaut » (société 1, séquence 10, _activate_or_create_pricelists) : après « Prix EUR » et
# « Prix CH » (séquence 1), elle ne change pas la liste par défaut des clients
MigrationTable(db_src,db_dst,'product_pricelist')
MigrationTable(db_src,db_dst,'product_pricelist_item')
# Liste de prix des clients (29 partenaires ; la 30e valeur est la valeur par défaut de la société 2) : propriété en v16, champ jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_product_pricelist','specific_property_product_pricelist',where="p.company_id=1")

# Prix fournisseurs (317) : unité d'achat de l'article (uom_po_id, supprimé en v20) => unité du prix fournisseur (obligatoire)
MigrationTable(db_src,db_dst,'product_supplierinfo',default={'uom_id':1,'discount':0})
cr_src.execute("select s.id,t.uom_po_id from product_supplierinfo s join product_template t on t.id=s.product_tmpl_id")
for row in cr_src.fetchall():
    cr_dst.execute("update product_supplierinfo set uom_id=%s where id=%s",[row['uom_po_id'],row['id']])
cnx_dst.commit()

# Ids des devises : ids de la v16 => ids de la v20
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
# A reprendre avec les pièces jointes : images des articles
#******************************************************************************
