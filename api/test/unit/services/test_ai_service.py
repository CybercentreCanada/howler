import pytest

from howler.common.exceptions import HowlerValueError
from howler.models.lead import Lead
from howler.models.localized_label import LocalizedLabel
from howler.services import ai_service


def test_managed_lead_uses_validated_localized_label_and_preserves_primitives():
    content = "Generated triage note"
    lead = ai_service._managed_lead(content)
    model_validate_equivalent = Lead.model_validate(
        {
            "label": {"en": "AI Triage", "fr": "Triage IA"},
            "format": "markdown",
            "content": content,
            "metadata": '{"owner": "howler.ai_triage"}',
        }
    )

    assert isinstance(lead.label, LocalizedLabel)
    assert lead.label.en == "AI Triage"
    assert lead.label.fr == "Triage IA"
    assert lead == model_validate_equivalent
    assert lead.as_primitives() == model_validate_equivalent.as_primitives()
    assert Lead.model_validate(lead.as_primitives()) == lead


def test_managed_lead_constructor_preserves_validation_errors():
    invalid_payload = {
        "label": {"en": "AI Triage", "fr": "Triage IA"},
        "format": "markdown",
        "content": "",
        "metadata": '{"owner": "howler.ai_triage"}',
    }
    with pytest.raises(HowlerValueError) as validation_error:
        Lead.model_validate(invalid_payload)

    with pytest.raises(HowlerValueError) as constructor_error:
        ai_service._managed_lead("")

    assert type(constructor_error.value) is type(validation_error.value)
