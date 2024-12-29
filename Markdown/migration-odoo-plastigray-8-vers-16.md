Migration Odoo Plastigray 8 vers 16

# Terminé (à tester)

|                                                                         |          |             |
|-------------------------------------------------------------------------|----------|-------------|
| A tester                                                                | Fait le  | Commentaire |
| Ventes / BL manuel/Transport / BL Manuel                                |          |             |
| Ventes / BL manuel/Transport / Demande de transport                     |          |             |
| Gestion product_ul et product_packgaging                                | 26/10/22 |             |
|                                                                         |          |             |
| Revoir toutes les « ir.actions.server » (en commentaire pour le moment) |          |             |
| Revoir « \_defaults » partout car n'est plus utilisé avec Odoo 16       |          |             |
|                                                                         |          |             |
| Tarif commercial : Revoir le code python (create, write, copy\...)      |          |             |
| copy_other_database à revoir partout                                    |          |             |
|                                                                         |          |             |
|                                                                         |          |             |

# A Faire

<table>
<tbody>
<tr class="odd">
<td><p>Les champs "supplier" et « customer » n'existe plus dans
res_partner : </p>
<p>&lt;field name="mouliste_id"/&gt; &lt;!--
domain="[('supplier','=',True),('is_company','=',True)]" /&gt;
--&gt;</p>
<p>&lt;field name="client_id"/&gt; &lt;!--
domain="[('customer','=',True),('is_company','=',True)]" /&gt;
--&gt;</p></td>
<td></td>
</tr>
<tr class="even">
<td><p>Ligne à revoir : </p>
<p>is_mold.py/if company.is_base_principale</p></td>
<td></td>
</tr>
<tr class="odd">
<td><p>Action à revoir : </p>
<p>actualiser_chef_de_projet_action_server</p></td>
<td></td>
</tr>
<tr class="even">
<td>name_get et name_search dans product_product et
product_template</td>
<td></td>
</tr>
<tr class="odd">
<td>is_demande_achat_serie =&gt; pricelist_id<strong> =&gt; Il n'y a
plus de liste de prix pour les fournisseurs</strong></td>
<td></td>
</tr>
<tr class="even">
<td>is_demande_achat_fg =&gt; pricelist_id</td>
<td></td>
</tr>
<tr class="odd">
<td>is_demande_achat_invest =&gt; pricelist_id</td>
<td></td>
</tr>
<tr class="even">
<td>is_demande_achat_moule =&gt; pricelist_id</td>
<td></td>
</tr>
<tr class="odd">
<td>is_facture_pk <strong>=&gt; A revoir après avoir mis en place
stock_picking et sale_order</strong></td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td></td>
</tr>
<tr class="odd">
<td><p>Action à revoir car tous les champs sont affichés et problème
avec company_id :</p>
<p> if line.vsb==False and line.name:</p>
<p> print(line.name, line.name.name)</p>
<p> #setattr(obj, line.name.name, True)</p>
<p>J’ai ajouté un try pour éviter l’erreur sur company_id</p></td>
<td>28/09/22</td>
</tr>
<tr class="even">
<td><p>A finaliser : </p>
<p>product_view.xml</p></td>
<td></td>
</tr>
<tr class="odd">
<td><p>Problème avec les unités suite migration table uom.uom en
ajoutant un colis sur la fiche article</p>
<p> return self.env.ref('uom.product_uom_millimeter')</p>
<p> File "/opt/odoo16/odoo/api.py", line 591, in ref</p>
<p> raise ValueError('No record found for unique ID %s. It may have been
deleted.' % (xml_id))</p>
<p>ValueError: No record found for unique ID uom.product_uom_millimeter.
It may have been deleted.</p></td>
<td></td>
</tr>
<tr class="even">
<td><p>A revoir : </p>
<p>is_view_partner_bank_form</p>
<p>is_view_partner_bank_tree</p></td>
<td></td>
</tr>
<tr class="odd">
<td><p>is_bon_transfert</p>
<p>galia_um_ids</p></td>
<td></td>
</tr>
<tr class="even">
<td><p>res_partner_view : <strong>Encore plein de chose à
revoir</strong></p>
<p>is_database_origine_id à activer sur toutes les views dans
res_partner_view</p></td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td></td>
</tr>
<tr class="even">
<td><p>is_bon_transfert</p>
<p>La table product.ul pour gérer les colis n’existe plus</p>
<p> id | create_uid | create_date | name | weight | height | width |
length | write_date | write_uid | type </p>
<p>-----+------------+----------------------------+------------------------+--------+--------+-------+--------+----------------------------+-----------+--------</p>
<p> 3 | 1 | 2016-04-05 14:42:55.26323 | SAC | 0 | 0 | 0 | 0 | 2016-04-05
14:42:55.26323 | 1 | unit</p>
<p> 5 | 1 | 2016-04-05 14:51:59.104838 | CARTON | 0 | 0 | 0 | 0 |
2016-04-05 14:51:59.104838 | 1 | pack</p>
<p> 8 | 1 | 2016-05-30 08:58:57.820444 | BAC EFP642 E2 FENWICK | 2 | 200
| 400 | 600 | 2016-05-30 08:58:57.820444 | 1 | box</p>
<p> #uc_id = fields.Many2one('product.ul', 'UC' , compute='_compute',
readonly=True, store=True)</p>
<p> #um_id = fields.Many2one('product.ul', 'UM' , compute='_compute',
readonly=True, store=True)</p></td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td></td>
</tr>
<tr class="even">
<td><p>Liste à servir</p>
<p>2022-10-23 14:38:35,285 6227 WARNING pg-odoo16-1 odoo.fields: Field
is.liste.servir.line.uc_id with unknown comodel_name
'<strong>product.ul</strong>' </p>
<p>2022-10-23 14:38:35,286 6227 WARNING pg-odoo16-1 odoo.fields: Field
is.liste.servir.line.um_id with unknown comodel_name 'product.ul' </p>
<p>2022-10-23 14:38:35,286 6227 WARNING pg-odoo16-1 odoo.fields: Field
is.liste.servir.uc.uc_id with unknown comodel_name 'product.ul' </p>
<p>2022-10-23 14:38:35,286 6227 WARNING pg-odoo16-1 odoo.fields: Field
is.liste.servir.uc.um_id with unknown comodel_name 'product.ul' </p>
<p>2022-10-23 14:38:35,286 6227 WARNING pg-odoo16-1 odoo.fields: Field
is.liste.servir.um.um_id with unknown comodel_name 'product.ul' </p>
<p>Manque les séquences</p>
<p>Finaliser la vue (vues des tableaux à revoir)</p></td>
<td></td>
</tr>
<tr class="odd">
<td>is_consigne_journaliere TODO : Liens avec odoo0, dynacase et les
ordres de travaux =&gt; A revoir plus tard</td>
<td></td>
</tr>
<tr class="even">
<td>is_pointage : default name et write</td>
<td></td>
</tr>
<tr class="odd">
<td>is_deb : A revoir après la facturation client</td>
<td></td>
</tr>
<tr class="even">
<td>is_reach : A revoir après stock_picking</td>
<td></td>
</tr>
<tr class="odd">
<td>is_export_edi : à finaliser</td>
<td></td>
</tr>
<tr class="even">
<td>is_export_cegid : A finaliser</td>
<td></td>
</tr>
<tr class="odd">
<td>is_mini_delta_dore : A finaliser</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td></td>
</tr>
</tbody>
</table>

