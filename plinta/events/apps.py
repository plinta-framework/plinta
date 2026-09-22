from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "plinta.events"
    label = "plinta_events"     # prefixed: a consumer may have their own `events` app
