from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from app.assignment import preview_assignments
from app.data_loader import load_absences, load_leads, load_users
from app.snowflake_repository import SnowflakeRepository


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_demo_data():
    return (
        load_users(DATA_DIR / "usuarios.csv"),
        load_leads(DATA_DIR / "registros.csv"),
        load_absences(DATA_DIR / "ausencias.csv"),
    )


def _render_assignments(assignments, sellers) -> None:
    assignment_by_lead = {assignment.lead_id: assignment for assignment in assignments}
    rows = []
    for assignment in assignments:
        seller = sellers.get(assignment.user_id)
        rows.append(
            {
                "Registro": assignment.lead_id,
                "Vendedor": seller.nombre if seller else "Sin asignar",
                "Puntaje": assignment.score,
                "Razón principal": assignment.reasons[0],
            }
        )

    assigned_count = sum(item.user_id is not None for item in assignments)
    metric_one, metric_two = st.columns(2)
    metric_one.metric("Asignables", assigned_count)
    metric_two.metric("Sin asignar", len(assignments) - assigned_count)
    st.subheader("Resultado de la previsualización")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not assignments:
        return
    st.subheader("Detalle de una asignación")
    detail_id = st.selectbox("Registro", options=list(assignment_by_lead))
    detail = assignment_by_lead[detail_id]
    st.write("**Razones:**", "; ".join(detail.reasons))
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Vendedor": sellers[candidate.user_id].nombre,
                    "Puntaje": candidate.score,
                    "Razones": "; ".join(candidate.reasons),
                }
                for candidate in detail.candidates
                if candidate.user_id in sellers
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    st.set_page_config(page_title="Bia Assignment Engine", layout="wide")
    st.title("Motor de asignación comercial")

    if message := st.session_state.pop("migration_message", None):
        st.success(message)

    with st.sidebar:
        st.header("Configuración")
        source = st.radio("Fuente de datos", ["Snowflake", "CSV local"])
        execution_date = st.date_input("Fecha de ejecución", value=date.today())
        executed_by = st.text_input("Usuario operador", value="demo.operator")
        approved_by = st.text_input("Usuario aprobador", value=executed_by)
        method = st.selectbox(
            "Método de asignación",
            options=["weighted_score", "balanced", "round_robin"],
            format_func=lambda value: {
                "weighted_score": "Puntaje ponderado",
                "balanced": "Balanceado por carga",
                "round_robin": "Round-robin con capacidad",
            }[value],
        )
        if method == "weighted_score":
            weights = {
                "zone": st.number_input("Peso zona", 0.0, 1.0, 0.35, 0.05),
                "segment": st.number_input("Peso segmento", 0.0, 1.0, 0.25, 0.05),
                "capacity": st.number_input("Peso capacidad", 0.0, 1.0, 0.25, 0.05),
                "balance": st.number_input("Peso balance", 0.0, 1.0, 0.15, 0.05),
            }
            st.caption(f"Suma de pesos: {sum(weights.values()):.2f}")
        else:
            weights = {"zone": 0.35, "segment": 0.25, "capacity": 0.25, "balance": 0.15}
            st.info("Este método no utiliza pesos configurables.")

    repository = None
    try:
        if source == "Snowflake":
            repository = SnowflakeRepository()
            repository.expire_runs()
            operational_data = repository.load_operational_data()
            legacy_reviews = repository.load_legacy_review()
            users, all_leads, absences = (
                operational_data.users,
                operational_data.leads,
                operational_data.absences,
            )
            current_load = operational_data.current_load
        else:
            users, all_leads, absences = load_demo_data()
            current_load = {}
            legacy_reviews = []
    except Exception as error:
        st.error(f"No fue posible cargar la fuente seleccionada: {error}")
        st.stop()

    pending_leads = [lead for lead in all_leads if lead.estado == "nuevo"]
    sellers = {user.id: user for user in users if user.rol.casefold() == "vendedor"}

    if source == "Snowflake" and legacy_reviews:
        st.subheader("Conciliación histórica")
        st.caption(
            "Estas asignaciones son provisionales: actividad histórica no equivale "
            "automáticamente a propietario actual."
        )
        review_rows = [
            {
                "Registro": review.registro_id,
                "Empresa": review.razon_social,
                "Estado": review.estado,
                "Usuario histórico": review.inferred_user_id,
                "Actividades": review.activity_count,
                "Clasificación": review.classification,
            }
            for review in legacy_reviews
        ]
        st.dataframe(pd.DataFrame(review_rows), use_container_width=True, hide_index=True)
        confirmed_ids = st.multiselect(
            "Registros históricos a confirmar",
            options=[review.registro_id for review in legacy_reviews],
            default=[],
            key="legacy_confirmed_ids",
        )
        if st.button("Confirmar históricos seleccionados"):
            run_id, count = repository.save_legacy_confirmations(
                legacy_reviews, confirmed_ids, executed_by
            )
            st.session_state.pop("legacy_confirmed_ids", None)
            st.session_state["migration_message"] = (
                f"Migración histórica #{run_id}: {count} registros confirmados."
            )
            st.rerun()
    selected_ids = st.multiselect(
        "Registros a previsualizar",
        options=[lead.id for lead in pending_leads],
        default=[lead.id for lead in pending_leads],
    )
    selected_leads = [lead for lead in pending_leads if lead.id in selected_ids]
    preview_context = {
        "source": source,
        "execution_date": str(execution_date),
        "selected_ids": tuple(selected_ids),
        "method": method,
        "weights": tuple(sorted(weights.items())),
    }
    previous_context = st.session_state.get("preview_context")
    if st.session_state.get("assignments") and previous_context != preview_context:
        if source == "Snowflake" and st.session_state.get("run_status") == "previewed":
            repository.cancel_run(st.session_state["run_id"])
        for key in ("assignments", "run_id", "run_status", "preview_context"):
            st.session_state.pop(key, None)
        st.warning("La configuración cambió. Debes generar una nueva previsualización.")

    st.subheader("Registros pendientes")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": lead.id,
                    "Empresa": lead.razon_social,
                    "Sector": lead.sector or "Sin dato",
                    "Zona": lead.zona or "Sin dato",
                    "Ingresos": lead.ingresos_estimados,
                    "Creación": lead.fecha_creacion,
                }
                for lead in selected_leads
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Previsualizar y preparar borrador", type="primary"):
        if source == "Snowflake" and st.session_state.get("run_status") == "previewed":
            repository.cancel_run(st.session_state["run_id"])
        assignments = preview_assignments(
            selected_leads,
            users,
            absences,
            current_load,
            execution_date,
            method,
            weights,
        )
        st.session_state["assignments"] = assignments
        st.session_state["preview_context"] = preview_context
        if source == "Snowflake":
            run_id = repository.create_run(
                method=method,
                parameters={"version": "0.1.0", "weights": weights},
                executed_by=executed_by,
                execution_date=execution_date,
            )
            repository.save_decisions(run_id, assignments)
            st.session_state["run_id"] = run_id
            st.session_state["run_status"] = "previewed"
            st.success(f"Borrador #{run_id} creado. Expira en 24 horas.")

    assignments = st.session_state.get("assignments")
    if not assignments:
        return
    _render_assignments(assignments, sellers)

    if source != "Snowflake":
        st.info("El modo CSV permite probar, pero no persiste ejecuciones.")
        return

    run_id = st.session_state.get("run_id")
    status = st.session_state.get("run_status")
    if status == "previewed":
        approve, cancel = st.columns(2)
        if approve.button("Aprobar borrador", type="primary"):
            repository.approve_run(run_id, approved_by)
            st.session_state["run_status"] = "approved"
            st.rerun()
        if cancel.button("Cancelar borrador"):
            repository.cancel_run(run_id)
            st.session_state.clear()
            st.rerun()
    elif status == "approved":
        if st.button("Ejecutar asignación aprobada", type="primary"):
            repository.mark_run_executed(run_id)
            st.session_state["run_status"] = "executed"
            st.success(f"Corrida #{run_id} ejecutada correctamente.")
    elif status == "executed":
        st.success(f"Corrida #{run_id} ejecutada y auditada en Snowflake.")


if __name__ == "__main__":
    main()
