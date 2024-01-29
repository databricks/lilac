"""Dataset formats are inferred from the dataset schema."""


from .default_formats import register_default_formats
from .openai_json import OpenAIConversationJSON, OpenAIJSON
from .openchat import OpenChat
from .sharegpt import ShareGPT

register_default_formats()

__all__ = ['ShareGPT', 'OpenChat', 'OpenAIJSON', 'OpenAIConversationJSON']
