from odoo import api, fields, models

class EIGRConstructionCommon(models.AbstractModel):
    _name = "eigr.construction.common"
    _description = "Base común de modelos de obra"

    project_id = fields.Many2one(
        "eigr.construction.project",
        string="Obra",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="project_id.company_id",
        string="Empresa",
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="project_id.currency_id",
        string="Moneda",
        store=True,
    )
    date = fields.Date(string="Fecha")
    notes = fields.Text(string="Observaciones")

class EigrConstructionTechnicalFile(models.Model):
    _name = "eigr.construction.technical_file"
    _description = "Expediente Técnico de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Expediente", required=True)
    code = fields.Char(string="Código", required=True, default="Nuevo")
    file_type = fields.Selection(
        [
            ("study", "Estudio definitivo"),
            ("project", "Proyecto"),
            ("approved", "Expediente aprobado"),
            ("additional", "Expediente de adicional"),
            ("other", "Otro"),
        ],
        string="Tipo",
        default="study",
    )
    version = fields.Integer(string="Versión", default=1)
    approver_id = fields.Many2one("res.partner", string="Entidad que aprobó")
    approval_date = fields.Date(string="Fecha de aprobación")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("submitted", "En revisión"),
            ("approved", "Aprobado"),
            ("rejected", "Observado"),
        ],
        string="Estado",
        default="draft",
    )
    attachment_ids = fields.Many2many("ir.attachment", string="Documentos")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "Nuevo") == "Nuevo":
                vals["code"] = (
                    self.env["ir.sequence"]
                    .next_by_code("eigr.construction.technical_file")
                    or "Nuevo"
                )
        return super().create(vals_list)

class EigrConstructionMetrado(models.Model):
    _name = "eigr.construction.metrado"
    _description = "Metrado de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "code, id"

    code = fields.Char(string="Código de metrado", required=True)
    description = fields.Char(string="Partida", required=True)
    unit_id = fields.Many2one("uom.uom", string="Unidad")
    quantity = fields.Float(string="Metrado")
    unit_price = fields.Monetary(
        string="Precio unitario", currency_field="currency_id"
    )
    amount = fields.Monetary(
        string="Parcial",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
    )

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_price

class EigrConstructionSchedule(models.Model):
    _name = "eigr.construction.schedule"
    _description = "Cronograma de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "start_date, id"

    name = fields.Char(string="Actividad", required=True)
    code = fields.Char(string="Código")
    start_date = fields.Date(string="Inicio")
    end_date = fields.Date(string="Fin")
    duration = fields.Integer(string="Duración (días)")
    weight_percent = fields.Float(string="Peso (%)")
    planned_percent = fields.Float(string="Avance acumulado planificado (%)")
    actual_percent = fields.Float(string="Avance real (%)")

class EigrConstructionAdvance(models.Model):
    _name = "eigr.construction.advance"
    _description = "Adelanto de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Adelanto", required=True)
    advance_type = fields.Selection(
        [
            ("direct", "Adelanto directo"),
            ("material", "Adelanto para materiales"),
        ],
        string="Tipo",
        required=True,
    )
    approved_amount = fields.Monetary(
        string="Monto aprobado", currency_field="currency_id"
    )
    amortization_percent = fields.Float(string="Amortización (%)")

class EigrConstructionAdditional(models.Model):
    _name = "eigr.construction.additional"
    _description = "Adicional o Deductivo de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Concepto", required=True)
    kind = fields.Selection(
        [
            ("additional", "Adicional de obra"),
            ("deductive", "Deductivo de obra"),
        ],
        string="Tipo",
        default="additional",
    )
    approved_amount = fields.Monetary(
        string="Monto aprobado", currency_field="currency_id"
    )
    resolution = fields.Char(string="Resolución / Sustento")

class EigrConstructionDeadline(models.Model):
    _name = "eigr.construction.deadline"
    _description = "Ampliación de Plazo"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Ampliación", required=True)
    days = fields.Integer(string="Días de ampliación")
    start_date = fields.Date(string="Fecha de inicio")
    end_date = fields.Date(string="Nuevo término")

class EigrConstructionPenalty(models.Model):
    _name = "eigr.construction.penalty"
    _description = "Penalidad de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Penalidad", required=True)
    penalty_type = fields.Selection(
        [
            ("delay", "Por mora / retraso"),
            ("contract", "Contractual"),
            ("guarantee", "Por garantías"),
        ],
        string="Tipo",
    )
    days_delayed = fields.Integer(string="Días de atraso")
    daily_rate = fields.Monetary(
        string="Penalidad diaria", currency_field="currency_id"
    )
    state = fields.Selection(
        [
            ("draft", "Registrada"),
            ("fined", "Aplicada"),
            ("waived", "Levantada"),
        ],
        string="Estado",
        default="draft",
    )

