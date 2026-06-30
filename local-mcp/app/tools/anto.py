from secrets import choice

from app.schemas.anto import AntoQuote
from app.utils.http_client import get_anto_quotes


def get_random_anto_quote() -> AntoQuote:
    quotes = [quote.strip() for quote in get_anto_quotes() if quote.strip()]
    if not quotes:
        raise ValueError("No Anto quotes are available")

    return AntoQuote(quote=choice(quotes))
