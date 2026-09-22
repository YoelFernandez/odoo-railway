import logging

from odoo import models, fields, api

from ..services.bitrix_api import BitrixAPI

_logger = logging.getLogger(__name__)

class CrmLead(models.Model):

    _inherit = "crm.lead"

    bitrix_deal_id = fields.Char(
        string="Bitrix24 ID de negociación",
        index=True,
        copy=False,
    )

    bitrix_company_id = fields.Char(
        string="Bitrix24 ID de empresa",
        index=True,
    )

    def _odoo_to_bitrix(self):

        self.ensure_one()

        values = {
            "TITLE": self.name or "",
            "OPPORTUNITY": self.planned_revenue
            if self.planned_revenue else False,
        }

        if self.bitrix_company_id:

            values["COMPANY_ID"] = self.bitrix_company_id

        return values

    def push_bitrix(self):

        api = BitrixAPI(
            self.env["bitrix.config"]
            .search([("active", "=", True)], limit=1)
            .webhook_url
            or ""
        )

        for lead in self:

            if not lead.bitrix_deal_id:

                new_id = api.call(
                    "crm.deal.add",
                    {
                        "fields": lead._odoo_to_bitrix(),
                    },
                ).get("result")

                if new_id:
                    lead.bitrix_deal_id = str(new_id)

            else:

                api.call(
                    "crm.deal.update",
                    {
                        "id": lead.bitrix_deal_id,
                        "fields": lead._odoo_to_bitrix(),
                    },
                )

    @api.model
    def _cron_push_deals(self):

        for lead in self.search([
            ("bitrix_deal_id", "=", False),
            ("type", "=", "opportunity"),
        ]):

            try:

                lead.push_bitrix()

            except Exception as error:

                _logger.error(
                    "Bitrix24: fallo al exportar lead %s: %s",
                    lead.id,
                    error,
                )
