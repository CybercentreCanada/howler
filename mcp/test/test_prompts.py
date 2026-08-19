from collections.abc import Callable

from howler_mcp.prompts import register_prompts


class _CaptureMCP:
    def __init__(self):
        self.prompts: dict[str, Callable[[], str]] = {}

    def prompt(self, name: str):
        def decorator(prompt):
            self.prompts[name] = prompt
            return prompt

        return decorator


def test_register_prompts_registers_and_returns_guidance():
    mcp = _CaptureMCP()
    register_prompts(mcp)

    expected_opening = {
        "whoami": "Use whoami",
        "list_assigned_hits": "Use list_assigned_hits",
        "add_comment_to_hit": "Use add_comment_to_hit",
        "get_field_values": "Use get_field_values",
        "get_hit_fields": "Use get_hit_fields",
        "get_label_set_options": "Use get_label_set_options",
        "add_label_to_hit": "Use add_label_to_hit",
        "create_dossier": "Use create_dossier",
        "create_dossier_for_hit": "Use create_dossier_for_hit",
        "update_dossier": "Use update_dossier",
        "_verify_leads": "Use _verify_leads",
        "_verify_pivots": "Use _verify_pivots",
        "lucene_query": "Use lucene_query",
    }

    assert set(mcp.prompts) == set(expected_opening)
    for name, opening in expected_opening.items():
        assert mcp.prompts[name]().startswith(opening)
