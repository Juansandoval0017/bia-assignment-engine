from datetime import date

from app.models import LegacyReview


def test_legacy_review_requires_confirmation_for_provisional_owner():
    review = LegacyReview(
        registro_id=1,
        razon_social="Empresa Demo",
        estado="en_gestion",
        inferred_user_id=8,
        historical_user_ids=[8],
        activity_count=3,
        latest_activity=date(2026, 9, 16),
        classification="provisional",
        reason="un solo usuario histórico; requiere confirmación",
    )

    assert review.classification == "provisional"
    assert review.inferred_user_id == 8
