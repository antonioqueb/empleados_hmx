# -*- coding: utf-8 -*-
"""Sesiones de captura de asistencia para supervisores.

Flujo de piso, calcado de la lista de asistencia en papel:
1. El supervisor abre una sesión eligiendo su estancia (planta y/o
   departamento). La hora de inicio se sella automáticamente y no se
   puede modificar.
2. La plantilla de empleados de esa estancia se carga sola: el supervisor
   no busca empleados uno a uno, solo marca a cada quien su código de
   lista (A, F, V, INC, ...) y el tiempo extra. Cada marca sella la hora
   y el usuario del movimiento.
3. Al final del turno confirma salidas y cierra la sesión: se sella la
   hora de cierre y las marcas se consolidan en los registros diarios
   (hmx.attendance.record), que son los que administración cruza contra
   el reloj checador. El supervisor nunca toca nada del checador.
"""
from datetime import timezone

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HmxAttendanceSession(models.Model):
    _name = 'hmx.attendance.session'
    _description = 'Sesión de captura de asistencia'
    _inherit = ['mail.thread']
    _order = 'started_at desc'

    name = fields.Char('Folio', default='/', readonly=True, copy=False)
    supervisor_id = fields.Many2one(
        'res.users', 'Supervisor', required=True, readonly=True,
        default=lambda self: self.env.user,
    )
    date = fields.Date(
        'Fecha de la lista', required=True, default=fields.Date.context_today,
        readonly=True, help='Día al que corresponde la asistencia capturada.',
    )
    planta = fields.Selection(
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
    )
    department_id = fields.Many2one('hr.department', 'Departamento')
    turno = fields.Selection(
        [('dia', 'Día'), ('tarde', 'Tarde'), ('noche', 'Noche'), ('mixto', 'Mixto')],
        string='Turno',
    )
    started_at = fields.Datetime(
        'Inicio de captura', readonly=True, copy=False,
        help='Se sella al crear la sesión; no es modificable.',
    )
    closed_at = fields.Datetime('Cierre de captura', readonly=True, copy=False)
    state = fields.Selection(
        [('open', 'En captura'), ('done', 'Cerrada')],
        default='open', string='Estado', tracking=True,
    )
    line_ids = fields.One2many('hmx.attendance.session.line', 'session_id', 'Empleados')
    line_count = fields.Integer(compute='_compute_progress')
    marked_count = fields.Integer('Capturados', compute='_compute_progress')
    progress = fields.Integer('Avance %', compute='_compute_progress')

    @api.depends('line_ids.incidence_type_id')
    def _compute_progress(self):
        for session in self:
            session.line_count = len(session.line_ids)
            session.marked_count = len(session.line_ids.filtered('incidence_type_id'))
            session.progress = (
                round(100.0 * session.marked_count / session.line_count)
                if session.line_count else 0
            )

    @api.constrains('planta', 'department_id')
    def _check_scope(self):
        for session in self:
            if not session.planta and not session.department_id:
                raise ValidationError(_(
                    'Selecciona la estancia de la sesión: una planta, un '
                    'departamento, o ambos.'
                ))

    def _roster_domain(self):
        self.ensure_one()
        domain = [('active', '=', True)]
        if self.planta:
            domain.append(('x_planta', '=', self.planta))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        return domain

    def _populate_roster(self):
        """Carga la plantilla de la estancia como líneas de captura."""
        Line = self.env['hmx.attendance.session.line']
        default_type = self.env.ref(
            'empleados_hmx.incidence_type_asistencia', raise_if_not_found=False)
        for session in self:
            existing = session.line_ids.mapped('employee_id')
            employees = self.env['hr.employee'].search(
                session._roster_domain(), order='x_numero_nomina, name')
            for employee in employees - existing:
                Line.create({
                    'session_id': session.id,
                    'employee_id': employee.id,
                    'maquina': employee.x_maquina or False,
                    'default_type_id': default_type.id if default_type else False,
                })
            if not session.line_ids:
                raise UserError(_(
                    'No hay empleados activos vinculados a esa estancia. '
                    'Revisa la planta/departamento en las fichas de empleados.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # La hora de inicio la sella el servidor: no viene del cliente.
            vals['started_at'] = fields.Datetime.now()
            vals['supervisor_id'] = self.env.user.id
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hmx.attendance.session') or '/'
        sessions = super().create(vals_list)
        sessions._populate_roster()
        return sessions

    def action_reload_roster(self):
        """Agrega a la sesión empleados de la estancia que falten (altas nuevas)."""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('La sesión ya está cerrada.'))
        self._populate_roster()
        return True

    def action_close(self):
        """Cierra la sesión y consolida las marcas en los registros diarios."""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('La sesión ya está cerrada.'))
        marked = self.line_ids.filtered('incidence_type_id')
        if not marked:
            raise UserError(_('No hay ningún empleado capturado todavía.'))

        Record = self.env['hmx.attendance.record']
        created = updated = 0
        for line in marked:
            vals = {
                'incidence_type_id': line.incidence_type_id.id,
                'turno': self.turno,
                'maquina': line.maquina,
                'overtime_hours': line.overtime_hours,
                'notes': line.notes,
                'session_id': self.id,
            }
            record = Record.search([
                ('employee_id', '=', line.employee_id.id),
                ('date', '=', self.date),
            ], limit=1)
            if record:
                record.write(vals)
                updated += 1
            else:
                Record.create(dict(
                    vals, employee_id=line.employee_id.id, date=self.date,
                    source='supervisor',
                ))
                created += 1
            # La máquina capturada se recuerda para precargar la próxima lista.
            if line.maquina and line.employee_id.x_maquina != line.maquina:
                line.employee_id.x_maquina = line.maquina

        skipped = self.line_ids - marked
        self.write({'state': 'done', 'closed_at': fields.Datetime.now()})
        body = _(
            'Sesión cerrada: %(created)s registros creados y %(updated)s '
            'actualizados para el %(date)s.'
        ) % {'created': created, 'updated': updated, 'date': self.date}
        if skipped:
            body += _(' Sin capturar: %s.') % ', '.join(
                skipped.mapped('employee_id.name'))
        self.message_post(body=body)
        return True

    def unlink(self):
        if any(s.state == 'done' for s in self):
            raise UserError(_('Una sesión cerrada no se puede eliminar.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # API para la aplicación OWL de captura (menú Asistencias → Captura)
    # ------------------------------------------------------------------
    def _fmt_time(self, dt):
        """Hora local del usuario en formato corto para mostrar en la app."""
        if not dt:
            return False
        return fields.Datetime.context_timestamp(self, dt).strftime('%H:%M:%S')

    @staticmethod
    def _utc_ts(dt):
        """Epoch en segundos para cronómetros del lado del cliente."""
        return int(dt.replace(tzinfo=timezone.utc).timestamp()) if dt else False

    @api.model
    def js_bootstrap(self):
        """Catálogos y sesiones abiertas del supervisor, en una sola llamada."""
        Employee = self.env['hr.employee']
        planta_counts = {
            row['x_planta']: row['x_planta_count']
            for row in Employee.read_group(
                [('active', '=', True), ('x_planta', '!=', False)],
                ['x_planta'], ['x_planta'])
        }
        types = [{
            'id': t.id,
            'code': t.code,
            'name': t.name,
            'category': ('ok' if t.is_attendance
                         else 'justified' if t.justifies_absence else 'bad'),
        } for t in self.env['hmx.attendance.incidence.type'].search([])]
        open_sessions = self.search([
            ('state', '=', 'open'), ('supervisor_id', '=', self.env.uid),
        ])
        return {
            'user_name': self.env.user.name,
            'plantas': [
                {'value': value, 'label': label, 'count': planta_counts.get(value, 0)}
                for value, label in self._fields['planta'].selection
            ],
            'departments': self.env['hr.department'].search_read(
                [], ['id', 'name'], order='name'),
            'turnos': [
                {'value': value, 'label': label}
                for value, label in self._fields['turno'].selection
            ],
            'types': types,
            'open_sessions': [{
                'id': s.id,
                'name': s.name,
                'planta': s.planta or '',
                'department': s.department_id.name or '',
                'date': s.date.strftime('%d/%m/%Y'),
                'started_time': s._fmt_time(s.started_at),
                'progress': s.progress,
                'marked': s.marked_count,
                'total': s.line_count,
            } for s in open_sessions],
        }

    def js_payload(self):
        """Estado completo de la sesión para renderizar la app de captura."""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'planta': self.planta or '',
            'department': self.department_id.name or '',
            'turno': self.turno or '',
            'date': self.date.strftime('%d/%m/%Y'),
            'started_time': self._fmt_time(self.started_at),
            'started_ts': self._utc_ts(self.started_at),
            'closed_time': self._fmt_time(self.closed_at),
            'lines': [line.js_payload() for line in self.line_ids.sorted(
                key=lambda l: (l.numero_nomina or 999999, l.id))],
        }

    def js_start(self, planta, department_id, turno):
        """Crea la sesión desde la app y regresa su estado inicial."""
        session = self.create({
            'planta': planta or False,
            'department_id': department_id or False,
            'turno': turno or False,
        })
        return session.js_payload()

    def js_close(self):
        """Cierra desde la app y regresa el estado final consolidado."""
        self.ensure_one()
        self.action_close()
        return self.js_payload()


class HmxAttendanceSessionLinePayload(models.Model):
    _inherit = 'hmx.attendance.session.line'

    def js_payload(self):
        self.ensure_one()
        name = self.employee_id.name or ''
        initials = ''.join(w[0] for w in name.split()[:2]).upper()
        return {
            'id': self.id,
            'employee': name,
            'initials': initials or '?',
            'nomina': self.numero_nomina or 0,
            'maquina': self.maquina or '',
            'type_id': self.incidence_type_id.id or False,
            'type_code': self.incidence_type_id.code or '',
            'overtime': self.overtime_hours or 0.0,
            'notes': self.notes or '',
            'marked_time': self.session_id._fmt_time(self.marked_at),
            'exit_confirmed': self.exit_confirmed,
            'exit_time': self.session_id._fmt_time(self.exit_marked_at),
        }

    def js_mark(self, vals):
        """Aplica una marca desde la app y regresa la línea ya sellada."""
        self.ensure_one()
        allowed = {'incidence_type_id', 'overtime_hours', 'notes', 'maquina', 'exit_confirmed'}
        self.write({k: v for k, v in vals.items() if k in allowed})
        return self.js_payload()


class HmxAttendanceSessionLine(models.Model):
    _name = 'hmx.attendance.session.line'
    _description = 'Línea de sesión de captura de asistencia'
    _order = 'numero_nomina, id'

    session_id = fields.Many2one(
        'hmx.attendance.session', required=True, index=True, ondelete='cascade')
    session_state = fields.Selection(related='session_id.state')
    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True)
    numero_nomina = fields.Integer(
        related='employee_id.x_numero_nomina', string='Nómina', store=True)
    maquina = fields.Char('Máquina / Área')
    incidence_type_id = fields.Many2one(
        'hmx.attendance.incidence.type', 'Lista',
        help='Código de la lista de asistencia: A, F, S, PCS, PSS, V, INC, TX.')
    default_type_id = fields.Many2one(
        'hmx.attendance.incidence.type', string='Tipo sugerido')
    overtime_hours = fields.Float('T.E. (hrs)')
    notes = fields.Char('Observaciones')
    marked_at = fields.Datetime(
        'Hora del movimiento', readonly=True, copy=False,
        help='Se sella con la primera marca del supervisor sobre esta línea.')
    marked_by_id = fields.Many2one('res.users', 'Marcó', readonly=True, copy=False)
    exit_confirmed = fields.Boolean('Salida confirmada')
    exit_marked_at = fields.Datetime('Hora de salida (captura)', readonly=True, copy=False)

    _sql_constraints = [
        ('employee_session_uniq', 'unique(session_id, employee_id)',
         'El empleado ya está en la lista de esta sesión.'),
    ]

    def write(self, vals):
        stamp_fields = {'incidence_type_id', 'overtime_hours', 'notes', 'maquina'}
        now = fields.Datetime.now()
        if stamp_fields & set(vals):
            closed = self.filtered(lambda l: l.session_id.state != 'open')
            if closed:
                raise UserError(_('La sesión ya está cerrada; no se puede editar la lista.'))
            for line in self.filtered(lambda l: not l.marked_at):
                super(HmxAttendanceSessionLine, line).write({
                    'marked_at': now, 'marked_by_id': self.env.user.id})
        if vals.get('exit_confirmed'):
            vals = dict(vals, exit_marked_at=now)
        return super().write(vals)
