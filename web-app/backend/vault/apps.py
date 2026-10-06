from django.apps import AppConfig


class VaultConfig(AppConfig):
    name = "vault"

    def ready(self) -> None:
        from vault import clock

        clock.warn_if_half_configured()
