from django.apps import AppConfig

class PaperlessMediaConfig(AppConfig):
    name = "paperless_media"

    def ready(self):
        from documents.signals import document_consumer_declaration
        from paperless_media.signals import media_consumer_declaration
        import paperless_media.signals

        document_consumer_declaration.connect(media_consumer_declaration)

        AppConfig.ready(self)
