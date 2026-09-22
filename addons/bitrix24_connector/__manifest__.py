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
    ],

    "data": [
    "security/ir.model.access.csv",
    "views/bitrix_config_views.xml",
    "views/res_partner_views.xml",
],

    "external_dependencies": {
        "python": [
            "requests",
        ],
    },

    "installable": True,
    "application": True,
}
