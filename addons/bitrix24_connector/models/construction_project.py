import logging

from odoo import api, fields, models, _

from ..services.bitrix_api import BitrixAPI

_logger = logging.getLogger(__name__)

class EigrConstructionProjectBitrix(models.Model):

    _inherit = "eigr.construction.project"

    bitrix_deal_id = fields.Char(
        string="Bitrix24 ID de negociación",
        index=True,
        copy=False,
    )

    bitrix_contract_status = fields.Char(
        string="Estado de contrato (Bitrix24)",
        readonly=True,
    )

    bitrix_last_sync = fields.Datetime(
        string="Última sincronización Bitrix24",
        readonly=True,
    )

    def _get_bitrix_config(self):
        config = self.env["bitrix.config"].search(
            [("active", "=", True)], limit=1
        )
        if not config:
            raise Exception(
                "No existe una configuración activa de Bitrix24."
            )
        return config

    _CUSTOM_FIELD_LABELS = {
        "Avance financiero": "financial_progress",
        "Avance físico": "physical_progress",
        "Estado de contrato": "contract_status",
        "N° de contrato": "contract_number",
        "Monto contractual": "contract_amount",
        "Plazo contractual": "contract_term",
        "Fecha de término": "contract_end_date",
    }

    def _custom_field_value(self, code, project):
        if code == "financial_progress":
            return (project.financial_progress or 0.0) / 100.0
        if code == "physical_progress":
            return (project.progress_percent or 0.0) / 100.0
        if code == "contract_status":
            return self._contract_status_label().get(
                project.state, project.state
            )
        if code == "contract_number":
            return project.contract_number or ""
        if code == "contract_amount":
            return project.contract_amount or 0.0
        if code == "contract_term":
            return project.contract_term or ""
        if code == "contract_end_date":
            return (
                str(project.contract_end_date)
                if project.contract_end_date
                else ""
            )
        return None

    def _build_custom_fields(self, api, project):
        fields = api.get_deal_fields()
        payload = {}
        for field_code, field_meta in fields.items():
            label = (field_meta.get("formLabel") or "").strip()
            code = self._CUSTOM_FIELD_LABELS.get(label)
            if not code:
                continue
            value = self._custom_field_value(code, project)
            if value not in (None, "", False):
                payload[field_code] = value
        return payload

    def export_project(self):
        config = self._get_bitrix_config()
        api = BitrixAPI(config.webhook_url)
        for project in self:
            if not project.bitrix_deal_id:
                continue
            values = {
                "TITLE": project.name or "",
                "OPPORTUNITY": project.contract_amount or 0.0,
                "COMMENTS": _(
                    "Estado: %s | Avance: %s%% | Contrato: %s"
                ) % (
                    project.state,
                    project.progress_percent,
                    project.contract_number or "—",
                ),
            }
            values.update(self._build_custom_fields(api, project))
            api.update_deal(project.bitrix_deal_id, values)
            project.bitrix_last_sync = fields.Datetime.now()
        return True

    def _pull_bitrix_deals(self, config):
        api = BitrixAPI(config.webhook_url)
        deals = api.get_deals()
        imported = 0
        updated = 0
        projects_by_bitrix_id = {
            p.bitrix_deal_id: p
            for p in self.search([("bitrix_deal_id", "!=", False)])
        }
        for deal in deals:
            bitrix_id = str(deal.get("ID") or "")
            if not bitrix_id:
                continue
            values = {
                "name": deal.get("TITLE")
                or f"Proyecto Bitrix {bitrix_id}",
                "contract_amount": deal.get("OPPORTUNITY") or 0.0,
            }
            project = projects_by_bitrix_id.get(bitrix_id)
            if not project:
                project = self.create(dict(
                    values,
                    bitrix_deal_id=bitrix_id,
                    bitrix_last_sync=fields.Datetime.now(),
                ))
                projects_by_bitrix_id[bitrix_id] = project
                imported += 1
            else:
                changed = project.name != values["name"] or (
                    project.contract_amount != values["contract_amount"]
                )
                if changed:
                    project.write(dict(
                        values,
                        bitrix_last_sync=fields.Datetime.now(),
                    ))
                    updated += 1
        return imported, updated

    def sync_projects_with_bitrix(self, config):
        imported, updated = self._pull_bitrix_deals(config)
        exported = 0
        for project in self.search([("bitrix_deal_id", "!=", False)]):
            try:
                project.export_project()
                exported += 1
            except Exception as error:
                _logger.error(
                    "Bitrix24: fallo al exportar obra %s: %s",
                    project.code, error,
                )
        return {
            "imported": imported,
            "updated": updated,
            "exported": exported,
        }

    @api.model
    def _cron_sync_projects(self):
        config = self.env["bitrix.config"].search(
            [("active", "=", True)], limit=1
        )
        if not config:
            return
        try:
            self.env["res.partner"]._sync_companies(config)
            self.sync_projects_with_bitrix(config)
        except Exception as error:
            _logger.error(
                "Bitrix24: fallo en la sincronización de "
                "proyectos: %s", error,
            )