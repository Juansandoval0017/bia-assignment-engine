from os import environ

from dotenv import load_dotenv


def get_setting(name: str, default: str | None = None) -> str | None:
    load_dotenv()
    value = environ.get(name)
    if value:
        return value
    try:
        import streamlit as st

        return st.secrets.get(name, default)
    except Exception:
        return default
