"""Config flow."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers import selector

from .const import DOMAIN


class ChauffageManagerFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="Chauffage Manager",
                data={"persons": user_input.get("persons", [])},
            )
        schema = vol.Schema(
            {
                vol.Optional("persons", default=[]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="person", multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
