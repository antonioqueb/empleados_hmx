# -*- coding: utf-8 -*-
{
    'name': 'empleados_hmx',
    'version': '1.0.0',
    'author': 'Alphaqueb Consulting S.A.S.',
    'category': 'Human Resources',
    'summary': 'Módulo personalizado para la gestión extendida de empleados.',
    'description': """
                    Módulo personalizado de Odoo 17 que agrega campos adicionales al modelo de Empleados
                    y extiende las vistas de formulario y lista para gestionar:
                    - Número de nómina
                    - Planta
                    - Ubicación
                    - Fecha de ingreso
                    - Antigüedad (cálculo almacenado)
                    - Fecha de baja
                  """,
    'depends': ['hr'],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}
