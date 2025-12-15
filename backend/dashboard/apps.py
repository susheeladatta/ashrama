from django.apps import AppConfig

class DashboardConfig(AppConfig):
    name = "dashboard"
    # Prefix with "0." so it appears at the top of the sidebar
    verbose_name = "0. Dashboard"
