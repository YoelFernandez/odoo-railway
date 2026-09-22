from odoo import models, fields, _
from odoo.exceptions import UserError

from ..services.bitrix_api import BitrixAPI


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
        help="URL del webhook entrante de Bitrix24.",
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
    )

    last_sync = fields.Datetime(
        string="Última sincronización",
        readonly=True,
    )

    def action_test_connection(self):

        self.ensure_one()

        api = BitrixAPI(self.webhook_url)

        try:
            profile = api.test_connection()

        except Exception as error:
            raise UserError(
                _("Error conectando con Bitrix24: %s") % error
            )

        result = profile.get("result") or {}

        user_name = " ".join(
            part
            for part in [
                result.get("NAME"),
                result.get("LAST_NAME"),
            ]
            if part
        ) or result.get("ID", "")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bitrix24"),
                "message": _(
                    "Conexión correcta. Usuario: %s"
                ) % user_name,
                "type": "success",
                "sticky": False,
            },
        }

    def action_import_contacts(self):

        self.ensure_one()

        return self.env[
            "res.partner"
        ].import_bitrix_contacts()
