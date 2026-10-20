"""Google-signed id tokens from Cloud Scheduler: signature, expiry and audience are checked here."""

from collections.abc import Callable


def google_token_verifier(audience: str) -> Callable[[str], dict]:
    from google.auth.transport import requests
    from google.oauth2 import id_token

    request = requests.Request()

    def verify(token: str) -> dict:
        return id_token.verify_oauth2_token(token, request, audience=audience)

    return verify
