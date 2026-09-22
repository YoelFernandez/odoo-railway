from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestEigrConstructionClosure(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Closure = cls.env["eigr.construction.closure"]
        cls.team_user = cls.env["res.users"].create(
            {
                "name": "Responsable de Cierre EIGR",
                "login": "responsable_cierre_eigr_test",
                "group_ids": [
                    Command.link(
                        cls.env.ref(
                            "eigr_construction_management.group_eigr_user"
                        ).id
                    )
                ],
            }
        )
        cls.project = cls.env["eigr.construction.project"].create(
            {
                "name": "Obra para cierre",
                "responsible_id": cls.team_user.id,
                "state": "closing",
                "progress_percent": 100,
                "planned_start_date": "2026-01-01",
                "planned_end_date": "2026-12-31",
            }
        )

    def _closure_values(self, completed=10):
        lines = []
        for index in range(10):
            lines.append(
                Command.create(
                    {
                        "sequence": (index + 1) * 10,
                        "category": "contractual",
                        "name": f"Control de cierre {index + 1}",
                        "responsible_id": self.team_user.id,
                        "deadline": "2026-12-31",
                        "status": "done" if index < completed else "pending",
                        "evidence_reference": (
                            f"EVIDENCIA-{index + 1}" if index < completed else False
                        ),
                    }
                )
            )
        return {
            "name": "Expediente de cierre de prueba",
            "project_id": self.project.id,
            "responsible_id": self.team_user.id,
            "start_date": "2026-12-01",
            "target_date": "2026-12-31",
            "final_report_reference": "INF-CIERRE-TEST",
            "client_acceptance_date": "2026-12-30",
            "line_ids": lines,
        }

    def test_sequence_and_completion(self):
        closure = self.Closure.create(self._closure_values())
        self.assertRegex(closure.code, r"^CIE-\d{4}-\d{4}$")
        self.assertEqual(closure.item_count, 10)
        self.assertEqual(closure.completed_count, 10)
        self.assertEqual(closure.completion_percent, 100)
        self.assertEqual(self.project.closure_id, closure)

    def test_submit_approve_and_close_project(self):
        closure = self.Closure.create(self._closure_values())
        closure.action_submit_review()
        self.assertEqual(closure.state, "review")
        closure.action_approve()
        self.assertEqual(closure.state, "approved")
        self.assertEqual(self.project.state, "closed")
        self.assertTrue(self.project.actual_end_date)

    def test_reject_incomplete_checklist(self):
        closure = self.Closure.create(self._closure_values(completed=9))
        with self.assertRaises(UserError):
            closure.action_submit_review()

    def test_only_manager_can_approve(self):
        closure = self.Closure.create(self._closure_values())
        closure.action_submit_review()
        with self.assertRaises(AccessError):
            closure.with_user(self.team_user).action_approve()

    def test_review_checklist_is_locked(self):
        closure = self.Closure.create(self._closure_values())
        closure.action_submit_review()
        with self.assertRaises(UserError):
            closure.line_ids[0].status = "pending"

    def test_generate_standard_checklist(self):
        closure = self.Closure.create(
            {
                "name": "Checklist estandar",
                "project_id": self.project.id,
                "responsible_id": self.team_user.id,
                "start_date": "2026-12-01",
                "target_date": "2026-12-31",
            }
        )
        closure.action_generate_checklist()
        self.assertEqual(len(closure.line_ids), 10)

    def test_reject_invalid_dates(self):
        values = self._closure_values()
        values["target_date"] = "2026-11-30"
        with self.assertRaises(ValidationError):
            self.Closure.create(values)

    def test_executive_report_renders_html(self):
        self.Closure.create(self._closure_values())
        html, report_type = self.env["ir.actions.report"]._render_qweb_html(
            "eigr_construction_management.action_report_eigr_project_executive",
            [self.project.id],
        )
        self.assertEqual(report_type, "html")
        self.assertIn(b"REPORTE EJECUTIVO DE OBRA", html)
        self.assertIn(b"Obra para cierre", html)
