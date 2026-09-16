from core.lifecycle_config import lifecycle_config
from integrations.mail.provider import MailProviderRegistry
from integrations.mail.smtp import SMTPMailProvider


mail_provider_registry = MailProviderRegistry()
mail_provider_registry.register(SMTPMailProvider(lifecycle_config))

__all__ = ["mail_provider_registry"]
