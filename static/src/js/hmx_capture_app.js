/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const SESSION = "hmx.attendance.session";
const LINE = "hmx.attendance.session.line";

/**
 * Captura de Asistencia — aplicación de piso para supervisores.
 *
 * Pantallas: inicio (reanudar sesión o abrir una nueva eligiendo la
 * estancia), captura (lista viva de empleados con marcado de un toque,
 * buscador, pestañas, pase de salida y cronómetro) y cierre (resumen
 * consolidado). Toda la lógica de sellos de hora vive en el servidor;
 * aquí solo se refleja.
 */
export class HmxCaptureApp extends Component {
    static template = "empleados_hmx.CaptureApp";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            view: "loading", // loading | start | capture | done
            bootstrap: null,
            draft: { planta: false, department_id: false, turno: "dia" },
            session: null,
            filter: "",
            tab: "all", // all | pending | marked
            exitMode: false,
            busy: {}, // line id -> true mientras guarda
            confirmBulk: false,
            showCloseModal: false,
            closing: false,
            now: Date.now(),
        });

        this._tick = setInterval(() => (this.state.now = Date.now()), 1000);
        onWillDestroy(() => clearInterval(this._tick));
        onWillStart(() => this.loadBootstrap());
    }

    // ------------------------------------------------------------------
    // Carga y navegación
    // ------------------------------------------------------------------
    async loadBootstrap() {
        this.state.bootstrap = await this.orm.call(SESSION, "js_bootstrap", []);
        this.state.view = "start";
    }

    async resumeSession(sessionId) {
        this.state.session = await this.orm.call(SESSION, "js_payload", [[sessionId]]);
        this.state.view = "capture";
    }

    async startSession() {
        const d = this.state.draft;
        if (!d.planta && !d.department_id) {
            this.notification.add("Elige una planta o un departamento para abrir la sesión.", {
                type: "warning",
            });
            return;
        }
        try {
            this.state.session = await this.orm.call(SESSION, "js_start", [
                d.planta,
                d.department_id ? parseInt(d.department_id) : false,
                d.turno,
            ]);
            this.state.view = "capture";
            this.state.tab = "all";
            this.state.filter = "";
        } catch (error) {
            // El error de Odoo (p. ej. estancia sin empleados) ya se muestra
            // en su diálogo estándar; aquí solo evitamos romper el flujo.
        }
    }

    async backToStart() {
        this.state.session = null;
        this.state.exitMode = false;
        this.state.view = "loading";
        await this.loadBootstrap();
    }

    // ------------------------------------------------------------------
    // Getters de presentación
    // ------------------------------------------------------------------
    get clock() {
        return new Date(this.state.now).toLocaleTimeString("es-MX", { hour12: false });
    }

    get elapsed() {
        const s = this.state.session;
        if (!s || !s.started_ts) {
            return "00:00:00";
        }
        let secs = Math.max(0, Math.floor(this.state.now / 1000) - s.started_ts);
        const h = String(Math.floor(secs / 3600)).padStart(2, "0");
        const m = String(Math.floor((secs % 3600) / 60)).padStart(2, "0");
        const ss = String(secs % 60).padStart(2, "0");
        return `${h}:${m}:${ss}`;
    }

    get markedCount() {
        return this.state.session.lines.filter((l) => l.type_id).length;
    }

    get totalCount() {
        return this.state.session.lines.length;
    }

    get progressPct() {
        return this.totalCount ? Math.round((100 * this.markedCount) / this.totalCount) : 0;
    }

    get ringStyle() {
        return `background: conic-gradient(#4caf7d ${this.progressPct * 3.6}deg, rgba(255,255,255,0.18) 0deg);`;
    }

    get filteredLines() {
        const term = this.state.filter.trim().toLowerCase();
        return this.state.session.lines.filter((line) => {
            if (this.state.tab === "pending" && line.type_id) {
                return false;
            }
            if (this.state.tab === "marked" && !line.type_id) {
                return false;
            }
            if (!term) {
                return true;
            }
            return (
                line.employee.toLowerCase().includes(term) ||
                String(line.nomina).includes(term) ||
                line.maquina.toLowerCase().includes(term)
            );
        });
    }

    get summary() {
        const byCode = {};
        for (const line of this.state.session.lines) {
            const code = line.type_code || "—";
            byCode[code] = (byCode[code] || 0) + 1;
        }
        return Object.entries(byCode)
            .sort((a, b) => b[1] - a[1])
            .map(([code, count]) => ({ code, count }));
    }

    get pendingNames() {
        return this.state.session.lines.filter((l) => !l.type_id).map((l) => l.employee);
    }

    typeMeta(typeId) {
        return this.state.bootstrap.types.find((t) => t.id === typeId);
    }

    avatarHue(line) {
        let hash = 0;
        for (const ch of line.employee) {
            hash = (hash * 31 + ch.charCodeAt(0)) % 360;
        }
        return `background: hsl(${hash}, 42%, 38%);`;
    }

    // ------------------------------------------------------------------
    // Captura
    // ------------------------------------------------------------------
    _replaceLine(fresh) {
        const lines = this.state.session.lines;
        const index = lines.findIndex((l) => l.id === fresh.id);
        if (index !== -1) {
            lines[index] = fresh;
        }
    }

    async _mark(line, vals) {
        if (this.state.session.state !== "open" || this.state.busy[line.id]) {
            return;
        }
        this.state.busy[line.id] = true;
        try {
            const fresh = await this.orm.call(LINE, "js_mark", [[line.id], vals]);
            this._replaceLine(fresh);
        } finally {
            this.state.busy[line.id] = false;
        }
    }

    async tapType(line, type) {
        const value = line.type_id === type.id ? false : type.id;
        await this._mark(line, { incidence_type_id: value });
    }

    async stepOvertime(line, delta) {
        const value = Math.max(0, Math.round((line.overtime + delta) * 2) / 2);
        await this._mark(line, { overtime_hours: value });
    }

    async setNotes(line, ev) {
        const value = ev.target.value.trim();
        if (value !== line.notes) {
            await this._mark(line, { notes: value });
        }
    }

    async setMaquina(line, ev) {
        const value = ev.target.value.trim();
        if (value !== line.maquina) {
            await this._mark(line, { maquina: value });
        }
    }

    async toggleExit(line) {
        if (line.exit_confirmed) {
            return; // la salida confirmada no se desconfirma desde la app
        }
        await this._mark(line, { exit_confirmed: true });
    }

    async bulkAttendance() {
        if (!this.state.confirmBulk) {
            this.state.confirmBulk = true;
            setTimeout(() => (this.state.confirmBulk = false), 3500);
            return;
        }
        this.state.confirmBulk = false;
        const typeA = this.state.bootstrap.types.find((t) => t.code === "A");
        const pending = this.state.session.lines.filter((l) => !l.type_id);
        if (!typeA || !pending.length) {
            return;
        }
        await this.orm.write(LINE, pending.map((l) => l.id), {
            incidence_type_id: typeA.id,
        });
        this.state.session = await this.orm.call(SESSION, "js_payload", [
            [this.state.session.id],
        ]);
        this.notification.add(`${pending.length} empleados marcados con asistencia.`, {
            type: "success",
        });
    }

    // ------------------------------------------------------------------
    // Cierre
    // ------------------------------------------------------------------
    openCloseModal() {
        this.state.showCloseModal = true;
    }

    async confirmClose() {
        if (this.state.closing) {
            return;
        }
        this.state.closing = true;
        try {
            this.state.session = await this.orm.call(SESSION, "js_close", [
                [this.state.session.id],
            ]);
            this.state.showCloseModal = false;
            this.state.view = "done";
        } catch (error) {
            this.state.showCloseModal = false;
        } finally {
            this.state.closing = false;
        }
    }
}

registry.category("actions").add("hmx_attendance_capture", HmxCaptureApp);
