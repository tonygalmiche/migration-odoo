#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de France Filets : Odoo 15 (is_france_filets15) => Odoo 20 (is_france_filets20)
# Documentation : Documentation/migration-odoo/migration-is_france_filets15-vers-is_france_filets20.md (étape 9)
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "france-filets15"
db_dst = "france-filets20"
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# france-filets20-vierge : base v20 avec is_france_filets20 installé, sans données (à créer par Tony)
# db_vierge = db_dst+'-vierge'
# SQL='DROP DATABASE "'+db_dst+'";CREATE DATABASE "'+db_dst+'" WITH TEMPLATE "'+db_vierge+'"'
# cde="""echo '"""+SQL+"""' | psql postgres"""
# lines=os.popen(cde).readlines()
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** 9.b Contacts, utilisateurs, société **************************************
#******************************************************************************


# ** 9.c Employés *************************************************************
#******************************************************************************


# ** 9.d Articles et paramètres de vente et de comptabilité *******************
#******************************************************************************


# ** 9.e Ventes ***************************************************************
#******************************************************************************


# ** 9.f Tables métier is_* ***************************************************
#******************************************************************************


# ** 9.g Comptabilité *********************************************************
#******************************************************************************


# ** 9.h Séquences, filtres, valeurs par défaut *******************************
#******************************************************************************


# ** 9.i Chatter **************************************************************
#******************************************************************************


# ** 9.j Pièces jointes (données seulement, fichiers à l'étape 11) ************
#******************************************************************************
