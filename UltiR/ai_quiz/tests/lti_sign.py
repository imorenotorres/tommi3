"""Build a signed LTI 1.1 launch form, the way Moodle would send it.

Lets the tests go through the real signature check in UltiR/lti_common.py
instead of a test route. Standard library only. Synthetic identities only.
"""

import hashlib
import hmac
import secrets
import time
import urllib.parse
from base64 import b64encode


def _enc(value) -> str:
    return urllib.parse.quote(str(value), safe="")


def signature(method: str, url: str, params: dict, consumer_secret: str) -> str:
    """OAuth 1.0a HMAC-SHA1 signature over every param except oauth_signature."""
    pairs = sorted((k, v) for k, v in params.items() if k != "oauth_signature")
    param_string = "&".join(f"{_enc(k)}={_enc(v)}" for k, v in pairs)
    base_string = "&".join([method.upper(), _enc(url), _enc(param_string)])
    signing_key = _enc(consumer_secret) + "&"
    digest = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    return b64encode(digest).decode()


def sign_launch(
    url: str,
    consumer_key: str,
    consumer_secret: str,
    *,
    roles: str = "Learner",
    user_id: str = "synthetic-user-1",
    context_id: str = "synthetic-course-1",
    context_title: str = "Synthetic course",
    resource_link_id: str = "synthetic-link-1",
    name: str = "Synthetic User",
    email: str = "synthetic.user@example.invalid",
    timestamp: int | None = None,
    nonce: str | None = None,
    omit: tuple = (),
) -> dict:
    """Return the full form body for a basic LTI 1.1 launch, signature included.

    `omit` names fields to leave out before signing, for a launch that lacks one (a correct signature
    over a form without `context_id`, as a tool opened from outside any course would send).
    """
    params = {
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "resource_link_id": resource_link_id,
        "user_id": user_id,
        "roles": roles,
        "context_id": context_id,
        "context_title": context_title,
        "lis_person_name_full": name,
        "lis_person_contact_email_primary": email,
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_timestamp": str(int(time.time()) if timestamp is None else timestamp),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_version": "1.0",
    }
    for field in omit:
        del params[field]
    params["oauth_signature"] = signature("POST", url, params, consumer_secret)
    return params
