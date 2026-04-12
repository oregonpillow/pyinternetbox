from typing import Literal

from internetbox_client.utils.APIClient import APIClient


class Static(APIClient):
    """Fetch static JSON assets (settings, translations) from the gateway."""

    def settings(self) -> str:
        """Get device information"""
        return self.get("/static/settings/application.json", auth_required=False)

    def translations(self, language: Literal["en", "de", "fr", "it"] = "en") -> str:
        """Get translations"""
        return self.get(f"/static/translations/stargatev4/{language}.json", auth_required=False)