class EigrConstructionIncident(models.Model):
    _name = "eigr.construction.incident"
    _description = "Incidencia de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Incidencia", required=True)
    incident_type = fields.Selection(
        [
            ("obra", "De obra"),
            ("accident", "Accidente"),
            ("weather", "Clima"),
            ("material", "Materiales"),
            ("inspection", "Inspección"),
            ("other", "Otro"),
        ],
        string="Tipo",
    )
    reported_by_id = fields.Many2one("res.users", string="Reportado por")
    state = fields.Selection(
        [
            ("open", "Abierta"),
            ("in_progress", "En atención"),
            ("closed", "Cerrada"),
        ],
        string="Estado",
        default="open",
    )

class EigrConstructionDocument(models.Model):
    _name = "eigr.construction.document"
    _description = "Documento de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Documento", required=True)
    doc_type = fields.Selection(
        [
            ("contract", "Contrato"),
            ("resolution", "Resolución"),
            ("report", "Informe"),
            ("measurement", "Acta de medición"),
            ("technical", "Expediente técnico"),
            ("legal", "Legal"),
            ("other", "Otro"),
        ],
        string="Tipo",
    )
    reference = fields.Char(string="Referencia / N° documento")
    attachment_ids = fields.Many2many("ir.attachment", string="Archivos")

class EigrConstructionResource(models.Model):
    _name = "eigr.construction.resource"
    _description = "Recurso de Obra (Personal, Equipos, Materiales)"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "resource_type, name"

    name = fields.Char(string="Recurso", required=True)
    resource_type = fields.Selection(
        [
            ("person", "Personal"),
            ("equipment", "Equipo / Maquinaria"),
            ("material", "Material"),
        ],
        string="Tipo",
        required=True,
        default="person",
    )
    role = fields.Char(string="Cargo / Especificación")
    quantity = fields.Float(string="Cantidad")
    unit_id = fields.Many2one("uom.uom", string="Unidad")
    hourly_rate = fields.Monetary(
        string="Costo / hora", currency_field="currency_id"
    )
    state = fields.Selection(
        [
            ("active", "Activo"),
            ("inactive", "Inactivo"),
        ],
        string="Estado",
        default="active",
    )

class EigrConstructionCost(models.Model):
    _name = "eigr.construction.cost"
    _description = "Costo de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Concepto de costo", required=True)
    cost_type = fields.Selection(
        [
            ("labor", "Mano de obra"),
            ("material", "Materiales"),
            ("equipment", "Equipos / Maquinaria"),
            ("subcontract", "Subcontrato"),
            ("indirect", "Gastos generales"),
            ("other", "Otro"),
        ],
        string="Tipo",
    )
    quantity = fields.Float(string="Cantidad")
    unit_price = fields.Monetary(
        string="Precio unitario", currency_field="currency_id"
    )
    amount = fields.Monetary(
        string="Importe",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
    )

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_price

class EigrConstructionLiquidation(models.Model):
    _name = "eigr.construction.liquidation"
    _description = "Liquidación de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Liquidación", required=True)
    state = fields.Selection(
        [
            ("draft", "En elaboración"),
            ("submitted", "En revisión"),
            ("approved", "Aprobada"),
            ("closed", "Liquidada"),
        ],
        string="Estado",
        default="draft",
    )
    contractual_amount = fields.Monetary(
        string="Monto contractual", currency_field="currency_id"
    )
    executed_amount = fields.Monetary(
        string="Monto ejecutado", currency_field="currency_id"
    )

class EigrConstructionPartida(models.Model):
    _name = "eigr.construction.partida"
    _description = "Partida de Obra"
    _inherit = ["eigr.construction.common", "mail.thread"]
    _order = "code, id"

    code = fields.Char(string="Partida", required=True)
    description = fields.Char(string="Descripción", required=True)
    unit_id = fields.Many2one("uom.uom", string="Unidad")
    quantity = fields.Float(string="Metrado")
    unit_price = fields.Monetary(
        string="Precio unitario", currency_field="currency_id"
    )
    amount = fields.Monetary(
        string="Parcial",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
    )

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_price
