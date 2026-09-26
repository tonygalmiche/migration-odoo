# -*- coding: utf-8 -*-
# pyright: reportUndefinedVariable=false
# Correctif des utilisateurs techniques décalés sur Coheliance (Odoo 18)
# Voir Documentation/migration-odoo/correctif-utilisateurs-techniques-coheliance18.md
#
# À lancer dans odoo shell (toujours sur une copie avant la production) :
#   odoo-bin shell -c /etc/odoo/odoo18.conf -d odoo18 --no-http < correctif-utilisateurs-techniques-coheliance18.py
#
# Par défaut, rien n'est enregistré (odoo shell annule tout à la fin).
# Passer COMMIT à True seulement quand l'essai a donné le résultat attendu.
COMMIT = False

from odoo import Command

Users = env['res.users'].with_context(active_test=False, no_reset_password=True)
IMD = env['ir.model.data']


def xmlid(name, model):
    rec = IMD.search([('module', '=', 'base'), ('name', '=', name), ('model', '=', model)])
    assert len(rec) == 1, "identifiant externe base.%s introuvable" % name
    return rec


def etat(titre):
    print("\n=== %s" % titre)
    for name in ('user_root', 'user_admin', 'default_user', 'public_user', 'template_portal_user_id'):
        u = Users.browse(xmlid(name, 'res.users').res_id)
        print("%-24s -> %s %-26s active=%s share=%s partenaire=%s groupes=%s" % (
            name, u.id, u.login, u.active, u.share, u.partner_id.id, len(u.groups_id)))
    for name in ('public_partner', 'default_user_res_partner', 'template_portal_user_id_res_partner'):
        p = env['res.partner'].with_context(active_test=False).browse(xmlid(name, 'res.partner').res_id).exists()
        print("%-36s -> %s %s" % (name, p.id, p.name))
    print("paramètre base.template_portal_user_id = %s" % env['ir.config_parameter'].get_param('base.template_portal_user_id'))
    print("paramètre auth_signup.invitation_scope = %s" % env['ir.config_parameter'].get_param('auth_signup.invitation_scope'))
    for uid in (3, 4):
        u = Users.browse(uid)
        print("groupes de %s %s : %s" % (u.id, u.login, ', '.join(sorted(u.groups_id.get_external_id().values()))))


etat("Avant")

# 0. Vérifier qu'on est bien dans la situation constatée le 26/09/2026
public = Users.browse(3)
portal = Users.browse(4)
assert xmlid('default_user', 'res.users').res_id == 3
assert xmlid('public_user', 'res.users').res_id == 4
assert xmlid('template_portal_user_id', 'res.users').res_id == 5
assert public.login == 'public' and portal.login == 'portaltemplate'
assert not Users.search([('login', '=', 'default')]), "un utilisateur 'default' existe déjà"
group_public = env.ref('base.group_public')
group_portal = env.ref('base.group_portal')
Members = env['discuss.channel.member'].sudo()
membres_avant = Members.search([]).ids

# 1. Créer le modèle des nouveaux utilisateurs internes, avec les groupes par défaut actuels (ceux de l'uid 3)
# sans active_test=False : sinon Odoo refuse d'archiver le partenaire du nouvel utilisateur inactif
default = env['res.users'].with_context(no_reset_password=True).create({
    'name': 'Default User Template',
    'login': 'default',
    'active': False,
    'groups_id': [Command.set(public.groups_id.ids)],
})

# 2. Remettre les identifiants externes sur les bons utilisateurs et partenaires
xmlid('default_user', 'res.users').res_id = default.id
xmlid('default_user_res_partner', 'res.partner').res_id = default.partner_id.id
xmlid('public_user', 'res.users').res_id = public.id
xmlid('template_portal_user_id', 'res.users').res_id = portal.id
xmlid('template_portal_user_id_res_partner', 'res.partner').res_id = portal.partner_id.id
env['ir.config_parameter'].set_param('base.template_portal_user_id', str(portal.id))
env.flush_all()               # écrire les nouveaux res_id en base...
env.registry.clear_cache()    # ...puis oublier les anciens (sinon default_user reste l'uid 3)

# Si default_user pointait encore sur l'uid 3, changer ses groupes les propagerait à tous les utilisateurs internes
assert env.ref('base.default_user') == default
assert env.ref('base.public_user') == public
assert env.ref('base.template_portal_user_id') == portal

# 3. Visiteurs anonymes : uniquement group_public. Modèle portail : uniquement group_portal.
public.groups_id = [Command.set([group_public.id])]
portal.groups_id = [Command.set([group_portal.id])]
env.flush_all()

# Créer un utilisateur avec group_user abonne tous les utilisateurs internes au canal Discuss « general »
# (lié à group_user). Ce canal n'est pas utilisé chez Coheliance (0 membre) : on retire ces abonnements,
# sinon un -u base plante en recréant le membre « admin » (discuss_channel_member_partner_unique).
nouveaux_membres = Members.search([('id', 'not in', membres_avant)])
print("\nMembres de canaux créés par effet de bord puis supprimés : %s (%s)" % (
    len(nouveaux_membres), ', '.join(nouveaux_membres.mapped(lambda m: '%s/%s' % (m.channel_id.name, m.partner_id.name)))))
nouveaux_membres.unlink()
env.flush_all()

etat("Après")

# 4. Contrôles
assert public.groups_id == group_public and public.share
assert portal.groups_id == group_portal and portal.share
assert not default.active and not default.share
assert xmlid('template_portal_user_id', 'res.users').res_id == portal.id
assert Users.browse(5).active, "Florence doit rester active"
assert sorted(Members.search([]).ids) == sorted(membres_avant), "les membres des canaux Discuss ont changé"

if COMMIT:
    env.cr.commit()
    print("\n*** ENREGISTRÉ. Redémarrer Odoo. ***")
else:
    env.cr.rollback()
    print("\n*** ESSAI : rien n'a été enregistré (COMMIT = False). ***")