# Voir comment mettre le chatter en bas et non pas à droite pour pouvoir élargir la taille du formulaire                         {#voir-comment-mettre-le-chatter-en-bas-et-non-pas-à-droite-pour-pouvoir-élargir-la-taille-du-formulaire}

https://apps.odoo.com/apps/modules/16.0/od_chatter_position/

# Comparer les modules installés

odoo@bullseye:/media/sf_dev_odoo/migration-odoo\$ ./migration-odoo.py
compare_modules \| grep \"state_src=installed\" \| grep -v
state_dst=installed

\- account_accountant state_src=installed state_dst=uninstallable OK OK

**- account_cancel state_src=installed OK**

\- account_chart state_src=installed OK

\- account_voucher state_src=installed OK

**- auditlog state_src=installed OK**

\- auth_crypt state_src=installed OK

\- auth_ldap state_src=installed state_dst=uninstalled OK OK

\- base_action_rule state_src=installed OK

\- board state_src=installed state_dst=uninstalled OK OK

\- calendar state_src=installed state_dst=uninstalled OK OK

\- crm state_src=installed state_dst=uninstalled OK OK

\- decimal_precision state_src=installed OK

\- document state_src=installed OK

\- edi state_src=installed OK

\- email_template state_src=installed OK

\- fetchmail state_src=installed OK

