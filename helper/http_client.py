"""HTTPS transport restricted to known publishers and pinned public addresses."""

import ipaddress
import socket
import threading
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import HTTPError as Urllib3HTTPError

ALLOWED_HOSTS = frozenset({
    "benuanta.co.id", "www.benuanta.co.id", "www.prokal.co", "prokal.co",
    "radartarakan.jawapos.com", "api-jjmn.jawapos.com", "kaltara.tribunnews.com",
})
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_local = threading.local()


class FetchError(RuntimeError):
    code = "FETCH_FAILED"


class UnsafeURL(FetchError):
    code = "UNSAFE_URL"


def validate_url(url, allowed_hosts=ALLOWED_HOSTS):
    """Validate syntax only; DNS is checked and pinned at connection time."""
    if not isinstance(url, str) or len(url) > 8192 or any(ord(char) < 33 for char in url) or "\\" in url:
        raise UnsafeURL("URL tidak valid.")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme != "https" or host not in allowed_hosts
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)):
            raise UnsafeURL("Tujuan URL tidak diizinkan.")
    except ValueError as error:
        raise UnsafeURL("URL tidak valid.") from error
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def public_address(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise FetchError("Resolusi DNS sumber gagal.") from error
    if not addresses:
        raise FetchError("DNS sumber tidak memberikan alamat.")
    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        # IPv4-mapped IPv6 addresses must pass the IPv4 check as well.
        mapped = getattr(address, "ipv4_mapped", None)
        if (not address.is_global or address.is_multicast or address.is_reserved
                or getattr(address, "is_site_local", False) or (mapped and not mapped.is_global)):
            raise UnsafeURL("DNS sumber mengarah ke jaringan yang tidak diizinkan.")
    return addresses[0][4][0]


class PublicHTTPSAdapter(HTTPAdapter):
    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        if verify is not True or proxies or cert:
            raise UnsafeURL("Transport hanya mendukung HTTPS terverifikasi tanpa proxy.")
        parsed = urlsplit(validate_url(request.url))
        address = public_address(parsed.hostname)
        _, pool_kwargs = self.build_connection_pool_key_attributes(request, verify, cert)
        pool_kwargs.update(assert_hostname=parsed.hostname, server_hostname=parsed.hostname)
        request.headers["Host"] = parsed.hostname
        # The pool connects to this numeric address, never resolving the hostname
        # again. TLS SNI and certificate hostname validation retain the real host.
        return self.poolmanager.connection_from_host(
            address, port=443, scheme="https", pool_kwargs=pool_kwargs,
        )


class RejectHTTPAdapter(HTTPAdapter):
    def send(self, *args, **kwargs):
        raise UnsafeURL("HTTP tanpa TLS tidak diizinkan.")


def session():
    if not hasattr(_local, "session"):
        client = requests.Session()
        client.trust_env = False
        client.headers.update({
            "User-Agent": "Fantastik/2.0 (news research)",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
        })
        client.mount("https://", PublicHTTPSAdapter(max_retries=0))
        client.mount("http://", RejectHTTPAdapter())
        _local.session = client
    return _local.session


def close_session():
    client = getattr(_local, "session", None)
    if client is not None:
        client.close()
        del _local.session


def request(method, url, *, allowed_hosts=ALLOWED_HOSTS, json=None, headers=None,
            timeout=15, retries=2, deadline=None, check=None, max_bytes=MAX_RESPONSE_BYTES):
    """Bound redirects, retries, time, and decompressed bytes for every request.

    Only the read-only GraphQL query is posted by callers. Redirected POSTs are
    rejected rather than forwarding a body to a new destination.
    """
    url = validate_url(url, allowed_hosts)
    deadline = min(deadline if deadline is not None else float("inf"), time.monotonic() + 45)
    retries = max(1, min(retries, 3))
    for attempt in range(retries):
        current = url
        try:
            for hop in range(4):
                if check:
                    check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise FetchError("Batas waktu pengambilan halaman tercapai.")
                wait = min(timeout, remaining)
                response = session().request(
                    method, current, json=json, headers=headers, timeout=(min(5, wait), wait),
                    allow_redirects=False, stream=True,
                )
                try:
                    if 300 <= response.status_code < 400:
                        if method != "GET" or hop == 3 or not response.headers.get("Location"):
                            raise FetchError("Redirect sumber tidak dapat diterima.")
                        current = validate_url(urljoin(current, response.headers["Location"]), allowed_hosts)
                        continue
                    response.raise_for_status()
                    chunks, size = [], 0
                    # read1 returns after at most one underlying read. A large
                    # iter_content chunk can otherwise wait indefinitely when a
                    # peer trickles bytes just below the socket read timeout.
                    while True:
                        if check:
                            check()
                        if time.monotonic() >= deadline:
                            raise FetchError("Batas waktu pengambilan halaman tercapai.")
                        chunk = response.raw.read1(16384, decode_content=True)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > max_bytes:
                            raise FetchError("Ukuran respons sumber melebihi batas.")
                        chunks.append(chunk)
                    response._content = b"".join(chunks)
                    response._content_consumed = True
                    if not response.encoding or response.encoding.lower() == "iso-8859-1":
                        response.encoding = response.apparent_encoding or "utf-8"
                    return response
                finally:
                    response.close()
        except UnsafeURL:
            raise
        except (requests.RequestException, Urllib3HTTPError, OSError) as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            retryable = (status in (429, 500, 502, 503, 504) if status is not None else isinstance(
                error, (requests.ConnectionError, requests.Timeout, Urllib3HTTPError, OSError),
            ))
            if not retryable or attempt + 1 >= retries:
                raise FetchError(f"Pengambilan sumber gagal (HTTP {status or 'network'}).") from error
            delay = min(2 ** attempt, 4)
            retry_after = getattr(getattr(error, "response", None), "headers", {}).get("Retry-After", "")
            if retry_after.isdigit():
                delay = min(max(delay, int(retry_after)), 15)
            until = min(time.monotonic() + delay, deadline)
            while time.monotonic() < until:
                if check:
                    check()
                time.sleep(min(0.1, max(0, until - time.monotonic())))
    raise FetchError("Pengambilan sumber tidak selesai.")
