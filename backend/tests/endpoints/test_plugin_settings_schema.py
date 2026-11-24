"""What the settings endpoints accept before the manifest sees it.

The body schema is checked on its own here: a field that holds a list of entries
would otherwise be refused by the request model, before any of the manifest's
own rules ran, and the answer would say nothing useful about why.
"""

from endpoints.responses.plugin import PluginSettingsSchema


def test_a_body_may_carry_a_list_of_entries() -> None:
    body = PluginSettingsSchema(
        values={
            "handheld": "e4394fe4",
            "pc_setups": [
                {"name": "Desktop", "cpu": "5900x", "memory": 32, "os": "LINUX"}
            ],
        }
    )

    assert body.values["pc_setups"] == [
        {"name": "Desktop", "cpu": "5900x", "memory": 32, "os": "LINUX"}
    ]


def test_a_body_may_carry_a_scalar() -> None:
    body = PluginSettingsSchema(values={"enabled": True, "limit": 5})

    assert body.values == {"enabled": True, "limit": 5}