\- knowledge state_src=installed OK

\- mass_editing state_src=installed OK

\- mrp_byproduct state_src=installed OK

\- mrp_operations state_src=installed OK

\- payment_transfer state_src=installed OK

\- procurement state_src=installed OK

\- qweb_usertime state_src=installed OK

\- report state_src=installed OK

\- sale_crm state_src=installed state_dst=uninstalled OK OK

\- share state_src=installed OK

\- wct_keyboard_shortcuts state_src=installed OK

\- web_calendar state_src=installed OK

\- web_diagram state_src=installed OK

\- web_export_view state_src=installed OK

\- web_gantt state_src=installed OK

\- web_graph state_src=installed OK

\- web_kanban state_src=installed OK

\- web_kanban_sparkline state_src=installed OK

\- web_list_view_sticky state_src=installed OK

\- web_m2x_options state_src=installed OK

\- web_tests state_src=installed OK

\- web_tree_color state_src=installed OK

\- web_tree_many2one_clickable state_src=installed OK

\- web_view_editor state_src=installed OK

\- web_widget_color state_src=installed OK

# Données dans la table source et table de destination inexistante

odoo@bullseye:/media/sf_dev_odoo/migration-odoo\$ ./migration-odoo.py
compare_tables \| grep -v \"is\_\" \| grep test3

ct/nb table nb_src nb_dst src dst test1 test2

6/1134 account_account_financial_report_type 15 2 test1 test2 test3

15/1134 account_account_type 16 10 test1 test2 test3

29/1134 account_analytic_journal 2 10 test1 test2 test3

64/1134 account_financial_report 8 14 test1 test2 test3

74/1134 account_fiscalyear 7 12 test1 test2 test3

85/1134 account_invoice 34834 50 test1 test2 test3

88/1134 account_invoice_line 127021 30 test1 test2 test3

89/1134 account_invoice_line_tax 128537 2 test1 test2 test3

92/1134 account_invoice_tax 36529 18 test1 test2 test3

100/1134 account_journal_cashbox_line 255 7 test1 test2 test3

103/1134 account_journal_period 254 11 test1 test2 test3

120/1134 account_move_reconcile 9 8 test1 test2 test3

139/1134 account_period 91 13 test1 test2 test3

172/1134 account_tax_code 67 13 test1 test2 test3

173/1134 account_tax_code_template 90 12 test1 test2 test3

202/1134 auditlog_http_request 385474 10 test1 test2 test3

203/1134 auditlog_http_session 10588 7 test1 test2 test3

204/1134 auditlog_log 255241 13 test1 test2 test3

205/1134 auditlog_log_line 1236468 19 test1 test2 test3

206/1134 auditlog_rule 15 15 test1 test2 test3

254/1134 calendar_alarm 7 10 test1 test2 test3

260/1134 calendar_event_type 5 6 test1 test2 test3

268/1134 crm_case_categ 10 8 test1 test2 test3

269/1134 crm_case_section 1 24 test1 test2 test3

270/1134 crm_case_stage 7 13 test1 test2 test3

281/1134 crm_payment_mode 4 7 test1 test2 test3

290/1134 crm_tracking_medium 5 7 test1 test2 test3

291/1134 crm_tracking_source 3 6 test1 test2 test3

299/1134 document_directory 9 17 test1 test2 test3

300/1134 document_directory_content 2 13 test1 test2 test3

301/1134 document_directory_content_type 1 9 test1 test2 test3

305/1134 email_template 14 29 test1 test2 test3

379/1134 ir_model_mass_object_rel 2 2 test1 test2 test3

391/1134 ir_sequence_type 57 7 test1 test2 test3

393/1134 ir_translation 16883 10 test1 test2 test3

399/1134 ir_values 7975 15 test1 test2 test3

728/1134 l10n_fr_line 130 9 test1 test2 test3

729/1134 l10n_fr_report 2 7 test1 test2 test3

753/1134 mail_group 1 15 test1 test2 test3

754/1134 mail_group_res_group_rel 1 2 test1 test2 test3

781/1134 mass_field_rel 10 2 test1 test2 test3

