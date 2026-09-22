from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class EigrConstructionBudget(models.Model):
    _name = "eigr.construction.budget"
    _description = "Presupuesto de Obra EIGR"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Presupuesto", required=True, tracking=True)
    code = fields.Char(string="Código", required=True, default="Nuevo", tracking=True)
    project_id = fields.Many2one(
        "eigr.construction.project",
        string="Obra",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
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
    date = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    version = fields.Integer(string="Version", required=True, default=1, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("approved", "Aprobado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        "eigr.construction.budget.line",
        "budget_id",
        string="Partidas",
        copy=True,
    )
    line_count = fields.Integer(
        compute="_compute_line_count",
        string="Cantidad de partidas",
    )
    amount_cost = fields.Monetary(
        string="Costo Meta",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        tracking=True,
    )
    amount_sale = fields.Monetary(
        string="Venta Meta",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        tracking=True,
    )
    margin_amount = fields.Monetary(
        string="Margen",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    margin_percent = fields.Float(
        string="Margen (%)",
        compute="_compute_totals",
        store=True,
    )
    approved_by_id = fields.Many2one(
        "res.users",
        string="Aprobado por",
        readonly=True,
        tracking=True,
    )
    approval_date = fields.Datetime(
        string="Fecha de aprobación",
        readonly=True,
        tracking=True,
    )
    notes = fields.Html(string="Criterios y observaciones")

    _project_version_unique = models.Constraint(
        "UNIQUE(project_id, version)",
        "La version del presupuesto debe ser unica para la obra.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "Nuevo") == "Nuevo":
                vals["code"] = (
                    self.env["ir.sequence"].next_by_code("eigr.construction.budget")
                    or "Nuevo"
                )
        return super().create(vals_list)

    @api.depends("line_ids")
    def _compute_line_count(self):
        for budget in self:
            budget.line_count = len(budget.line_ids)

    @api.depends("line_ids.subtotal_cost", "line_ids.subtotal_sale")
    def _compute_totals(self):
        for budget in self:
            budget.amount_cost = sum(budget.line_ids.mapped("subtotal_cost"))
            budget.amount_sale = sum(budget.line_ids.mapped("subtotal_sale"))
            budget.margin_amount = budget.amount_sale - budget.amount_cost
            budget.margin_percent = (
                budget.margin_amount / budget.amount_sale * 100
                if budget.amount_sale
                else 0.0
            )

    @api.constrains("version")
    def _check_version(self):
        for budget in self:
            if budget.version <= 0:
                raise ValidationError("La version debe ser mayor que cero.")

    def _check_manager(self):
        if not self.env.user.has_group(
            "eigr_construction_management.group_eigr_manager"
        ):
            raise AccessError("Solo el Jefe de Control puede aprobar presupuestos.")

    def action_approve(self):
        self._check_manager()
        for budget in self:
            if budget.state != "draft":
                raise UserError("Solo se puede aprobar un presupuesto en borrador.")
            if budget.project_id.state not in ("planning", "execution"):
                raise UserError(
                    "La obra debe estar en Planificación o Ejecución para aprobar el presupuesto."
                )
            if not budget.line_ids or budget.amount_sale <= 0:
                raise UserError("Agregue partidas con una venta meta mayor que cero.")
            other = self.search_count(
                [
                    ("project_id", "=", budget.project_id.id),
                    ("state", "=", "approved"),
                    ("id", "!=", budget.id),
                ]
            )
            if other:
                raise UserError("La obra ya tiene un Presupuesto Meta aprobado.")
        self.sudo().write(
            {
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approval_date": fields.Datetime.now(),
            }
        )
        return True

    def action_reset_draft(self):
        self._check_manager()
        invalid = self.filtered(lambda budget: budget.state != "approved")
        if invalid:
            raise UserError("Solo un presupuesto aprobado puede volver a borrador.")
        self.sudo().write(
            {
                "state": "draft",
                "approved_by_id": False,
                "approval_date": False,
            }
        )
        return True

    def action_cancel(self):
        self._check_manager()
        invalid = self.filtered(lambda budget: budget.state == "cancelled")
        if invalid:
            raise UserError("El presupuesto ya esta cancelado.")
        self.sudo().write({"state": "cancelled"})
        return True

    def action_restore(self):
        self._check_manager()
        invalid = self.filtered(lambda budget: budget.state != "cancelled")
        if invalid:
            raise UserError("Solo un presupuesto cancelado puede restaurarse.")
        self.sudo().write(
            {
                "state": "draft",
                "approved_by_id": False,
                "approval_date": False,
            }
        )
        return True

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        last_version = self.search(
            [("project_id", "=", self.project_id.id)],
            order="version desc",
            limit=1,
        ).version
        default.update(
            {
                "code": "Nuevo",
                "name": f"{self.name} - Version {last_version + 1}",
                "version": last_version + 1,
                "state": "draft",
                "approved_by_id": False,
                "approval_date": False,
            }
        )
        return super().copy(default)


class EigrConstructionBudgetLine(models.Model):
    _name = "eigr.construction.budget.line"
    _description = "Partida de Presupuesto EIGR"
    _order = "sequence, code, id"

    sequence = fields.Integer(default=10)
    budget_id = fields.Many2one(
        "eigr.construction.budget",
        string="Presupuesto",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="budget_id.company_id", store=True)
    currency_id = fields.Many2one(related="budget_id.currency_id", store=True)
    code = fields.Char(string="Código de partida", required=True)
    name = fields.Char(string="Partida", required=True)
    chapter = fields.Char(string="Capitulo")
    unit = fields.Selection(
        [
            ("glb", "Global"),
            ("und", "Unidad"),
            ("m", "Metro"),
            ("m2", "Metro cuadrado"),
            ("m3", "Metro cubico"),
            ("kg", "Kilogramo"),
            ("dia", "Dia"),
            ("mes", "Mes"),
        ],
        string="Unidad",
        required=True,
        default="und",
    )
    quantity = fields.Float(string="Metrado", required=True, default=1.0, digits=(16, 3))
    unit_cost = fields.Monetary(
        string="Costo unitario",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )
    unit_price = fields.Monetary(
        string="Precio unitario",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )
    subtotal_cost = fields.Monetary(
        string="Costo Meta",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    subtotal_sale = fields.Monetary(
        string="Venta Meta",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    margin_amount = fields.Monetary(
        string="Margen",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    weight_percent = fields.Float(
        string="Peso (%)",
        compute="_compute_weight",
    )
    control_item = fields.Boolean(string="Partida de Control", default=True)
    resource_type = fields.Selection(
        [
            ("labor", "Mano de obra"),
            ("material", "Material"),
            ("equipment", "Equipo"),
            ("subcontract", "Subcontrato"),
            ("service", "Servicio"),
            ("mixed", "Mixto"),
        ],
        string="Recurso principal",
        default="mixed",
    )
    specific_destination = fields.Char(string="Destino especifico")

    _budget_code_unique = models.Constraint(
        "UNIQUE(budget_id, code)",
        "El código de partida debe ser unico dentro del presupuesto.",
    )

    @api.depends("quantity", "unit_cost", "unit_price")
    def _compute_amounts(self):
        for line in self:
            line.subtotal_cost = line.quantity * line.unit_cost
            line.subtotal_sale = line.quantity * line.unit_price
            line.margin_amount = line.subtotal_sale - line.subtotal_cost

    @api.depends("subtotal_sale", "budget_id.amount_sale")
    def _compute_weight(self):
        for line in self:
            line.weight_percent = (
                line.subtotal_sale / line.budget_id.amount_sale * 100
                if line.budget_id.amount_sale
                else 0.0
            )

    @api.constrains("quantity", "unit_cost", "unit_price")
    def _check_nonnegative_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError("El metrado debe ser mayor que cero.")
            if line.unit_cost < 0 or line.unit_price < 0:
                raise ValidationError("Los costos y precios no pueden ser negativos.")

    def _check_budget_editable(self):
        if self.filtered(lambda line: line.budget_id.state != "draft"):
            raise UserError("Las partidas solo pueden modificarse en un presupuesto borrador.")

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env["eigr.construction.budget"].browse(
            [vals.get("budget_id") for vals in vals_list if vals.get("budget_id")]
        )
        if budgets.filtered(lambda budget: budget.state != "draft"):
            raise UserError("No se pueden agregar partidas a un presupuesto aprobado o cancelado.")
        return super().create(vals_list)

    def write(self, vals):
        self._check_budget_editable()
        return super().write(vals)

    def unlink(self):
        self._check_budget_editable()
        return super().unlink()
