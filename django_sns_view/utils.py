from functools import lru_cache
import logging
import re

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.encoding import smart_bytes
from requests.exceptions import HTTPError
import requests

from .types import AnySNSPayload, SubscriptionConfirmation

logger = logging.getLogger(__name__)

NOTIFICATION_HASH_FORMAT = """Message
{Message}
MessageId
{MessageId}
Subject
{Subject}
Timestamp
{Timestamp}
TopicArn
{TopicArn}
Type
{Type}
"""

NOTIFICATION_HASH_FORMAT_NO_SUBJECT = """Message
{Message}
MessageId
{MessageId}
Timestamp
{Timestamp}
TopicArn
{TopicArn}
Type
{Type}
"""

SUBSCRIPTION_HASH_FORMAT = """Message
{Message}
MessageId
{MessageId}
SubscribeURL
{SubscribeURL}
Timestamp
{Timestamp}
Token
{Token}
TopicArn
{TopicArn}
Type
{Type}
"""


def confirm_subscription(payload: SubscriptionConfirmation) -> HttpResponse:
    """
    Confirm subscription request by making a
    get request to the required url.
    """
    pattern = getattr(
        settings,
        "SNS_SUBSCRIBE_DOMAIN_REGEX",
        r"sns.[a-z0-9\-]+.amazonaws.com$",
    )
    if not payload.SubscribeURL.host or not re.search(
        pattern, payload.SubscribeURL.host
    ):
        logger.error("Invalid Subscription Domain %s", payload.SubscribeURL)
        return HttpResponseBadRequest("Improper Subscription Domain")

    try:
        response = requests.get(str(payload.SubscribeURL))
        response.raise_for_status()
    except HTTPError as e:
        logger.error(
            "HTTP verification Error",
            extra={
                "error": e,
                "sns_payload": payload,
            },
        )
        raise e

    return HttpResponse("OK")


def verify_notification(payload: AnySNSPayload) -> bool:
    """
    Verify notification came from a trusted source
    Returns True if verified, False if not
    """
    cert = get_x509_cert(str(payload.SigningCertURL))
    public_key = cert.public_key()
    if payload.Type == "Notification":
        if payload.Subject is not None:
            hash_format = NOTIFICATION_HASH_FORMAT
        else:
            hash_format = NOTIFICATION_HASH_FORMAT_NO_SUBJECT
    else:
        hash_format = SUBSCRIPTION_HASH_FORMAT
    message = hash_format.format(**payload.model_dump()).encode("utf-8")

    hash_type: hashes.SHA1 | hashes.SHA256
    if payload.SignatureVersion == "1":
        hash_type = hashes.SHA1()
    elif payload.SignatureVersion == "2":
        hash_type = hashes.SHA256()
    else:
        raise ValueError("Unknown SignatureVersion: %s" % payload.SignatureVersion)
    pss = padding.PKCS1v15()
    try:
        if not isinstance(public_key, RSAPublicKey):
            raise ValueError("Unknown key type: %s" % public_key)
        public_key.verify(payload.Signature, message, pss, hash_type)
    except InvalidSignature as e:
        logger.error("Verification of signature raised an Error: %s", e)
        return False
    return True


@lru_cache(maxsize=128)
def get_x509_cert(cert_url: str) -> x509.Certificate:
    """
    Acquire the keyfile
    SNS keys expire and Amazon does not promise they will use the same key
    for all SNS requests. So we need to keep a copy of the cert in our
    cache
    """
    try:
        response = requests.get(cert_url)
        response.raise_for_status()
    except HTTPError as e:
        logger.error("Unable to fetch the keyfile: %s" % e)
        raise
    pemfile = smart_bytes(response.text)
    # Extract the first certificate in the file and confirm it's a valid
    # PEM certificate
    cert = x509.load_pem_x509_certificate(pemfile)
    return cert