782/1134 mass_object 2 9 test1 test2 test3

802/1134 mrp_operations_operation_code 5 8 test1 test2 test3

803/1134 mrp_prevision 25931 27 test1 test2 test3

806/1134 mrp_product_produce 39 14 test1 test2 test3

807/1134 mrp_product_produce_line 194 10 test1 test2 test3

812/1134 mrp_production_product_line 232629 13 test1 test2 test3

817/1134 mrp_production_workcenter_line 78193 23 test1 test2 test3

820/1134 mrp_routing 2423 14 test1 test2 test3

839/1134 partner_database_rel 6384 2 test1 test2 test3

840/1134 payment_acquirer 1 19 test1 test2 test3

860/1134 pricelist_partnerinfo 1 9 test1 test2 test3

**865/1134 procurement_order 67870 29 test1 test2 test3**

869/1134 procurement_rule 6 24 test1 test2 test3

887/1134 product_price_history 9070 9 test1 test2 test3

889/1134 product_price_type 2 9 test1 test2 test3

892/1134 product_pricelist_type 2 7 test1 test2 test3

893/1134 product_pricelist_version 1885 11 test1 test2 test3

912/1134 product_ul 125 11 test1 test2 test3

913/1134 product_uom 111 13 test1 test2 test3

914/1134 product_uom_categ 6 6 test1 test2 test3

**926/1134 purchase_order_taxe 57206 2 test1 test2 test3**

950/1134 res_font 42 9 test1 test2 test3

962/1134 res_partner_bank_type 2 8 test1 test2 test3

963/1134 res_partner_bank_type_field 4 10 test1 test2 test3

968/1134 res_request_link 7 8 test1 test2 test3

988/1134 sale_member_rel 1 2 test1 test2 test3

**992/1134 sale_order_invoice_rel 15962 2 test1 test2 test3**

**999/1134 sale_order_tax 76331 2 test1 test2 test3**

1005/1134 section_stage_rel 7 2 test1 test2 test3

1033/1134 stock_incoterms 27 8 test1 test2 test3

1034/1134 stock_inventory 13797 16 test1 test2 test3

1039/1134 stock_inventory_line 70577 19 test1 test2 test3

1045/1134 stock_location_route 6 15 test1 test2 test3

1047/1134 stock_location_route_move 188914 2 test1 test2 test3

1055/1134 stock_move_operation_link 194512 9 test1 test2 test3

1059/1134 stock_pack_operation 145768 21 test1 test2 test3

1069/1134 stock_production_lot 87830 11 test1 test2 test3

1072/1134 stock_quant_move_rel 2566008 2 test1 test2 test3

1099/1134 stock_transfer_details 6 9 test1 test2 test3

1100/1134 stock_transfer_details_items 20 19 test1 test2 test3

1128/1134 wkf 8 8 test1 test2 test3

1129/1134 wkf_activity 66 16 test1 test2 test3

1130/1134 wkf_instance 223939 6 test1 test2 test3

1131/1134 wkf_transition 104 13 test1 test2 test3

1133/1134 wkf_witm_trans 9684 2 test1 test2 test3

1134/1134 wkf_workitem 235422 5 test1 test2 test3

test3 : nb_src\>0 and nb_dst==\'\' =\> Données dans la table source et
table de destination inexistante

# res_partner

odoo@bullseye:/media/sf_dev_odoo/migration-odoo\$ ./migration-odoo.py
compare_champs res_partner \| grep \"nb\>1\" \| grep -v \"is\_\" \| grep
-v ok_dst

\- credit_limit double precision ok_src 2 nb\>1

\- customer boolean ok_src 2 nb\>1

\- fax character varying ok_src 51 nb\>1

\- image bytea ok_src 144 nb\>1

\- image_medium bytea ok_src 144 nb\>1

\- image_small bytea ok_src 144 nb\>1

\- last_reconciliation_date timestamp without time zone ok_src 3 nb\>1

\- message_last_post timestamp without time zone ok_src 2 nb\>1

\- notify_email character varying ok_src 2 nb\>1

\- opt_out boolean ok_src 2 nb\>1

\- supplier boolean ok_src 3 nb\>1

\- use_parent_address boolean ok_src 3 nb\>1

\- vat_subjected boolean ok_src 3 nb\>1

# product_template

