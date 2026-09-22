import logging
from datetime import datetime, timezone

from odoo import models, fields, _
from odoo.exceptions import UserError

from ..services.bitrix_api import BitrixAPI

_logger = logging.getLogger(__name__)


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

    bitrix_company_id = fields.Char(
        string="Bitrix24 ID de empresa",
        index=True,
        copy=False,
    )

    synced_company_ids = fields.Many2many(
        "res.partner",
        relation="bitrix_partner_company_rel",
        column1="contact_id",
        column2="company_id",
        string="Empresas sincronizadas con Bitrix24",
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

    @staticmethod
    def _parse_bitrix_date(value):

        if not value:
            return False

        try:

            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

        except ValueError:

            return False

        if parsed.tzinfo is not None:

            parsed = parsed.astimezone(
                timezone.utc
            ).replace(tzinfo=None)

        return parsed

    @staticmethod
    def _split_name(name):

        parts = [
            part for part in str(name or "").split()
        ]

        if not parts:
            return "", ""

        if len(parts) == 1:
            return parts[0], ""

        return " ".join(parts[:-1]), parts[-1]

    @staticmethod
    def _bitrix_to_odoo_values(contact):

        bitrix_id = str(contact.get("ID") or "")

        first_name = contact.get("NAME") or ""
        second_name = contact.get("SECOND_NAME") or ""
        last_name = contact.get("LAST_NAME") or ""

        name = " ".join(
            part
            for part in [
                first_name,
                second_name,
                last_name,
            ]
            if part
        ).strip()

        if not name:
            name = f"Bitrix Contact {bitrix_id}"

        country = self.env["res.country"].search(
            [("code", "=", contact.get("ADDRESS_COUNTRY"))],
            limit=1,
        )

        return {
            "name": name,
            "phone": ResPartner._get_multifield_value(
                contact.get("PHONE")
            ) or False,
            "email": ResPartner._get_multifield_value(
                contact.get("EMAIL")
            ) or False,
            "function": contact.get("POST") or False,
            "street": contact.get("ADDRESS") or False,
            "city": contact.get("ADDRESS_CITY") or False,
            "zip": contact.get("ADDRESS_POSTAL_CODE")
            or False,
            "country_id": country.id
            if country else False,
        }

    @staticmethod
    def _odoo_to_sync_values(partner):

        first_name, last_name = ResPartner._split_name(
            partner.name
        )

        return {
            "first_name": first_name,
            "last_name": last_name,
            "phone": partner.phone or False,
            "email": partner.email or False,
            "function": partner.function or False,
            "street": partner.street or False,
            "city": partner.city or False,
            "zip": partner.zip or False,
            "country_code": partner.country_id.code
            or False,
        }

    @staticmethod
    def _odoo_values_to_bitrix(values):

        payload = {
            "NAME": values.get("first_name") or "",
        }

        if values.get("last_name"):

            payload["LAST_NAME"] = values["last_name"]

        if values.get("phone"):

            payload["PHONE"] = [
                {
                    "VALUE": values["phone"],
                    "VALUE_TYPE": "WORK",
                }
            ]

        if values.get("email"):

            payload["EMAIL"] = [
                {
                    "VALUE": values["email"],
                    "VALUE_TYPE": "WORK",
                }
            ]

        if values.get("function"):

            payload["POST"] = values["function"]

        if values.get("street"):

            payload["ADDRESS"] = values["street"]

        if values.get("city"):

            payload["ADDRESS_CITY"] = values["city"]

        if values.get("zip"):

            payload["ADDRESS_POSTAL_CODE"] = values["zip"]

        if values.get("country_code"):

            payload["ADDRESS_COUNTRY"] = values["country_code"]

        return payload

    def _log_failure(self, log, label, error):

        _logger.warning("Bitrix24: fallo en %s: %s", label, error)

        log.write({
            "failed": log.failed + 1,
            "error_log": (log.error_log or "")
            + f"{label}: {error}\n",
        })

    def _sync_companies(self, config):

        api = BitrixAPI(config.webhook_url)

        since = config.last_sync

        companies = api.get_companies(since=since)

        companies_by_odoo_id = {}

        partners_by_bitrix_company = {
            partner.bitrix_company_id: partner
            for partner in self.search([
                ("bitrix_company_id", "!=", False)
            ])
        }

        for company in companies:

            bitrix_company_id = str(company.get("ID") or "")

            if not bitrix_company_id:
                continue

            company_partner = partners_by_bitrix_company.get(
                bitrix_company_id
            )

            if not company_partner:

                company_partner = self.create({
                    "name": company.get("TITLE")
                    or f"Bitrix Company {bitrix_company_id}",
                    "is_company": True,
                    "bitrix_company_id": bitrix_company_id,
                })

                partners_by_bitrix_company[
                    bitrix_company_id
                ] = company_partner

            companies_by_odoo_id[
                company_partner.id
            ] = company

        for partner in self.search([
            ("type", "=", "contact"),
            ("parent_id", "!=", False),
            ("parent_id.bitrix_company_id", "!=", False),
        ]):

            partner.synced_company_ids = [(
                4, partner.parent_id.id
            )]

        return companies_by_odoo_id

    def _pull_bitrix_contacts(self, contacts_by_id, log):

        imported = 0
        updated = 0
        touched_ids = set()

        if not contacts_by_id:
            return imported, updated, touched_ids

        partners_by_bitrix_id = {
            partner.bitrix_contact_id: partner
            for partner in self.search([
                (
                    "bitrix_contact_id",
                    "in",
                    list(contacts_by_id),
                )
            ])
        }

        for bitrix_id, contact in contacts_by_id.items():

            try:

                with self.env.cr.savepoint():

                    values = self._bitrix_to_odoo_values(contact)

                    partner = partners_by_bitrix_id.get(
                        bitrix_id
                    )

                    if not partner:

                        partner = self.create(dict(
                            values,
                            bitrix_contact_id=bitrix_id,
                            bitrix_last_sync=(
                                fields.Datetime.now()
                            ),
                        ))

                        partners_by_bitrix_id[
                            bitrix_id
                        ] = partner

                        touched_ids.add(partner.id)
                        imported += 1

                    elif self._odoo_to_sync_values(
                        partner
                    ) != values:

                        bitrix_date = self._parse_bitrix_date(
                            contact.get("DATE_MODIFY")
                        )

                        if not (
                            bitrix_date
                            and partner.write_date
                            and bitrix_date <= partner.write_date
                        ):

                            partner.write(dict(
                                values,
                                bitrix_last_sync=(
                                    fields.Datetime.now()
                                ),
                            ))

                            touched_ids.add(partner.id)
                            updated += 1

            except Exception as error:

                self._log_failure(
                    log,
                    _("Contacto Bitrix %s") % bitrix_id,
                    error,
                )

        return imported, updated, touched_ids

    def _push_bitrix_contacts(
        self, api, contacts_by_id, touched_ids, since, log
    ):

        domain = [("type", "=", "contact")]

        if touched_ids:

            domain.append(
                ("id", "not in", list(touched_ids))
            )

        if since:

            domain = [
                "|",
                ("write_date", ">", since),
                ("bitrix_contact_id", "=", False),
            ] + domain

        exported = 0

        for partner in self.search(domain):

            try:

                with self.env.cr.savepoint():

                    values = self._odoo_to_sync_values(partner)
                    bitrix_id = partner.bitrix_contact_id

                    if bitrix_id:

                        if bitrix_id not in contacts_by_id:
                            continue

                        if values == (
                            self._bitrix_to_odoo_values(
                                contacts_by_id[bitrix_id]
                            )
                        ):
                            continue

                        api.update_contact(
                            bitrix_id,
                            self._odoo_values_to_bitrix(values),
                        )

                    else:

                        new_id = api.create_contact(
                            self._odoo_values_to_bitrix(values)
                        )

                        if new_id:
                            partner.bitrix_contact_id = str(
                                new_id
                            )

                    partner.bitrix_last_sync = (
                        fields.Datetime.now()
                    )

                    exported += 1

            except Exception as error:

                self._log_failure(
                    log,
                    _("Contacto Odoo %s") % partner.display_name,
                    error,
                )

        return exported

    def sync_with_bitrix(self, config):

        api = BitrixAPI(config.webhook_url)

        since = config.last_sync

        contacts = api.get_contacts(since=since)

        contacts_by_id = {
            str(contact.get("ID")): contact
            for contact in contacts
            if contact.get("ID")
        }

        log = self.env["bitrix.sync.log"].create({
            "config_id": config.id,
            "direction": "both",
            "run_datetime": fields.Datetime.now(),
            "incremental": bool(since),
        })

        imported, updated, touched_ids = (
            self._pull_bitrix_contacts(
                contacts_by_id, log
            )
        )

        exported = self._push_bitrix_contacts(
            api, contacts_by_id, touched_ids, since, log
        )

        self._sync_companies(config)

        log.write({
            "imported": imported,
            "updated": updated,
            "exported": exported,
        })

        config.last_sync = fields.Datetime.now()

        return {
            "imported": imported,
            "updated": updated,
            "exported": exported,
            "failed": log.failed,
            "log_id": log.id,
        }

    def import_bitrix_contacts(self):

        config = self._get_bitrix_config()

        api = BitrixAPI(config.webhook_url)

        try:
            contacts = api.get_contacts()

        except Exception as error:
            raise UserError(
                _("Error conectando con Bitrix24: %s") % error
            )

        contacts_by_id = {
            str(contact.get("ID")): contact
            for contact in contacts
            if contact.get("ID")
        }

        log = self.env["bitrix.sync.log"].create({
            "config_id": config.id,
            "direction": "pull",
            "run_datetime": fields.Datetime.now(),
            "incremental": False,
        })

        imported, updated, _touched = (
            self._pull_bitrix_contacts(contacts_by_id, log)
        )

        log.write({
            "imported": imported,
            "updated": updated,
        })

        config.last_sync = fields.Datetime.now()

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