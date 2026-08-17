# -*- coding: utf-8 -*-
{
    'name': 'empleados_hmx',
    'version': '18.0.2.1.0',
    'author': 'Alphaqueb Consulting S.A.S.',
    'category': 'Human Resources',
    'summary': 'Módulo personalizado para la gestión extendida de empleados.',
    'description': """
Módulo personalizado que agrega campos adicionales al modelo de Empleados
y extiende las vistas de formulario y lista para gestionar:
- Número de nómina
- Planta
- Ubicación
- Fecha de ingreso
- Antigüedad (cálculo almacenado)
- Fecha de baja

Gestión de asistencia HMX:
- Captura diaria de asistencia e incidencias por los supervisores
  (A, F, S, PCS, PSS, V, INC, TX) con turno, máquina y tiempo extra;
  cada movimiento queda registrado con hora y usuario.
- Importación del archivo del reloj checador (.xls/.xlsx) con empate
  por número de nómina.
- Cruce checador vs. captura: entrada/salida por día, discrepancias
  (sin checada, checó con incidencia, checó sin captura, checada única)
  y generación automática de registros por validar.
""",
    'depends': ['hr', 'mail'],
    'data': [
        'security/hmx_attendance_security.xml',
        'security/ir.model.access.csv',
        'data/hmx_attendance_data.xml',
        'views/hr_employee_views.xml',
        'views/hmx_attendance_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}