psycopg2.errors.InvalidTextRepresentation: ERREUR: syntaxe en entrée
invalide pour le type json

DETAIL: Le jeton « FICHE » n\'est pas valide.

CONTEXT: données JSON, ligne 1 : FICHE\...

COPY product_template, ligne 2, colonne name : « FICHE HYPRA 380V + N +
T 16A »

Le format jsonb n'est pas reconnu pour la migration

odoo@bullseye:/media/sf_dev_odoo/migration-odoo\$ ./migration-odoo.py
compare_champs product_template \| grep json

\- description text jsonb ok_src ok_dst 1

\- description_picking jsonb ok_dst 0

\- description_pickingin jsonb ok_dst 0

\- description_pickingout jsonb ok_dst 0

\- description_purchase text jsonb ok_src ok_dst 1

\- description_sale text jsonb ok_src ok_dst 1

\- name character varying jsonb ok_src ok_dst 5816 nb\>1

# Fonctions json dans postgresql

- https://www.postgresql.org/docs/9.3/functions-json.html
- https://www.postgresql.org/docs/13/functions-json.html

pg-odoo16-1=# select id, name from product_template;

id \| name

\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

1 \| {\"en_US\": \"toto et tutu\", \"fr_FR\": \"toto et tutu\"}

(1 ligne)

pg-odoo16-1=# select id, name-\>\>\'fr_FR\' from product_template;

id \| ?column?

\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\--

1 \| toto et tutu

(1 ligne)

# L\'utilisateur ne peut pas avoir plus d\'un type d\'utilisateur

pg-odoo16-1=# select id,name-\>\>\'fr_FR\' from ir_module_category where
name-\>\>\'en_US\'=\'User types\';

id \| ?column?

\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

67 \| Types d\'utilisateur

pg-odoo16-1=# select id,name-\>\>\'fr_FR\' from res_groups where
category_id=67;

id \| ?column?

\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

11 \| Public

10 \| Portail

1 \| Utilisateur interne

# product_packaging

Beaucoup de changements sur cette table à réintégrer dans odoo 16

pg-odoo8-1=# select id, rows, ul_qty, qty, product_tmpl_id, ul,
ul_container from product_packaging;

id \| rows \| ul_qty \| qty \| product_tmpl_id \| ul \| ul_container

\-\-\-\-\--+\-\-\-\-\--+\-\-\-\-\-\-\--+\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\--

2299 \| 3 \| 4 \| 70 \| 3277 \| 53 \| 9

1348 \| 5 \| 10 \| 1456 \| 2126 \| 47 \| 1

1415 \| 3 \| 8 \| 96 \| 2193 \| 47 \| 9

1343 \| 3 \| 4 \| 108 \| 2121 \| 54 \| 9

class product_packaging(osv.osv):

\_name = \"product.packaging\"

\_description = \"Packaging\"

\_rec_name = \'ean\'

\_order = \'sequence\'

\_columns = {

\'sequence\': fields.integer(\'Sequence\', help=\"Gives the sequence
order when displaying a list of packaging.\"),

\'name\' : fields.text(\'Description\'),

\'qty\' : fields.float(\'Quantity by Package\',

help=\"The total number of products you can put by pallet or box.\"),

\'ul\' : fields.many2one(\'product.ul\', \'Package Logistic Unit\',
required=True),

\'ul_qty\' : fields.integer(\'Package by layer\', help=\'The number of
packages by layer\'),

\'ul_container\': fields.many2one(\'product.ul\', \'Pallet Logistic
Unit\'),

\'rows\' : fields.integer(\'Number of Layers\', required=True,

help=\'The number of layers on a pallet or box\'),

\'product_tmpl_id\' : fields.many2one(\'product.template\', \'Product\',
select=1, ondelete=\'cascade\', required=True),

\'ean\' : fields.char(\'EAN\', size=14, help=\"The EAN code of the
package unit.\"),

\'code\' : fields.char(\'Code\', help=\"The code of the transport
unit.\"),

\'weight\': fields.float(\'Total Package Weight\',

help=\'The weight of a full package, pallet or box.\'),

}

# product_ul

Cette table n'existe plus =\> Il faut la re-créer, car elle est utilisée
par Plastigray

class product_ul(osv.osv):

\_name = \"product.ul\"

\_description = \"Logistic Unit\"

