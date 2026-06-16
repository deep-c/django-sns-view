from base64 import b64decode
import logging
import re
import six
import requests

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from requests.exceptions import HTTPError
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from django.http import HttpResponse, HttpResponseBadRequest
from django.core.cache import caches
from django.conf import settings
from django.utils.encoding import smart_bytes


logger = logging.getLogger(__name__)

NOTIFICATION_HASH_FORMAT = u'''Message
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
'''

NOTIFICATION_HASH_FORMAT_NO_SUBJECT = u'''Message
{Message}
MessageId
{MessageId}
Timestamp
{Timestamp}
TopicArn
{TopicArn}
Type
{Type}
'''

SUBSCRIPTION_HASH_FORMAT = u'''Message
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
'''


def confirm_subscription(payload):
    """
    Confirm subscription request by making a 
    get request to the required url.
    """
    subscribe_url = payload.get('SubscribeURL')

    domain = urlparse(subscribe_url).netloc
    pattern = getattr(
        settings,
        'SNS_SUBSCRIBE_DOMAIN_REGEX',
        r"sns.[a-z0-9\-]+.amazonaws.com$"
    )
    if not re.search(pattern, domain):
        logger.error('Invalid Subscription Domain %s', subscribe_url)
        return HttpResponseBadRequest('Improper Subscription Domain')

    try:
        response = requests.get(subscribe_url)
        response.raise_for_status()
    except HTTPError as e:
        logger.error('HTTP verification Error', extra={
            'error': e,
            'sns_payload': payload,
        })
        raise e

    return HttpResponse('OK')


def verify_notification(payload):
    """
    Verify notification came from a trusted source
    Returns True if verified, False if not
    """
    pemfile = get_pemfile(payload['SigningCertURL'])
    cert = x509.load_pem_x509_certificate(smart_bytes(pemfile))
    signature = b64decode(six.b(payload['Signature']))

    if payload['Type'] == "Notification":
        if payload.get('Subject'):
            hash_format = NOTIFICATION_HASH_FORMAT
        else:
            hash_format = NOTIFICATION_HASH_FORMAT_NO_SUBJECT
    else:
        hash_format = SUBSCRIPTION_HASH_FORMAT

    message = six.b(hash_format.format(**payload))
    try:
        cert.public_key().verify(
            signature, message, padding.PKCS1v15(), hashes.SHA1())
    except InvalidSignature as e:
        logger.error('Verification of signature raised an Error: %s', e)
        return False

    return True


def get_pemfile(cert_url):
    """
    Acquire the keyfile
    SNS keys expire and Amazon does not promise they will use the same key
    for all SNS requests. So we need to keep a copy of the cert in our
    cache
    """
    key_cache = caches[getattr(settings, 'AWS_PEM_CACHE', 'default')]

    pemfile = key_cache.get(cert_url)
    if not pemfile:
        try:
            response = requests.get(cert_url)
            response.raise_for_status()
        except HTTPError as e:
            logger.error('Unable to fetch the keyfile: %s' % e)
            raise
        pemfile = response.text
        # Extract the first certificate in the file and confirm it's a valid
        # PEM certificate
        pem_bytes = smart_bytes(pemfile)
        if pem_bytes.count(b'-----BEGIN CERTIFICATE-----') != 1:
            logger.error('Invalid Certificate File: URL %s', cert_url)
            raise ValueError('Invalid Certificate File')
        try:
            x509.load_pem_x509_certificate(pem_bytes)
        except ValueError:
            logger.error('Invalid Certificate File: URL %s', cert_url)
            raise ValueError('Invalid Certificate File')

        key_cache.set(cert_url, pemfile)
    return pemfile
