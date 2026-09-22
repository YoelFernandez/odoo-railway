{
    "name": "Bitrix24 Connector",
    "version": "19.0.1.0.0",
    "category": "CRM",
    "summary": "Integración directa Odoo 19 con Bitrix24",
    "author": "Custom",
    "license": "LGPL-3",

    "depends": [
        "base",
        "contacts",
        "crm",
        "eigr_construction_management",
    ],

    "data": [
    "security/ir.model.access.csv",
    "data/bitrix_cron.xml",
    "data/bitrix_crm_lead_cron.xml",
    "data/bitrix_deal_cron.xml",
    "views/bitrix_config_views.xml",
    "views/bitrix_sync_log_views.xml",
    "views/crm_lead_views.xml",
    "views/res_partner_views.xml",
    "views/construction_project_views.xml",
],

    "external_dependencies": {
        "python": [
            "requests",
        ],
    },

    "installable": True,
    "application": True,
}
