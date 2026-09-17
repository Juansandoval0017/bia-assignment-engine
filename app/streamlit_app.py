from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from app.assignment import preview_assignments
from app.data_loader import load_absences, load_leads, load_users


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_demo_data():
    users = load_users(DATA_DIR / "usuarios.csv")
    leads = load_leads(DATA_DIR / "registros.csv")
    absences = load_absences(DATA_DIR / "ausencias.csv")
    return users, leads, absences


def main() -> None:
    st.set_page_config(page_title="Bia Assignment Engine", layout="wide")
    st.title("Motor de asignación comercial")
    st.caption("Previsualización determinística sobre los datos locales del reto")

    try:
        users, all_leads, absences = load_demo_data()
    except FileNotFoundError:
        st.error("No se encontraron los CSV locales en la carpeta data/.")
        st.stop()

    pending_leads = [lead for lead in all_leads if lead.estado == "nuevo"]
    sellers = {user.id: user for user in users if user.rol.casefold() == "vendedor"}

    with st.sidebar:
        st.header("Configuración")
        execution_date = st.date_input("Fecha de ejecución", value=date.today())
        selected_ids = st.multiselect(
            "Registros a previsualizar",
            options=[lead.id for lead in pending_leads],
            default=[lead.id for lead in pending_leads],
        )
        st.info("El método actual es puntaje ponderado por zona, segmento y capacidad.")

    selected_leads = [lead for lead in pending_leads if lead.id in selected_ids]
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

    if not st.button("Previsualizar asignaciones", type="primary"):
        return

    assignments = preview_assignments(
        leads=selected_leads,
        users=users,
        absences=absences,
        execution_date=execution_date,
    )
    assignment_by_lead = {assignment.lead_id: assignment for assignment in assignments}
    rows = []
    for lead in selected_leads:
        assignment = assignment_by_lead[lead.id]
        seller = sellers.get(assignment.user_id)
        rows.append(
            {
                "Registro": lead.id,
                "Empresa": lead.razon_social,
                "Vendedor": seller.nombre if seller else "Sin asignar",
                "Puntaje": assignment.score,
                "Razón principal": assignment.reasons[0],
            }
        )

    assigned_count = sum(assignment.user_id is not None for assignment in assignments)
    metric_one, metric_two = st.columns(2)
    metric_one.metric("Asignables", assigned_count)
    metric_two.metric("Sin asignar", len(assignments) - assigned_count)

    st.subheader("Resultado de la previsualización")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Detalle de una asignación")
    detail_id = st.selectbox("Registro", options=[lead.id for lead in selected_leads])
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


if __name__ == "__main__":
    main()
