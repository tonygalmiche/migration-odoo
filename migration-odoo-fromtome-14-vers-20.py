#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Fromtome : Odoo 14 (is_fromtome14) => Odoo 20 (is_fromtome20)
# Documentation : Documentation/migration-odoo/migration-is_fromtome14-vers-is_fromtome20.md (§ 6 et § 7)
# Fait (étapes 1 à 10 de la reprise) : contacts, utilisateurs, société, paramétrage is_*, unités, articles, stock, ventes,
# achats, comptabilité (paramètres, pièces, lettrages, paiements, exports compta), tables du module, serveurs de mail,
# prompts IA
# A faire ensuite : pièces jointes, chatter
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit


#** Paramètres ****************************************************************
db_src = "fromtome14"
db_dst = "fromtome20"
# Reprise relancée à partir de l'étape N après un arrêt : option --depart N (7 : comptabilité, 8 : tables du module,
# 9 : serveurs de mail, 10 : prompts IA)
# => fromtome20 gardée telle quelle (pas recréée), étapes précédentes sautées ; chaque étape vide et recopie ses tables,
# elle peut être relancée si les étapes précédentes sont allées au bout. Si la base est abîmée : sans l'option, reprise
# complète à partir de fromtome20-vierge
depart = int(sys.argv[sys.argv.index('--depart')+1]) if '--depart' in sys.argv else 1
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# fromtome20-vierge : base v20 avec is_fromtome20 installé, sans données (étape 14 de la reprise, créée par Tony)
# Ni fromtome20 ni fromtome20-vierge ne doivent être ouvertes (Odoo arrêté ou sur une autre base) : sinon DROP / CREATE
# refusés (« is being accessed by other users »)
if depart==1:
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

# Titre de chaque partie de la reprise avec son heure de début (suivi du lancement)
def Etape(titre):
    print("\n** %s : %s **"%(datetime.now().strftime('%H:%M:%S'),titre))


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


