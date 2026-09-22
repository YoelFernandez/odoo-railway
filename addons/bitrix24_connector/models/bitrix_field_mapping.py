import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)

class BitrixFieldMapping(models.Model):
    _name = "bitrix.field.mapping"
    _description = "Mapeo de campos Odoo <-> Bitrix24"
    _order = "entity, sequence"

    entity = fields.Selection(
        [
            ("contact", "Contacto"),
            ("company", "Empresa"),
            ("deal", "Negocio"),
        ],
        string="Entidad Bitrix24",
        required=True,
    )

    sequence = fields.Integer(string="Secuencia", default=10)

    odoo_field = fields.Char(
        string="Campo Odoo",
        required=True,
        help="Nombre nominal del campo en Odoo (p. ej. name, phone).",
    )

    bitrix_field = fields.Char(
        string="Campo Bitrix24",
        required=True,
        help="Nombre del campo en Bitrix24 (p. ej. NAME, UF_CRM_...).",
    )

    field_type = fields.Selection(
        [
            ("char", "Texto"),
            ("multifield", "Multicampo (PHONE/EMAIL)"),
        ],
        string="Tipo",
        default="char",
    )

    is_bitrix_to_odoo = fields.Boolean(
        string="Importar (Bitrix -> Odoo)",
        default=True,
    )

    is_odoo_to_bitrix = fields.Boolean(
        string="Exportar (Odoo -> Bitrix)",
        default=True,
    )

    active = fields.Boolean(string="Activo", default=True)

    def get_mapping(self, entity):
        return self.search(
            [
                ("entity", "=", entity),
                ("active", "=", True),
            ],
            order="sequence",
        )

    def map_bitrix_to_odoo(self, values_by_odoo):
        extras = {}
        for mapping in self:
            bval = values_by_odoo.get(mapping.bitrix_field)
            if bval is None:
                continue
            if mapping.field_type == "multifield":
                bval = (
                    bval[0].get("VALUE")
                    if isinstance(bval, list) and bval
                    else (bval if isinstance(bval, dict) else bval)
                )
            extras[mapping.odoo_field] = bval
        return extras
