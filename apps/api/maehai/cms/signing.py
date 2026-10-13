"""Preview links for a campaign that is not live yet: a signed id that expires after 30 minutes."""
from django.core import signing

SALT = "maehai.cms.campaign-preview"
MAX_AGE = 30 * 60


def make_preview_token(campaign_id: int) -> str:
    return signing.dumps(campaign_id, salt=SALT)


def read_preview_token(token: str) -> int | None:
    try:
        return int(signing.loads(token, salt=SALT, max_age=MAX_AGE))
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        return None
