from odoo import models, fields, _
from odoo.exceptions import UserError

from ..services.bitrix_api import BitrixAPI


class ResPartner(models.Model):

    _inherit = "res.partner"

    bitrix_contact_id = fields.Char(
        string="Bitrix24 Contact ID",
        index=True,
        copy=False,
    )

    bitrix_last_sync = fields.Datetime(
        string="Última sincronización Bitrix24",
        readonly=True,
    )

    _bitrix_contact_id_unique = models.Constraint(
        "unique(bitrix_contact_id)",
        "El ID del contacto de Bitrix24 debe ser único.",
    )

    def _get_bitrix_config(self):

        config = self.env[
            "bitrix.config"
        ].search(
            [
                ("active", "=", True)
            ],
            limit=1,
        )

        if not config:
            raise UserError(
                _(
                    "No existe una configuración activa "
                    "de Bitrix24."
                )
            )

        return config

    def import_bitrix_contacts(self):

        config = self._get_bitrix_config()

        api = BitrixAPI(
            config.webhook_url
        )

        try:
            result = api.get_contacts()

        except Exception as error:
            raise UserError(
                _("Error conectando con Bitrix24: %s")
                % error
            )

        contacts = result.get(
            "result",
            []
        )

        imported = 0
        updated = 0

        for contact in contacts:

            bitrix_id = str(
                contact.get("ID")
            )

            if not bitrix_id:
                continue

            partner = self.search(
                [
                    (
                        "bitrix_contact_id",
                        "=",
                        bitrix_id,
                    )
                ],
                limit=1,
            )

            first_name = (
                contact.get("NAME")
                or ""
            )

            second_name = (
                contact.get("SECOND_NAME")
                or ""
            )

            last_name = (
                contact.get("LAST_NAME")
                or ""
            )

            name = " ".join(
                part
                for part in [
                    first_name,
                    second_name,
                    last_name,
                ]
                if part
            )

            if not name:
                name = (
                    f"Bitrix Contact "
                    f"{bitrix_id}"
                )

            phone = self._get_multifield_value(
                contact.get("PHONE")
            )

            email = self._get_multifield_value(
                contact.get("EMAIL")
            )

            values = {
                "name": name,
                "phone": phone,
                "email": email,
                "bitrix_contact_id": bitrix_id,
                "bitrix_last_sync": fields.Datetime.now(),
            }

            if partner:

                partner.write(values)

                updated += 1

            else:

                self.create(values)

                imported += 1

        config.write({
            "last_sync": fields.Datetime.now()
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bitrix24"),
                "message": _(
                    "Importación completada. "
                    "Nuevos: %s | Actualizados: %s"
                ) % (
                    imported,
                    updated,
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @staticmethod
    def _get_multifield_value(values):

        if not values:
            return False

        if isinstance(values, list):

            if not values:
                return False

            first = values[0]

            if isinstance(first, dict):
                return first.get("VALUE")

            return first

        return values
