from core.lifecycle_config import lifecycle_config
from integrations.mail.provider import MailProviderRegistry
from integrations.mail.rusender import RuSenderMailProvider
from integrations.mail.smtp import SMTPMailProvider


mail_provider_registry = MailProviderRegistry()
mail_provider_registry.register(SMTPMailProvider(lifecycle_config))
mail_provider_registry.register(RuSenderMailProvider(lifecycle_config))

__all__ = ["mail_provider_registry"]
