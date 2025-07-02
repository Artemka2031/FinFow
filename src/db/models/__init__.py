# -*- coding: utf-8 -*-
# FinFlow/src/db/models/__init__.py
from .articles import Article, create_article, get_article, get_articles, update_article, delete_article
from .contractors import Contractor, create_contractor, get_contractor, get_contractors, update_contractor, delete_contractor
from .creditors import Creditor, create_creditor, get_creditor, get_creditors, update_creditor, delete_creditor
from .employees import Employee, create_employee, get_employee, get_employees, update_employee, delete_employee
from .founders import Founder, create_founder, get_founder, get_founders, update_founder, delete_founder
from .materials import Material, create_material, get_material, get_materials, update_material, delete_material
from .projects import Project, create_project, get_project, get_projects, update_project, delete_project
from .wallets import Wallet, create_wallet, get_wallet, get_wallets, update_wallet, delete_wallet