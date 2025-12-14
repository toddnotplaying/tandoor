import socket
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Func
from ipaddress import ip_address

from recipes import settings


class Round(Func):
    function = 'ROUND'
    template = '%(function)s(%(expressions)s, 0)'


def str2bool(v):
    if isinstance(v, bool) or v is None:
        return v
    else:
        return v.lower() in ("yes", "true", "1")


"""
validates an url that is supposed to be imported
checks that the protocol used is http(s) and that no local address is accessed
@:param url to test
@:return true if url is valid, false otherwise
"""


def validate_import_url(url):
    try:
        validator = URLValidator(schemes=['http', 'https'])
        validator(url)
    except ValidationError:
        # if schema is not http or https, consider url invalid
        return False

    # resolve IP address of url
    try:
        url_ip_address = ip_address(str(socket.gethostbyname(urlparse(url).hostname)))
    except (ValueError, AttributeError, TypeError, Exception) as e:
        # if ip cannot be parsed, consider url invalid
        return False

    # validate that IP is neither private nor any other special address
    return not any([url_ip_address.is_private, url_ip_address.is_reserved, url_ip_address.is_loopback,  url_ip_address.is_multicast, url_ip_address.is_link_local, ])


# Constants for secure image fetching
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
IMAGE_FETCH_TIMEOUT = 15  # seconds
MAX_REDIRECTS = 3  # Maximum number of redirects to follow


def secure_image_fetch(url: str, _redirect_count: int = 0) -> tuple:
    """
    Securely fetch image from URL with SSRF protection, timeout, and size limits.

    Security measures:
    - SSRF protection via validate_import_url() (blocks private/reserved IPs)
    - 15 second timeout to prevent DoS via slow servers
    - 10MB size limit to prevent memory exhaustion
    - Content-type validation (must be image/*)
    - No automatic redirect following (prevents redirect to private IPs)
    - Maximum redirect limit to prevent infinite redirect loops
    - Streaming download to enforce size limit during transfer

    Args:
        url: The URL to fetch the image from
        _redirect_count: Internal counter for tracking redirect depth (do not pass externally)

    Returns:
        tuple: (content_bytes, content_type) - The image data and its MIME type

    Raises:
        ValueError: If URL fails validation, content-type is invalid, size exceeded,
                    or too many redirects
        requests.exceptions.Timeout: If request times out
        requests.exceptions.RequestException: For other network errors
    """
    import requests

    # Check redirect limit
    if _redirect_count > MAX_REDIRECTS:
        raise ValueError(f"Too many redirects (max: {MAX_REDIRECTS})")

    # Validate URL for SSRF
    if not validate_import_url(url):
        raise ValueError("URL failed security validation (private/reserved IP or invalid format)")

    try:
        response = requests.get(
            url,
            timeout=IMAGE_FETCH_TIMEOUT,
            stream=True,
            allow_redirects=False,  # Prevent redirect to private IPs
            headers={"User-Agent": "Tandoor/1.0"}
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise ValueError(f"Request timed out after {IMAGE_FETCH_TIMEOUT} seconds")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}")

    # Handle redirects manually with validation
    if response.status_code in (301, 302, 303, 307, 308):
        redirect_url = response.headers.get('Location')
        if redirect_url:
            if not validate_import_url(redirect_url):
                raise ValueError("Redirect URL failed security validation")
            # Recursive call for redirect with incremented counter
            return secure_image_fetch(redirect_url, _redirect_count + 1)
        raise ValueError("Redirect response missing Location header")

    # Validate content-type
    content_type = response.headers.get('content-type', '')
    if not content_type.startswith('image/'):
        raise ValueError(f"Invalid content-type: {content_type}. Expected image/*")

    # Check content-length header if available
    content_length = response.headers.get('content-length')
    if content_length:
        try:
            if int(content_length) > MAX_IMAGE_SIZE:
                raise ValueError(f"Image too large: {content_length} bytes (max: {MAX_IMAGE_SIZE})")
        except (ValueError, TypeError):
            pass  # Invalid content-length header, rely on streaming check

    # Stream download directly to BytesIO with size guard (reduces peak memory vs concatenation)
    import io
    buffer = io.BytesIO()
    downloaded = 0
    for chunk in response.iter_content(chunk_size=8192):
        downloaded += len(chunk)
        if downloaded > MAX_IMAGE_SIZE:
            response.close()
            buffer.close()
            raise ValueError(
                f"Image exceeded max size during download. "
                f"Limit: {MAX_IMAGE_SIZE // (1024*1024)}MB ({MAX_IMAGE_SIZE:,} bytes)"
            )
        buffer.write(chunk)

    content = buffer.getvalue()
    buffer.close()
    return content, content_type