# ** Étapes 1 à 6 : sautées si départ à l'étape 7 ou plus (base gardée telle quelle) ****
if depart<=6:


    # ** res_partner et res_users *************************************************
    Etape("Étape 1 : partenaires, utilisateurs, groupes")
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
    Etape("Étape 1 : société, mise en page, comptes bancaires")
    # Champs simples (nom, e-mail, téléphone, champs is_* : coefficients et ports des prix, GLN, configuration IA...)
    # Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
    cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
    exclure = [row['column_name'] for row in cr_dst.fetchall()]
    MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

    # Vérification des TVA par VIES : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont un n° de TVA
    # => à réactiver après la bascule si besoin (Paramètres / Comptabilité)
    cr_dst.execute("update res_company set vat_check_vies=false")
    cnx_dst.commit()

    # Précisions décimales de la v14 (4 décimales : quantités, poids, prix, volume ; 2 par défaut en v20 : prix et
    # quantités arrondis à la saisie, 11,32 kg au lieu de 11,3180 sur les BL) ; « Product Unit of Measure » renommé
    # « Product Unit » en v20
    cr_src.execute("select name, digits from decimal_precision")
    for row in cr_src.fetchall():
        nom = {'Product Unit of Measure': 'Product Unit'}.get(row['name'],row['name'])
        cr_dst.execute("update decimal_precision set digits=%s where name=%s",[row['digits'],nom])
    cnx_dst.commit()

    # Pied de page des documents : texte traduit en v14 (ir_translation, avec retours à la ligne ; la valeur de base est
    # une ancienne version) => html par langue en v20 (sinon pied de page calculé : téléphone, e-mail, TVA, SIRET)
    cr_src.execute("select lang, value from ir_translation where name='res.company,report_footer' and res_id=1 and value<>''")
    pied = {row['lang']: '<p>%s</p>'%'<br>'.join(html.escape(ligne) for ligne in row['value'].splitlines()) for row in cr_src.fetchall()}
    if pied:
        cr_dst.execute("update res_company set report_footer=%s where id=1",[json.dumps(pied)])
        cnx_dst.commit()

    # Mise en page des documents : agencement « Boxed » en v14 (web.external_layout_boxed), supprimé en v20 => « Light »
    # (web.external_layout_standard, en-tête et pied de page Fromtome : report/external_layout_boxed.xml du module) avec
    # les tableaux « Encadré » (report_tables_id boxed : classes o_report_layout_boxed de l'ancien Boxed) ;
    # format A4 avec les marges de la v14 (haut 40, bas 32, gauche et droite 7, en-tête 35 mm). Format en noupdate :
    # non écrasé par un -u base
    cr_dst.execute("select res_id from ir_model_data where module='web' and name='external_layout_standard'")
    layout_id = cr_dst.fetchone()['res_id']
    cr_dst.execute("select res_id from ir_model_data where module='base' and name='paperformat_euro'")
    paperformat_id = cr_dst.fetchone()['res_id']
    cr_dst.execute("update res_company set external_report_layout_id=%s, report_tables_id='boxed', paperformat_id=%s where id=1",[layout_id,paperformat_id])
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
    Etape("Étape 2 : tables de paramétrage is_*")
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
    Etape("Étape 3 : unités de mesure")
    # Copiées avec les ids de la v14 (23 unités) ; noms traduits par ir_translation ; voir MigrationUnites
    MigrationUnites(db_src,db_dst)
    #******************************************************************************


    # ** Articles (étape 3) *******************************************************
    Etape("Étape 3 : articles, listes de prix, prix fournisseurs")
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
    Etape("Étape 4 : équipes commerciales")
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
    Etape("Étape 4 : conditions de paiement")
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
    Etape("Étape 5 : configuration du stock")
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
    Etape("Étape 5 : lots, colis, quants")
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
    Etape("Étape 6 : ventes")
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
    Etape("Étape 6 : achats")
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
    Etape("Étape 6 : transferts, mouvements, rebuts, références de stock")
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
    Etape("Étape 6 : séquences")
    # Commandes de vente (CC) et d'achat (CF) ; les transferts ont la séquence de leur type d'opération, recalée par
    # MigrationConfigurationStock
    for code in ['sale.order','purchase.order']:
        cr_src.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
        seq_src = cr_src.fetchone()
        cr_dst.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
        seq_dst = cr_dst.fetchone()
        MigrationIrSequence(db_src,db_dst,id_src=seq_src['id'],id_dst=seq_dst['id'])
    #******************************************************************************


