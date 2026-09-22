from odoo import models, fields, api

class BitrixSyncLog(models.Model):

    _name = "bitrix.sync.log"
    _description = "Registro de sincronización Bitrix24"
    _order = "run_datetime desc, id desc"

    name = fields.Char(
        string="Referencia",
        compute="_compute_name",
    )

    config_id = fields.Many2one(
        "bitrix.config",
        string="Configuración",
        ondelete="cascade",
    )

    run_datetime = fields.Datetime(
        string="Fecha de ejecución",
        readonly=True,
    )

    direction = fields.Selection(
        [
            ("pull", "Bitrix24 → Odoo"),
            ("push", "Odoo → Bitrix24"),
            ("both", "Bidireccional"),
        ],
        string="Dirección",
        readonly=True,
    )

    incremental = fields.Boolean(
        string="Incremental",
        readonly=True,
    )

    imported = fields.Integer(string="Importados", readonly=True)

    updated = fields.Integer(string="Actualizados", readonly=True)

    exported = fields.Integer(string="Exportados", readonly=True)

    failed = fields.Integer(string="Fallidos", readonly=True)

    error_log = fields.Text(string="Errores", readonly=True)

    @api.depends("direction", "run_datetime")
    def _compute_name(self):

        labels = dict(self._fields["direction"].selection)

        for log in self:

            log.name = "%s - %s" % (
                labels.get(log.direction, ""),
                log.run_datetime or "",
            )