from odoo import models, fields


class BitrixConfig(models.Model):
    _name = "bitrix.config"
    _description = "Configuración Bitrix24"

    name = fields.Char(
        string="Nombre",
        required=True,
        default="Bitrix24",
    )

    webhook_url = fields.Char(
        string="Webhook URL",
        required=True,
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
    )

    last_sync = fields.Datetime(
        string="Última sincronización",
        readonly=True,
    )
