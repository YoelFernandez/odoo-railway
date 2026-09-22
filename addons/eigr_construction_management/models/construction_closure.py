from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


DEFAULT_CLOSURE_ITEMS = [
    ("technical", "Dossier de obra consolidado"),
    ("technical", "Planos as-built aprobados"),
    ("contractual", "Acta de recepción de obra"),
    ("contractual", "Informe final del proyecto"),
    ("contractual", "Obligaciones contractuales de cierre verificadas"),
    ("financial", "Subcontratos cerrados y finiquitos emitidos"),
    ("financial", "Expediente de liquidación de obra"),
    ("quality", "Registros de calidad y no conformidades cerrados"),
    ("administrative", "Recursos liberados y equipos desmovilizados"),
    ("administrative", "Reunion de retroalimentacion y lecciones aprendidas"),
]


class EigrConstructionClosure(models.Model):
    _name = "eigr.construction.closure"
    _description = "Expediente de Cierre de Obra EIGR"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Expediente", required=True, tracking=True)
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
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsable del cierre",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        check_company=True,
    )
    start_date = fields.Date(
        string="Inicio del cierre",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    target_date = fields.Date(string="Fecha objetivo", required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "En preparacion"),
            ("review", "En revision"),
            ("approved", "Aprobado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        required=True,
        default="draft",
        tracking=True,
    )
    line_ids = fields.One2many(
        "eigr.construction.closure.line",
        "closure_id",
        string="Checklist de cierre",
        copy=True,
    )
    item_count = fields.Integer(string="Controles", compute="_compute_counts")
    completed_count = fields.Integer(string="Cumplidos", compute="_compute_counts")
    completion_percent = fields.Float(
        string="Cumplimiento (%)",
        compute="_compute_completion_percent",
        store=True,
        tracking=True,
    )
    final_report_reference = fields.Char(string="Informe final", tracking=True)
    client_acceptance_date = fields.Date(string="Aceptacion del cliente", tracking=True)
    liquidation_reference = fields.Char(string="Expediente de liquidación", tracking=True)
    lessons_learned = fields.Html(string="Lecciones aprendidas")
    final_notes = fields.Html(string="Conclusiones del cierre")
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

    _project_unique = models.Constraint(
        "UNIQUE(project_id)",
        "Solo puede existir un expediente de cierre por obra.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "Nuevo") == "Nuevo":
                vals["code"] = (
                    self.env["ir.sequence"].next_by_code("eigr.construction.closure")
                    or "Nuevo"
                )
        return super().create(vals_list)

    @api.depends("line_ids.status")
    def _compute_counts(self):
        for closure in self:
            closure.item_count = len(closure.line_ids)
            completed = closure.line_ids.filtered(
                lambda line: line.status in ("done", "waived")
            )
            closure.completed_count = len(completed)

    @api.depends("line_ids.status")
    def _compute_completion_percent(self):
        for closure in self:
            completed = closure.line_ids.filtered(
                lambda line: line.status in ("done", "waived")
            )
            closure.completion_percent = (
                len(completed) / len(closure.line_ids) * 100
                if closure.line_ids
                else 0.0
            )

    @api.constrains("start_date", "target_date")
    def _check_dates(self):
        for closure in self:
            if closure.target_date < closure.start_date:
                raise ValidationError(
                    "La fecha objetivo no puede ser anterior al inicio del cierre."
                )

    def _check_manager(self):
        if not self.env.user.has_group(
            "eigr_construction_management.group_eigr_manager"
        ):
            raise AccessError("Solo el Jefe de Control puede realizar esta operacion.")

    def action_generate_checklist(self):
        for closure in self:
            if closure.state != "draft":
                raise UserError("El checklist solo se genera durante la preparacion.")
            existing = set(closure.line_ids.mapped("name"))
            commands = [
                Command.create(
                    {
                        "sequence": index * 10,
                        "category": category,
                        "name": name,
                        "responsible_id": closure.responsible_id.id,
                        "deadline": closure.target_date,
                    }
                )
                for index, (category, name) in enumerate(DEFAULT_CLOSURE_ITEMS, 1)
                if name not in existing
            ]
            if commands:
                closure.write({"line_ids": commands})
        return True

    def action_submit_review(self):
        invalid = self.filtered(lambda closure: closure.state != "draft")
        if invalid:
            raise UserError("Solo un expediente en preparacion puede enviarse.")
        for closure in self:
            if closure.project_id.state != "closing":
                raise UserError("La obra debe estar en estado Cierre.")
            if not closure.line_ids:
                raise UserError("Genere y complete el checklist de cierre.")
            if closure.completion_percent < 95:
                raise UserError("El checklist debe alcanzar al menos 95% de cumplimiento.")
            if not closure.final_report_reference or not closure.client_acceptance_date:
                raise UserError("Registre el informe final y la aceptacion del cliente.")
        self.write({"state": "review"})
        return True

    def action_approve(self):
        self._check_manager()
        invalid = self.filtered(lambda closure: closure.state != "review")
        if invalid:
            raise UserError("Solo un expediente en revision puede aprobarse.")
        for closure in self:
            if closure.project_id.progress_percent <= 99:
                raise UserError(
                    "La obra debe tener un avance físico superior al 99%."
                )
        self.sudo().write(
            {
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approval_date": fields.Datetime.now(),
            }
        )
        for closure in self:
            closure.project_id.action_close()
        return True

    def action_reset_draft(self):
        self._check_manager()
        invalid = self.filtered(lambda closure: closure.state != "review")
        if invalid:
            raise UserError("Solo un expediente en revision puede volver a preparacion.")
        self.sudo().write({"state": "draft"})
        return True

    def action_cancel(self):
        self._check_manager()
        invalid = self.filtered(lambda closure: closure.state not in ("draft", "review"))
        if invalid:
            raise UserError("Un expediente aprobado o cancelado no puede cancelarse.")
        self.sudo().write({"state": "cancelled"})
        return True

    def unlink(self):
        if self.filtered(lambda closure: closure.state != "draft"):
            raise UserError("Solo puede eliminarse un expediente en preparacion.")
        return super().unlink()


class EigrConstructionClosureLine(models.Model):
    _name = "eigr.construction.closure.line"
    _description = "Control Documental de Cierre EIGR"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    closure_id = fields.Many2one(
        "eigr.construction.closure",
        string="Expediente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="closure_id.company_id", store=True)
    category = fields.Selection(
        [
            ("contractual", "Contractual"),
            ("technical", "Técnico"),
            ("quality", "Calidad"),
            ("financial", "Financiero"),
            ("administrative", "Administrativo"),
        ],
        string="Categoria",
        required=True,
        default="administrative",
    )
    name = fields.Char(string="Requisito de cierre", required=True)
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsable",
        required=True,
        default=lambda self: self.env.user,
        check_company=True,
    )
    deadline = fields.Date(string="Fecha limite")
    status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("in_progress", "En proceso"),
            ("done", "Cumplido"),
            ("waived", "No aplica"),
        ],
        string="Estado",
        required=True,
        default="pending",
    )
    evidence_reference = fields.Char(string="Evidencia / referencia")
    attachment_ids = fields.Many2many("ir.attachment", string="Archivos de evidencia")
    completed_by_id = fields.Many2one("res.users", string="Completado por", readonly=True)
    completion_date = fields.Datetime(string="Fecha de cumplimiento", readonly=True)
    notes = fields.Char(string="Observaciones")

    @api.onchange("status")
    def _onchange_status(self):
        if self.status in ("done", "waived"):
            self.completed_by_id = self.env.user
            self.completion_date = fields.Datetime.now()
        else:
            self.completed_by_id = False
            self.completion_date = False

    @api.model_create_multi
    def create(self, vals_list):
        closures = self.env["eigr.construction.closure"].browse(
            [vals.get("closure_id") for vals in vals_list if vals.get("closure_id")]
        )
        if closures.filtered(lambda closure: closure.state != "draft"):
            raise UserError("Solo se agregan controles durante la preparacion.")
        for vals in vals_list:
            if vals.get("status") in ("done", "waived"):
                vals.setdefault("completed_by_id", self.env.user.id)
                vals.setdefault("completion_date", fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda line: line.closure_id.state != "draft"):
            raise UserError("El checklist no puede editarse en el estado actual.")
        if "status" in vals:
            if vals["status"] in ("done", "waived"):
                vals.setdefault("completed_by_id", self.env.user.id)
                vals.setdefault("completion_date", fields.Datetime.now())
            else:
                vals.setdefault("completed_by_id", False)
                vals.setdefault("completion_date", False)
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda line: line.closure_id.state != "draft"):
            raise UserError("El checklist no puede editarse en el estado actual.")
        return super().unlink()