\_columns = {

\'name\' : fields.char(\'Name\', select=True, required=True,
translate=True),

\'type\' :
fields.selection(\[(\'unit\',\'Unit\'),(\'pack\',\'Pack\'),(\'box\',
\'Box\'), (\'pallet\', \'Pallet\')\], \'Type\', required=True),

\'height\': fields.float(\'Height\', help=\'The height of the
package\'),

\'width\': fields.float(\'Width\', help=\'The width of the package\'),

\'length\': fields.float(\'Length\', help=\'The length of the
package\'),

\'weight\': fields.float(\'Empty Package Weight\'),

}

# product_pricelist_version : Cette table n'existe plus dans Odoo 16 {#product_pricelist_version-cette-table-nexiste-plus-dans-odoo-16}

pg-odoo8-1=# select name, date_start, date_end, pricelist_id, active
from product_pricelist_version limit 5;

name \| date_start \| date_end \| pricelist_id \| active

\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\--

2017 \| 2017-01-01 \| 2017-12-31 \| 332 \| t

2016 \| \| 2016-12-31 \| 333 \| t

2016 \| \| 2016-12-31 \| 334 \| t

2017 \| 2017-01-01 \| 2017-12-31 \| 334 \| t

2016 \| \| 2016-12-31 \| 335 \| t

# Gestion des entrepôts emplacements et route

Les routes (stock.route) sont affectés à l'entrepôt (stock.warehouse)

![](Pictures/100002010000048B0000023B34234DEB4291BDAF.png){width="27.7cm"
height="13.598cm"}

Par défaut, il y a 2 routes affectés à l'entrepôt :

![](Pictures/1000020100000201000000D130A9A903F563CECE.png){width="10.368cm"
height="4.225cm"}

![](Pictures/100002010000043A000001E36CBFE571C5E78E08.png){width="23.664cm"
height="10.564cm"}

L'entrepôt contient aussi les liens vers les emplacements

![](Pictures/100002010000050C0000022F00317A6A002D8B2D.png){width="27.7cm"
height="11.984cm"}

La route est affecté à la catégorie de l'article

Par défaut la catégorie de l'article n'a aucune route. Il doit donc y
avoir un autre endroit pour définir la route à utiliser lors de
livraisons ou réceptions

![](Pictures/10000201000003DA000001700A78CDA8DBAFB446.png){width="26.084cm"
height="9.735cm"}

Avant migration :

![](Pictures/10000201000003E600000176AFBD765AFCBD3D74.png){width="20.731cm"
height="7.768cm"}

Après migration :

![](Pictures/10000201000003CC0000014BF8D45CEBA9C2EF76.png){width="20.687cm"
height="7.045cm"}

## stock.picking.type {#stock.picking.type}

Ne semble pas définir les routes à utiliser par défaut :

![](Pictures/1000020100000445000001AB510DB25E896CB460.png){width="27.7cm"
height="10.82cm"}

Cette case permet d'afficher l'onglet « Opérations détaillées » dans
stock.picking. Sinon, il faut compléter les lots sur chaque ligne de
l'onglet en réception

![](Pictures/100002010000010A0000004198E3302980BF075E.png){width="7.036cm"
height="1.72cm"}

## stock.picking {#stock.picking}

Les lots appariassent dans l'onglet « Opérations » seulement pour le
suivi de type « N° de série » dans la fiche article :

![](Pictures/1000020100000394000000ABBD515A737E8969CE.png){width="24.232cm"
height="4.523cm"}

# mrp_production

\'**move_lines**\': fields.one2many(\'stock.move\',
\'**raw_material_production_id**\', \'Products to Consume\',

domain=\[(\'state\', \'not in\', (\'done\', \'cancel\'))\],
readonly=True, states={\'draft\': \[(\'readonly\', False)\]}),

\'**move_lines2**\': fields.one2many(\'stock.move\',
\'**raw_material_production_id**\', \'Consumed Products\',

domain=\[(\'state\', \'in\', (\'done\', \'cancel\'))\], readonly=True),

\'**move_created_ids**\': fields.one2many(\'stock.move\',
\'**production_id**\', \'Products to Produce\',

domain=\[(\'state\', \'not in\', (\'done\', \'cancel\'))\],
readonly=True),

\'**move_created_ids2**\': fields.one2many(\'stock.move\',
\'**production_id**\', \'Produced Products\',

domain=\[(\'state\', \'in\', (\'done\', \'cancel\'))\], readonly=True),

Fonction à revoir pour ne pas supprimer les produits finis en cas de
modif de la quantité

@api.depends(\'product_id\', \'bom_id\', \'product_qty\',
\'product_uom_id\', \'location_dest_id\', \'date_planned_finished\')

def \_compute_move_finished_ids(self):

for production in self:

if production.state != \'draft\':

updated_values = {}

if production.date_planned_finished:

updated_values\[\'date\'\] = production.date_planned_finished

if production.date_deadline:

updated_values\[\'date_deadline\'\] = production.date_deadline

if \'date\' in updated_values or \'date_deadline\' in updated_values:

production.move_finished_ids = \[

Command.update(m.id, updated_values) for m in
production.move_finished_ids

\]

continue

production.move_finished_ids = \[Command.clear()\]

if production.product_id:

production.\_create_update_move_finished()

else:

production.move_finished_ids = \[

Command.delete(move.id) for move in production.move_finished_ids if
move.bom_line_id

\]

# workorder

odoo@bullseye:/media/sf_dev_odoo/migration-odoo\$ ./migration-odoo.py
compare_tables \| grep workorder

823/1122 **mrp_workorder** 0 28 test1 test2

824/1122 mrp_workorder_dependencies_rel 0 2 test1 test2

odoo@bullseye:/media/sf_dev_odoo/migration-odoo\$ ./migration-odoo.py
compare_tables \| grep workcenter

805/1122 **mrp_production_workcenter_line** 80343 23 test1 test2 test3

809/1122 mrp_routing_workcenter 4922 4925 15 20 test2 test4

810/1122 mrp_routing_workcenter_dependencies_rel 0 2 test1 test2

811/1122 mrp_routing_workcenter_product_template_attribute\_ 0 2 test1
test2

814/1122 mrp_workcenter 84 84 24 28 test4

## mrp_production_form_view

\<field name=\"workcenter_lines\" options=\"{\'reload_on_button\':
true}\"\>

\<tree string=\"Production Work Centers\"\>

\<field name=\"sequence\"/\>

\<field name=\"name\"/\>

\<field name=\"workcenter_id\"/\>

\<field name=\"cycle\"/\>

\<field name=\"hour\" widget=\"float_time\"/\>

\</tree\>

\</field\>

workcenter_lines =\> mrp.production.workcenter.line

# Facturation fournisseur / Facturation des réceptions {#facturation-fournisseur-facturation-des-réceptions}

Lien entre le mouvement de stock et la ligne de commande avec le champ
« purchase_line_id » :

pg-odoo16-1=# select id, picking_id,
date,product_id,product_qty,**purchase_line_id** from **stock_move**
where purchase_line_id is not null limit 5;

id \| picking_id \| date \| product_id \| product_qty \|
purchase_line_id

\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

3973618 \| 107466 \| 2023-07-12 13:12:51 \| 7368 \| 1.0 \| 71089

3973619 \| 107466 \| 2023-07-12 13:12:51 \| 7368 \| 1.0 \| 71090

3973620 \| 107466 \| 2023-07-12 13:12:51 \| 7368 \| 1.0 \| 71091

3973621 \| 107466 \| 2023-07-12 13:12:51 \| 7368 \| 1.0 \| 71092

3973622 \| 107466 \| 2023-07-12 13:12:51 \| 7368 \| 1.0 \| 71093

Cela permet de savoir ce qui a été livré mais pas ce qui a été facturé

Il y a un lien entre les lignes des factures et les lignes des commandes
mais pas de lien avec les réceptions :

pg-odoo16-1=# select
id,move_id,product_id,quantity,price_unit,**purchase_line_id** from
**account_move_line** where purchase_line_id is not null;

id \| move_id \| product_id \| quantity \| price_unit \|
purchase_line_id

\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

222749 \| 41259 \| 3045 \| 3.000000 \| 10.0000 \| 71096

Au moment de la facturation, il faut donc mémoriser le mouvement de
stock facturé

Pour BSA, j'ai ajouté un lien entre le mouvement de stock et la ligne de
la facture

class stock_move(models.Model):

\_inherit = \"stock.move\"

is_account_move_line_id = fields.Many2one(\"account.move.line\", \"Ligne
de facture\" )

Pour les achats :

def action_create_invoice(self):

\"\"\"Permet de faire le lien entre la ligne de facture et la ligne de
réception ce qui n\'existe pas par défaut\"\"\"

res = super().action_create_invoice()

if res and \"domain\" in res:

ids=\[\]

domain = res\[\"domain\"\]\[0\]

if domain\[0\] == \"id\":

ids = domain\[2\]

else:

if \"res_id\" in res:

if res\[\"res_id\"\]\>0:

ids=\[res\[\"res_id\"\]\]

invoices = self.env\[\"account.move\"\].search(\[(\"id\",\"in\", ids)\])

for invoice in invoices:

for line in invoice.line_ids:

if line.purchase_line_id:

for move in line.purchase_line_id.move_ids:

if not move.is_account_move_line_id and move.state==\"done\":

move.is_account_move_line_id = line.id

line.is_stock_move_id = move.id

return res

Et pour les ventes :

def \_create_invoices(self, grouped=False, final=False, date=None):

invoices = super().\_create_invoices(grouped=grouped, final=final,
date=date)

for invoice in invoices:

for line in invoice.line_ids:

for sale_line in line.sale_line_ids:

for move in sale_line.move_ids:

if not move.is_account_move_line_id and move.state==\"done\":

move.is_account_move_line_id = line.id

line.is_stock_move_id = move.id

return invoices

Dans ce cas, il faut désactiver la création standard d'une facture pour
bien sélectionner les mouvements à facturer et faire le lien entre le
mouvement de stock et la ligne de la facture

Sinon, la modification d'une quantité, ou une annulation de facture ne
sera pas prise correctement en compte

=\> Masquer le création de factures depuis une commande d'achat

=\> Revoir le programme de création des factures fournisseurs pour faire
ce lien

# Comptabilité / Journaux (account.journal) {#comptabilité-journaux-account.journal}

![](Pictures/100002010000036B000000FA2F353BB52AD96D28.png){width="17.888cm"
height="5.11cm"}

\#\*\* init sequence_id dans account_journal
\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

SQL=\"UPDATE account_journal j set sequence_id=(SELECT id from
ir_sequence s where s.name=j.name limit 1)\"

cr_dst.execute(SQL)

cnx_dst.commit()

\#\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

\#TODO A Revoir (Lignes commentés =\> Ne fonctionne pas avec
odoo-formation)

SQL=\"\"\"

update account_journal set type=\'general\' where code=\'BNK1\';

update account_journal set default_account_id=(select id from
account_account where code=\'512102\') where code=\'BNK2\';

update account_journal set suspense_account_id=(select id from
account_account where code=\'512112\') where code=\'BNK2\';

update account_journal set payment_debit_account_id=(select id from
account_account where code=\'512122\') where code=\'BNK2\';

update account_journal set payment_credit_account_id=(select id from
account_account where code=\'512132\') where code=\'BNK2\';

update account_journal set default_account_id=(select id from
account_account where code=\'512103\') where code=\'BNK3\';

update account_journal set suspense_account_id=(select id from
account_account where code=\'512113\') where code=\'BNK3\';

update account_journal set payment_debit_account_id=(select id from
account_account where code=\'512123\') where code=\'BNK3\';

update account_journal set payment_credit_account_id=(select id from
account_account where code=\'512133\') where code=\'BNK3\';

delete from account_journal_outbound_payment_method_rel;

delete from account_journal_inbound_payment_method_rel ;

insert into account_journal_inbound_payment_method_rel values(8,1);

\-- insert into account_journal_inbound_payment_method_rel values(10,1);

insert into account_journal_outbound_payment_method_rel values(8,2);

\-- insert into account_journal_outbound_payment_method_rel
values(10,2);

\"\"\"

cr_dst.execute(SQL)

cnx_dst.commit()  

# Mouvements de stocks

Problème avec la récupération des lignes des mouvements de stocks (64
lignes)

![](Pictures/100002010000036C0000024CAF26CD8A0A8ACA8C.png){width="23.174cm"
height="15.556cm"}

Dans Odoo 8, il y a bien les 64 lignes, mais la quantité est toujours la
même et il faudrait afficher dans Odoo 16 l'emplacement d'origine

![](Pictures/10000201000003950000026FD2D6857A07860CA3.png){width="18.117cm"
height="12.308cm"}
