# -*- coding: utf-8 -*-
from odoo import fields, models, api
from datetime import date

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

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

    x_antiguedad = fields.Integer(
        string='Antigüedad (días)',
        compute='_compute_antiguedad',
        store=True,
        help='Días transcurridos desde la fecha de ingreso hasta hoy.'
    )

        x_antiguedad_meses = fields.Integer(
        string='Antigüedad (meses)',
        compute='_compute_antiguedad',
        store=True,
        help='Meses transcurridos desde la fecha de ingreso hasta hoy.'
    )

    x_antiguedad_anios = fields.Integer(
        string='Antigüedad (años)',
        compute='_compute_antiguedad',
        store=True,
        help='Años transcurridos desde la fecha de ingreso hasta hoy.'
    )


    x_fecha_baja = fields.Date(
        string='Fecha de Baja',
        help='Fecha en la que el empleado causó baja.'
    )

    @api.depends('x_fecha_ingreso')
    def _compute_antiguedad(self):
        """ Calcula la antigüedad en días desde la fecha de ingreso
            hasta la fecha actual. """
        for record in self:
            if record.x_fecha_ingreso:
                delta = date.today() - record.x_fecha_ingreso
                record.x_antiguedad = delta.days
            else:
                record.x_antiguedad = 0
