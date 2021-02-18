from base64 import b64decode
import logging
import re
import requests
import pem

from OpenSSL import crypto
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
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, pemfile)
    signature = b64decode(payload['Signature'].encode('utf-8'))

    if payload['Type'] == "Notification":
        if payload.get('Subject'):
            hash_format = NOTIFICATION_HASH_FORMAT
        else:
            hash_format = NOTIFICATION_HASH_FORMAT_NO_SUBJECT
    else:
        hash_format = SUBSCRIPTION_HASH_FORMAT

    try:
        crypto.verify(
            cert, signature, hash_format.format(**payload).encode('utf-8'), 'sha1')
    except crypto.Error as e:
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
        certificates = pem.parse(smart_bytes(pemfile))
        # A proper certificate file will contain 1 certificate
        if len(certificates) != 1:
            logger.error('Invalid Certificate File: URL %s', cert_url)
            raise ValueError('Invalid Certificate File')

        key_cache.set(cert_url, pemfile)
    return pemfile
