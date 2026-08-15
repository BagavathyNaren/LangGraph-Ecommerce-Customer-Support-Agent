import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


def _create_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# Shared global HTTP session with connection pooling and automated backoff retry
_session = _create_retry_session()


def get_http_session():
    return _session
