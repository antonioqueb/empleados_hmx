# -*- coding: utf-8 -*-
from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ──────────────────────────────────────────────────────────────────────────
    # Campos HMX (NO cambiar nombres)
    # ──────────────────────────────────────────────────────────────────────────

    x_numero_nomina = fields.Integer(
        string='Número de nómina',
        help='Número de nómina asignado al empleado.'
    )

    x_planta = fields.Selection(
        [
            ('Planta 1', 'Planta 1'),
            ('Planta 2', 'Planta 2'),
            ('Planta 3', 'Planta 3'),
            ('Planta 4', 'Planta 4'),
            ('Planta 5', 'Planta 5'),
            ('Planta 6', 'Planta 6'),
            ('Planta 7', 'Planta 7'),
        ],
        string='Planta',
        help='Planta a la que está asignado el empleado.'
    )

    x_ubicacion = fields.Char(
        string='Ubicación',
        help='Ubicación o área asignada al empleado.'
    )

    x_fecha_ingreso = fields.Date(
        string='Fecha de Ingreso',
        help='Fecha en la que el empleado ingresó a la empresa.'
    )

    # x_antiguedad: días TOTALES transcurridos (considera bisiestos porque es diferencia real de fechas)
    x_antiguedad = fields.Integer(
        string='Antigüedad (días)',
        compute='_compute_antiguedad',
        store=True,
        help='Días totales transcurridos desde la fecha de ingreso hasta hoy (calendario gregoriano).'
    )

    # x_antiguedad_meses: meses TOTALES completos transcurridos (gregoriano: meses reales 28/29/30/31)
    x_antiguedad_meses = fields.Integer(
        string='Antigüedad (meses)',
        compute='_compute_antiguedad',
        store=True,
        help='Meses totales completos transcurridos desde la fecha de ingreso hasta hoy (calendario gregoriano).'
    )

    # x_antiguedad_anios: años COMPLETOS transcurridos (gregoriano, incluye años bisiestos)
    x_antiguedad_anios = fields.Integer(
        string='Antigüedad (años)',
        compute='_compute_antiguedad',
        store=True,
        help='Años completos transcurridos desde la fecha de ingreso hasta hoy (calendario gregoriano).'
    )

    x_fecha_baja = fields.Date(
        string='Fecha de Baja',
        help='Fecha en la que el empleado causó baja.'
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Cálculo robusto (Gregoriano + bisiestos)
    # ──────────────────────────────────────────────────────────────────────────

    @api.depends('x_fecha_ingreso')
    def _compute_antiguedad(self):
        """
        Reglas:
        - Se usa calendario gregoriano real (incluye días bisiestos automáticamente).
        - x_antiguedad: diferencia REAL en días (today - ingreso).
        - x_antiguedad_anios: años COMPLETOS transcurridos (relativedelta.years).
        - x_antiguedad_meses: meses TOTALES completos transcurridos (años*12 + meses).
        - Si x_fecha_ingreso está en el futuro, se normaliza todo a 0 (evita negativos).
        """
        # context_today respeta TZ/ctx; para Date es lo más consistente en Odoo
        today = fields.Date.context_today(self)

        for record in self:
            ingreso = record.x_fecha_ingreso
            if not ingreso:
                record.x_antiguedad = 0
                record.x_antiguedad_meses = 0
                record.x_antiguedad_anios = 0
                continue

            # Evita negativos si cargan una fecha futura por error
            if ingreso > today:
                record.x_antiguedad = 0
                record.x_antiguedad_meses = 0
                record.x_antiguedad_anios = 0
                continue

            # Días totales (incluye bisiestos al ser diferencia real de fechas)
            total_days = (today - ingreso).days

            # Delta por calendario (gregoriano): años/meses residuales exactos
            delta = relativedelta(today, ingreso)
            years_completed = delta.years
            months_total_completed = (delta.years * 12) + delta.months

            record.x_antiguedad = total_days
            record.x_antiguedad_anios = years_completed
            record.x_antiguedad_meses = months_total_completed