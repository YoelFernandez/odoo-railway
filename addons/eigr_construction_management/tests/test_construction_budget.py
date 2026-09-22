from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestEigrConstructionBudget(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Budget = cls.env["eigr.construction.budget"]
        cls.team_user = cls.env["res.users"].create(
            {
                "name": "Presupuestador EIGR",
                "login": "presupuestador_eigr_test",
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
                "name": "Obra para presupuesto",
                "responsible_id": cls.team_user.id,
                "state": "planning",
                "planned_start_date": "2026-08-01",
                "planned_end_date": "2026-12-31",
            }
        )

    def _budget_values(self, version=1):
        return {
            "name": f"Presupuesto Meta v{version}",
            "project_id": self.project.id,
            "version": version,
            "line_ids": [
                Command.create(
                    {
                        "code": "01.01",
                        "name": "Partida de prueba",
                        "unit": "m3",
                        "quantity": 10,
                        "unit_cost": 80,
                        "unit_price": 100,
                    }
                ),
                Command.create(
                    {
                        "code": "01.02",
                        "name": "Segunda partida",
                        "unit": "und",
                        "quantity": 5,
                        "unit_cost": 40,
                        "unit_price": 60,
                    }
                ),
            ],
        }

    def test_compute_budget_totals_and_sequence(self):
        budget = self.Budget.create(self._budget_values())
        self.assertRegex(budget.code, r"^PRE-\d{4}-\d{4}$")
        self.assertEqual(budget.amount_cost, 1000)
        self.assertEqual(budget.amount_sale, 1300)
        self.assertEqual(budget.margin_amount, 300)
        self.assertAlmostEqual(budget.margin_percent, 300 / 1300 * 100)
        self.assertAlmostEqual(sum(budget.line_ids.mapped("weight_percent")), 100)

    def test_approve_budget_and_project_summary(self):
        budget = self.Budget.create(self._budget_values())
        budget.action_approve()
        self.assertEqual(budget.state, "approved")
        self.assertEqual(budget.approved_by_id, self.env.user)
        self.assertEqual(self.project.approved_budget_id, budget)
        self.assertEqual(self.project.approved_budget_cost, 1000)

    def test_only_manager_can_approve(self):
        budget = self.Budget.create(self._budget_values())
        with self.assertRaises(AccessError):
            budget.with_user(self.team_user).action_approve()

    def test_only_one_approved_budget_per_project(self):
        first = self.Budget.create(self._budget_values())
        second = self.Budget.create(self._budget_values(version=2))
        first.action_approve()
        with self.assertRaises(UserError):
            second.action_approve()

    def test_approved_lines_are_locked(self):
        budget = self.Budget.create(self._budget_values())
        budget.action_approve()
        with self.assertRaises(UserError):
            budget.line_ids[0].unit_cost = 90

    def test_reject_invalid_line_values(self):
        values = self._budget_values()
        values["line_ids"] = [
            Command.create(
                {
                    "code": "INVALID",
                    "name": "Partida invalida",
                    "quantity": 0,
                    "unit_cost": 10,
                    "unit_price": 20,
                }
            )
        ]
        with self.assertRaises(ValidationError):
            self.Budget.create(values)

    def test_copy_creates_new_version(self):
        budget = self.Budget.create(self._budget_values())
        copied = budget.copy()
        self.assertEqual(copied.version, 2)
        self.assertEqual(copied.state, "draft")
        self.assertNotEqual(copied.code, budget.code)
        self.assertEqual(len(copied.line_ids), 2)