# ** Étape 7 : sautée si départ à l'étape 8 ou plus ***************************
if depart<=7:


    # ** Paramètres comptables (étape 7) ******************************************
    Etape("Étape 7 : paramètres comptables (comptes, taxes, positions fiscales, journaux)")
    # Plan comptable (1 495 comptes, dont un compte client 411xxx par client), groupes de taxes (12), taxes (55), positions
    # fiscales (9) et journaux (12) de la v14 copiés avec leurs ids à la place de ceux du plan fr_comp de la v20 (chargé
    # dans fromtome20-vierge le 26/10/2026 : 677 comptes, 48 taxes, 10 positions, 7 journaux) ; colonnes ajoutées par la
    # v20 (codes Factur-X des taxes...) reprises de l'enregistrement v20 équivalent (même identifiant externe) ; références
    # de la v20 recalées. Même méthode que pour ACPL 14→20
    # Voir Documentation/migration-odoo/migration-vers-odoo20.md § 3.7 et § 5.4

    # Lignes v20 et correspondance par identifiant externe, avant la copie
    avant, corr = {}, {}
    for table,suffixes in [('account_account',[]),('account_tax_group',[]),('account_tax',['_TTC','_ttc']),('account_fiscal_position',[])]:
        avant[table], corr[table] = LireAvantCopie(db_src,db_dst,table,suffixes)
    # Taxes utilisées sans identifiant de même nom en v20 : taxes à 0 % de vente et taxes intracommunautaires d'achat
    # séparées en biens et services en v20 (codes Factur-X différents) => « biens » (fromages, accord de Tony)
    # « TVA 0% autres opérations non imposables (achat) » (13 utilisations) : sans identifiant en v14, copiée telle quelle
    taxes_renommees = {
        '1_tva_0'            : '1_tva_sale_good_0',         # vente, 1 utilisation => E, VATEX-EU-F
        '1_tva_export_0'     : '1_tva_sale_good_export_0',  # vente, 1 630 utilisations => G, VATEX-EU-G
        '1_tva_intra_0'      : '1_tva_sale_good_intra_0',   # vente, 4 705 utilisations => K, VATEX-EU-IC
        '1_tva_intra_normale': '1_tva_intra_normale_biens', # achat 20 %, 78 utilisations
        '1_tva_intra_reduite': '1_tva_intra_reduite_biens', # achat 5,5 %, 736 utilisations
    }
    cr_src.execute("select name,res_id from ir_model_data where model='account.tax' and name = any(%s)",[list(taxes_renommees)])
    taxes_src = {row['name']:row['res_id'] for row in cr_src.fetchall()}
    cr_dst.execute("select name,res_id from ir_model_data where model='account.tax' and name = any(%s)",[list(taxes_renommees.values())])
    taxes_dst = {row['name']:row['res_id'] for row in cr_dst.fetchall()}
    for nom_src,nom_dst in taxes_renommees.items():
        if nom_src in taxes_src and nom_dst in taxes_dst:
            corr['account_tax'][taxes_src[nom_src]] = taxes_dst[nom_dst]
        else:
            print("Taxe %s => %s : identifiant absent (plan comptable pas chargé dans fromtome20-vierge ?)"%(nom_src,nom_dst))
    avant['account_journal'], _ = LireAvantCopie(db_src,db_dst,'account_journal')
    # Journaux : pas d'identifiant externe en v14 => correspondance par code (FAC, OD, EXCH, CABA, BNK1, STJ), sinon par type
    # s'il n'y en a qu'un (achats : AC en v14, FACTURE en v20)
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

    # Groupes de taxes (société obligatoire en v20) et taxes : price_include => price_include_override (vide = réglage de la société)
    # country_id : nouvelle colonne obligatoire en v20 => France (pays de la société)
    # Comptes de TVA à payer / à recevoir des groupes (propriétés en v14) : supprimés en v20
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
    # Taxes par défaut des comptes (7)
    MigrationTable(db_src,db_dst,'account_account_tax_default_rel')

    # Positions fiscales (9) ; correspondances de taxes (104) : en v20, portées par la taxe de remplacement ; correspondances
    # de comptes (12) : mêmes colonnes
    MigrationTableJsonb(db_src,db_dst,'account_fiscal_position')
    CompleterColonnesV20(db_src,db_dst,'account_fiscal_position',avant['account_fiscal_position'],corr['account_fiscal_position'],inverse)
    cr_src.execute("select position_id,tax_src_id,tax_dest_id from account_fiscal_position_tax where tax_dest_id is not null")
    for row in cr_src.fetchall():
        cr_dst.execute("insert into account_fiscal_position_account_tax_rel (account_tax_id,account_fiscal_position_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['position_id']])
        cr_dst.execute("insert into account_tax_alternatives (dest_tax_id,src_tax_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['tax_src_id']])
    cr_dst.execute("update account_tax t set is_domestic = not exists (select 1 from account_fiscal_position_account_tax_rel r where r.account_tax_id=t.id)")
    cr_dst.execute("update account_fiscal_position set is_domestic=false")
    cnx_dst.commit()
    MigrationTable(db_src,db_dst,'account_fiscal_position_account')

    # Journaux (12) : alias de messagerie non repris
    # Journaux 10 (Banque Populaire) et 12 (Caisse d'Epargne) avec le même code VR-BP en v14 (index unique par société en
    # v20, actif même sans les déclencheurs) : journal 12 => VR-CE à l'insertion (accord de Tony du 26/10/2026) ; ses 31
    # pièces gardent leur numéro VR-BP/...
    MigrationTableJsonb(db_src,db_dst,'account_journal',default={'invoice_reference_type':'invoice','invoice_reference_model':'odoo'},
        remplacer={12: {'code': 'VR-CE'}})
    cr_dst.execute("update account_journal set alias_id=null")
    cnx_dst.commit()
    CompleterColonnesV20(db_src,db_dst,'account_journal',avant['account_journal'],corr['account_journal'],inverse)
    # Modes de paiement des journaux : table account_payment_method_line créée en v15 => modes manuels (entrée et sortie,
    # seuls utilisés en v14) de chaque journal de banque et de caisse, avec les comptes d'attente des encaissements et des
    # décaissements du journal v14 (payment_debit_account_id, payment_credit_account_id, supprimés en v20)
    cr_dst.execute("delete from account_payment_method_line")
    cr_src.execute("select id,payment_debit_account_id,payment_credit_account_id from account_journal where type in ('bank','cash') order by id")
    lignes = []
    for row in cr_src.fetchall():
        lignes.append((row['id'],'inbound' ,row['payment_debit_account_id']))
        lignes.append((row['id'],'outbound',row['payment_credit_account_id']))
    execute_values(cr_dst,"""
        insert into account_payment_method_line (journal_id,payment_method_id,payment_account_id,name,sequence,create_uid,create_date,write_uid,write_date)
        select s.journal_id, m.id, s.payment_account_id, 'Manual Payment', 10, 1, now(), 1, now()
        from (values %s) as s(journal_id,payment_type,payment_account_id)
        join account_payment_method m on m.code='manual' and m.payment_type=s.payment_type
    """,lignes)
    cnx_dst.commit()

    # Étiquettes des comptes et des lignes de taxes (déclaration de TVA) : étiquettes de la v20, liens convertis par nom
    MigrationEtiquettesTaxes(db_src,db_dst,[
        ('account_account_account_tag','account_account_id'),
        ('account_account_tag_account_tax_repartition_line_rel','account_tax_repartition_line_id'),
    ])

    # Devises (EUR = 1 en v14)
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
    valeurs = {}
    for colonne,ref in GetClesEtrangeres(cr_dst,'res_company').items():
        if ref in tables_compta:
            valeurs[colonne] = societe_src[colonne] if colonne in colonnes_src else inverse.get(ref,{}).get(societe_dst[colonne])
    # En une seule requête, sans contrôle des clés : la société pointe encore sur des comptes v20 supprimés
    UpdateSansControle('res_company',"update res_company set "+','.join(c+'=%s' for c in valeurs)+" where id=1",list(valeurs.values()))
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
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_receivable_id')         # 1 046 comptes clients 411xxx
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_payable_id')            # 556
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_position_id')           # 1 907
    MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_income_id')        # 11
    MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_expense_id')       # 30
    MigrationIrPropertyJsonb(db_src,db_dst,'product.category','property_account_income_categ_id')  # 18
    MigrationIrPropertyJsonb(db_src,db_dst,'product.category','property_account_expense_categ_id') # 21

    # Taxes des articles (6 263 / 6 266, ids des taxes de la v14)
    for table in ['product_taxes_rel','product_supplier_taxes_rel']:
        MigrationTable(db_src,db_dst,table)

    # Identifiants externes des modèles repris (journaux : par la correspondance par code, sans identifiant en v14)
    # Taxes renommées (voir taxes_renommees) : identifiants « biens » de la v20 gardés sur les taxes v14 correspondantes
    MigrationIrModelData(db_src,db_dst,['account.account','account.tax.group','account.tax','account.fiscal.position'],correspondances={
        'account.tax': {nom_dst:taxes_src[nom_src] for nom_src,nom_dst in taxes_renommees.items() if nom_src in taxes_src},
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


    # ** Pièces comptables (étape 7) **********************************************
    Etape("Étape 7 : pièces, lettrages, paiements")
    # 45 817 pièces (17 402 factures, 1 517 avoirs, 11 274 factures et 615 avoirs fournisseurs, 15 009 écritures dont les
    # pièces des paiements), 393 701 lignes
    # v14 : aucune pièce « à vérifier », aucune comptabilisation automatique, aucun hachage, aucun litige (blocked), pas de
    # relevés bancaires ni d'analytique ; FF10544 (point 3 du § 5 de la doc) déjà corrigée dans la v14
    # to_check => review_state ; auto_post (booléen, toujours faux) => 'no' ; tax_cash_basis_move_id =>
    # tax_cash_basis_origin_move_id (56 pièces de TVA sur encaissements) ; payment_id => origin_payment_id (après la copie
    # des paiements) ; document_tax_mode : obligatoire pour les factures et avoirs, vide pour les autres pièces
    # 29 avoirs (22/12/2025 au 09/01/2026) numérotés comme des factures en v14 (FC13072 à FC13100, numéro déjà porté par une
    # facture du journal VE ; les autres avoirs sont en RFAC/...) : doublons refusés par l'index unique (name, journal_id)
    # de la v20 => suffixe -AV (FC13072-AV...), accord de Tony du 26/10/2026 ; même suffixe sur move_name des lignes
    avoir_en_double = """
        t.move_type in ('out_refund','in_refund') and exists (
            select 1 from account_move f
            where f.journal_id=t.journal_id and f.name=t.name and f.id<>t.id and f.move_type not in ('out_refund','in_refund')
        )
    """
    MigrationTable(db_src,db_dst,'account_move',rename={'tax_cash_basis_move_id':'tax_cash_basis_origin_move_id'},exclure=['auto_post'],
        expressions={
            'name'             : "case when "+avoir_en_double+" then t.name||'-AV' else t.name end",
            'auto_post'        : "'no'",
            'review_state'     : "'no_review'",
            # contrôlé dès le COPY (contrainte account_move_check_document_tax_mode_set) ; hors taxe, réglage de la société,
            # recalé juste après
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

    # Lettrages (29 953 partiels, 27 176 complets)
    MigrationTable(db_src,db_dst,'account_full_reconcile')
    MigrationTable(db_src,db_dst,'account_partial_reconcile')

    # Paiements (11 494) : nom, date, journal, société et mémo portés par la pièce en v14 ; mode de paiement du journal
    # (créé plus haut) et son compte d'attente
    MigrationTable(db_src,db_dst,'account_payment',default={'company_id':1,'date':'2000-01-01','journal_id':1,'state':'draft'})
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

    # Liens avec les commandes : lignes de commande de vente => lignes de factures (202 334), commandes d'achat => factures (14 002)
    MigrationTable(db_src,db_dst,'sale_order_line_invoice_rel')
    MigrationTable(db_src,db_dst,'account_move_purchase_order_rel')

    # Devises : EUR = 1 en v14
    MigrationDevisesParCode(db_src,db_dst,['account_move','account_move_line','account_payment','account_partial_reconcile','account_full_reconcile'])
    # Export compta (231 exports, 153 923 lignes) : référencé par les pièces et les paiements (is_export_compta_id), repris
    # avec eux (sinon « Enregistrement manquant : is.export.compta » sur les factures) ; fichiers des exports
    # (is_export_compta_attachment_rel) : pièces jointes reprises avec leurs ids (étape 11)
    for table in ['is_export_compta','is_export_compta_ligne','is_export_compta_attachment_rel']:
        MigrationTable(db_src,db_dst,table)
    # Pièce jointe principale des pièces (message_main_attachment_id) : copiée telle quelle, les pièces jointes sont reprises
    # avec leurs ids (étape 11)
    #******************************************************************************


# ** Tables du module (étape 8) ***********************************************
if depart<=8:
    Etape("Étape 8 : employés")
    # 76 employés (16 actifs) : suivi du temps (is_suivi_temps.employe_id, 69 employés) et transferts
    # (stock_picking.is_employe_id, 1 817) ; départements, postes, catégories et une hr_version par employé
    MigrationHrEmployee(db_src,db_dst)

    Etape("Étape 8 : traductions allemandes")
    # Les reprises de tables traduisibles ne prennent que le français : noms d'articles (2 308, listings en allemand),
    # listes de prix, unités (Pc), conditions de paiement, routes, types d'opérations. Données standard d'Odoo
    # (groupes, sous-types, incoterms...) : traduites par la v20
    MigrationTraductions(db_src,db_dst,[
        ('product.template'    ,'name','product_template'),
        ('product.pricelist'   ,'name','product_pricelist'),
        ('uom.uom'             ,'name','uom_uom'),
        ('account.payment.term','name','account_payment_term'),
        ('account.payment.term','note','account_payment_term'),
        ('stock.location.route','name','stock_route'),
        ('stock.picking.type'  ,'name','stock_picking_type'),
    ],['de_DE'])

    Etape("Étape 8 : étiquettes des partenaires")
    # 42 étiquettes, 1 338 partenaires étiquetés ; catégories de l'analyse de la facturation (568 143 liens)
    MigrationTableJsonb(db_src,db_dst,'res_partner_category')
    MigrationTable(db_src,db_dst,'res_partner_res_partner_category_rel')

    Etape("Étape 8 : tables du module (promos, calcul des besoins, FNC, analyses, scans, étiquettes, relances...)")
    # Mêmes colonnes en v14 et en v20, copiées avec les ids de la source (liens vers les articles, commandes, transferts,
    # factures déjà repris avec leurs ids), sauf colonnes supprimées en v20 : message_main_attachment_id (analyses de marge
    # par lot, calcul des besoins, FNC, promos client), is_scan_picking.inventory_id (stock.inventory supprimé)
    # Tables calculées (analyses, marges, calcul des besoins) reprises aussi (§ 6 de la doc : tout reprendre)
    # Vues SQL (is_account_invoice_line, is_sale_order_line, is_stock_move_line, is_stock_production_lot_contrat) : recréées
    # par le module ; assistants (is_search_general, *_update) : non repris
    # Ailleurs : prompts IA (is_prompt_ia, étape 10), pièces jointes des activités (mail_activity_is_attachment_ids_rel,
    # étape 12)
    for table in [
        'is_promo_client',                                      # Promos client (3) et leurs lignes (661)
        'is_promo_client_ligne',
        'is_promo_fournisseur',                                 # Promos fournisseur (569), lignes (8 134), articles (28)
        'is_promo_fournisseur_ligne',
        'is_promo_fournisseur_product_rel',
        'is_calcul_des_besoins',                                # Calculs des besoins (297), lignes (106 753), liens avec les
        'is_calcul_des_besoins_ligne',                          # lignes de vente (208 076) et d'achat (27 519)
        'is_calcul_des_besoins_ligne_sale_order_line_rel',
        'is_calcul_des_besoins_ligne_purchase_order_line_rel',
        'is_commande_fromtome',                                 # Commandes Fromtome (192) et lignes (48 312)
        'is_commande_fromtome_ligne',
        'is_commande_transporteur',                             # Commandes transporteur (vide)
        'is_preparation_transfert_entrepot',                    # Préparations de transfert entre entrepôts (8, 4 724 lignes)
        'is_preparation_transfert_entrepot_ligne',
        'is_suivi_commande_hebdo',                              # Suivi hebdomadaire des commandes (158, 18 909 lignes)
        'is_suivi_commande_hebdo_ligne',
        'is_fnc',                                               # Fiches de non-conformité (251)
        'is_suivi_temps',                                       # Suivi du temps (1 469)
        'is_relance_facture',                                   # Relances de factures (253, 4 113 lignes)
        'is_relance_facture_ligne',
        'is_listing_prix_client',                               # Listings de prix client (560, 160 185 articles)
        'is_listing_prix_client_product_rel',
        'is_imprimer_etiquette_gs1',                            # Étiquettes GS1 imprimées (49 452)
        'is_scan_picking',                                      # Scans des transferts (32 200), lignes (807 000), articles
        'is_scan_picking_line',                                 # (321 427)
        'is_scan_picking_product',
        'is_analyse_facturation',                               # Analyse de la facturation (289 315, catégories : 568 143)
        'is_analyse_facturation_res_partner_category_rel',
        'is_analyse_marge_lot',                                 # Analyses de marge par lot (3, 73 416 lignes)
        'is_analyse_marge_lot_ligne',
        'is_marge_brute_article',                               # Marge brute par article (6 676) et audits (183)
        'is_audit_marge_brute',
        'is_analyse_rupture',                                   # Analyses des ruptures (2, lignes vides)
        'is_analyse_rupture_ligne',
        'is_import_le_cellier',                                 # Import Le Cellier (1) et son fichier (pièce jointe, étape 11)
        'is_import_le_cellier_attachment_rel',
        'res_company_is_import_excel_ids_rel',                  # Fichier Excel importé de la société (pièce jointe, étape 11)
        'is_modele_commande_product_rel',                       # Vides en v14
        'is_pricelist_product_tmpl_rel',
        'is_purchase_order_livraison_client_rel',
    ]:
        # Rebut des analyses (662 et 750 lignes) : stock_scrap en v14, stock_move en v20 (rebuts de l'étape 6) => mouvement
        # du rebut (stock_scrap.move_id)
        expressions = {}
        if table in ('is_analyse_facturation','is_analyse_marge_lot_ligne'):
            expressions = {'scrap_id': "(select s.move_id from stock_scrap s where s.id=t.scrap_id)"}
        MigrationTable(db_src,db_dst,table,expressions=expressions)
    #******************************************************************************


# ** Serveurs de mail (étape 9) ***********************************************
if depart<=9:
    Etape("Étape 9 : serveurs de mail")
    # smtp_by_user (v14) => standard v20 : utilisateur du serveur (user_id) => owner_user_id (unique, un serveur par
    # utilisateur en v14 aussi), adresse d'envoi (smtp_user) => from_filter ; 16 serveurs, mots de passe compris
    # Archivés sur la base de test (aucun mail réel envoyé) : le nettoyage quotidien d'Odoo (autovacuum) supprime les
    # serveurs personnels archivés, recréés à chaque reprise. À la bascule : option --serveurs-actifs (actifs comme en v14)
    actif = "t.active" if '--serveurs-actifs' in sys.argv else "false"
    MigrationTable(db_src,db_dst,'ir_mail_server',expressions={
        'owner_user_id'      : "t.user_id",
        'from_filter'        : "lower(t.smtp_user)",
        'smtp_authentication': "'login'",
        'active'             : actif,
    })
    #******************************************************************************


# ** Prompts IA (étape 10) ****************************************************
if depart<=10:
    Etape("Étape 10 : prompts IA")
    # Configuration IA de la société (is_vllm_*) : reprise à l'étape 1 ; is_llm2odoo installé dans fromtome20-vierge
    # 23 prompts des fiches articles : modèle (ir_model) et champ (ir_model_fields) aux ids différents en v20 =>
    # retrouvés par leur nom après la copie
    MigrationTable(db_src,db_dst,'is_prompt_ia')
    cr_src.execute("""
        select p.id, m.model, f.model champ_modele, f.name champ
        from is_prompt_ia p left join ir_model m on m.id=p.modele_id left join ir_model_fields f on f.id=p.field_id
    """)
    for row in cr_src.fetchall():
        cr_dst.execute("""
            update is_prompt_ia set
                modele_id=(select id from ir_model where model=%s),
                field_id=(select id from ir_model_fields where model=%s and name=%s)
            where id=%s
        """,[row['model'],row['champ_modele'],row['champ'],row['id']])
    cnx_dst.commit()
    #******************************************************************************
