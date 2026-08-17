/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Selector de un toque para el código de lista de asistencia.
 *
 * Sustituye el dropdown many2one por una fila de píldoras (A, F, S, PCS,
 * PSS, V, INC, TX) para que el supervisor capture a cada empleado con un
 * solo clic, igual que palomea la lista en papel. El catálogo se carga una
 * sola vez por sesión de navegador.
 */
export class HmxIncidenceSelector extends Component {
    static template = "empleados_hmx.HmxIncidenceSelector";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        onWillStart(async () => {
            if (!HmxIncidenceSelector.catalog) {
                HmxIncidenceSelector.catalog = await this.orm.searchRead(
                    "hmx.attendance.incidence.type",
                    [["active", "=", true]],
                    ["id", "code", "name", "is_attendance", "justifies_absence"],
                    { order: "sequence, id" }
                );
            }
            this.types = HmxIncidenceSelector.catalog;
        });
    }

    get selectedId() {
        const value = this.props.record.data[this.props.name];
        return value ? value[0] : false;
    }

    get isClosed() {
        // La captura de un toque se bloquea solo cuando la sesión ya cerró;
        // no depende del modo edición de la fila (patrón de boolean_toggle).
        const state = this.props.record.data.session_state;
        return state !== undefined && state !== "open";
    }

    pillClass(type) {
        const classes = ["hmx-pill"];
        if (type.id === this.selectedId) {
            classes.push("hmx-pill-selected");
        }
        if (type.is_attendance) {
            classes.push("hmx-pill-ok");
        } else if (type.justifies_absence) {
            classes.push("hmx-pill-justified");
        } else {
            classes.push("hmx-pill-bad");
        }
        return classes.join(" ");
    }

    async select(type) {
        if (this.isClosed) {
            return;
        }
        // Volver a tocar la misma píldora desmarca la línea.
        const value =
            type.id === this.selectedId ? false : [type.id, `${type.code} - ${type.name}`];
        await this.props.record.update({ [this.props.name]: value });
    }
}

registry.category("fields").add("hmx_incidence_selector", {
    component: HmxIncidenceSelector,
    supportedTypes: ["many2one"],
});
