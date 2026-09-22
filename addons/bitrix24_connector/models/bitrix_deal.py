import logging

from odoo import models, fields, api, _

from odoo.exceptions import UserError

from ..services.bitrix_api import BitrixAPI

_logger = logging.getLogger(__name__)

class BitrixDeal(models.Model):
    _name = "bitrix.deal"
    _description = "Negocio Bitrix24"
    _order = "date_modify desc"

    name = fields.Char(string="Título", required=True)

    bitrix_deal_id = fields.Char(
        string="Bitrix24 Deal ID",
        index=True,
        copy=False,
    )

    stage_id = fields.Char(string="Fase (Stage ID)")
    category_id = fields.Char(string="Categoría (Category ID)")
    opportunity = fields.Float(string="Importe")

    partner_id = fields.Many2one("res.partner", string="Contacto")
    company_id = fields.Many2one("res.partner", string="Empresa")

    date_modify = fields.Datetime(string="Última modificación")
    bitrix_last_sync = fields.Datetime(
        string="Última sincronización", readonly=True
    )

    _bitrix_deal_id_unique = models.Constraint(
        "unique(bitrix_deal_id)",
        "El ID del negocio de Bitrix24 debe ser único.",
    )

    def _get_bitrix_config(self):
        config = self.env["bitrix.config"].search(
            [("active", "=", True)], limit=1
        )
        if not config:
            raise UserError(
                _("No existe una configuración activa de Bitrix24.")
            )
        return config

    def _find_partner(self, bitrix_entity, bitrix_id):
        if not bitrix_id:
            return False
        return self.env["res.partner"].search(
            [(bitrix_entity, "=", bitrix_id)], limit=1
        )

    @api.model
    def _deal_to_odoo_values(self, deal):
        contact_id = deal.get("CONTACT_ID") or deal.get("CONTACT_IDS", [])
        if isinstance(contact_id, list):
            contact_id = contact_id[0] if contact_id else False

        company_id = deal.get("COMPANY_ID") or deal.get("COMPANY_IDS", [])
        if isinstance(company_id, list):
            company_id = company_id[0] if company_id else False

        return {
            "name": deal.get("TITLE") or "Bitrix Deal",
            "stage_id": deal.get("STAGE_ID"),
            "category_id": deal.get("CATEGORY_ID"),
            "opportunity": deal.get("OPPORTUNITY") or 0.0,
            "partner_id": self._find_partner(
                "bitrix_contact_id", contact_id
            ).id or False,
            "company_id": self._find_partner(
                "bitrix_company_id", company_id
            ).id or False,
            "date_modify": self.env["res.partner"]._parse_bitrix_date(
                deal.get("DATE_MODIFY")
            ),
        }

    def sync_deals_with_bitrix(self, api, quiet=True):
        imported = 0
        updated = 0
        exported = 0

        try:
            deals = api.get_deals()
        except Exception as error:
            if quiet:
                _logger.error("Bitrix24: fallo obteniendo deals: %s", error)
                return imported, updated, exported
            raise

        deals_by_id = {
            deal.get("ID"): deal
            for deal in deals
            if deal.get("ID")
        }

        for deal_id, deal in deals_by_id.items():
            values = self._deal_to_odoo_values(deal)
            existing = self.search(
                [("bitrix_deal_id", "=", deal_id)], limit=1
            )

            if not existing:
                self.create(dict(
                    values,
                    bitrix_deal_id=deal_id,
                    bitrix_last_sync=fields.Datetime.now(),
                ))
                imported += 1
                continue

            current = {
                "name": existing.name or "",
                "stage_id": existing.stage_id or False,
                "category_id": existing.category_id or False,
                "opportunity": existing.opportunity or 0.0,
                "partner_id": existing.partner_id.id or False,
                "company_id": existing.company_id.id or False,
            }

            incoming = {
                "name": values.get("name") or "",
                "stage_id": values.get("stage_id") or False,
                "category_id": values.get("category_id") or False,
                "opportunity": values.get("opportunity") or 0.0,
                "partner_id": values.get("partner_id") or False,
                "company_id": values.get("company_id") or False,
            }

            if current == incoming:
                continue

            existing.write(dict(
                values,
                bitrix_last_sync=fields.Datetime.now(),
            ))
            updated += 1

        if not api:
            config = self._get_bitrix_config()
            api = BitrixAPI(config.webhook_url)

        unexported_deals = self.search([
            ("bitrix_deal_id", "=", False)
        ])

        for deal in unexported_deals:
            payload = {
                "TITLE": deal.name or "",
                "OPPORTUNITY": deal.opportunity or 0,
            }
            if deal.stage_id:
                payload["STAGE_ID"] = deal.stage_id
            if deal.partner_id and deal.partner_id.bitrix_contact_id:
                payload["CONTACT_ID"] = int(
                    deal.partner_id.bitrix_contact_id
                )
            if deal.company_id and deal.company_id.bitrix_company_id:
                payload["COMPANY_ID"] = int(
                    deal.company_id.bitrix_company_id
                )
            new_id = api.create_deal(payload)
            if new_id:
                deal.bitrix_deal_id = str(new_id)
                deal.bitrix_last_sync = fields.Datetime.now()
                exported += 1

        return imported, updated, exported
