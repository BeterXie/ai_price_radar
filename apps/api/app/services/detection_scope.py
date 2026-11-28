"""Assign official 16688 URLs to the Oracle detector, independent of user hints."""
from sqlalchemy import func, or_, true
from price_radar_http.platform_16688 import HOSTS

from ..core.config import get_settings


def detection_scope_filter(url_column, scope: str):
    if scope not in {'all', '16688', 'other'}:
        raise ValueError('invalid detector scope')
    if scope == 'all' and get_settings().detector_16688_on_oracle:
        # Old or misconfigured main workers must not steal Oracle's tasks.
        scope = 'other'
    if scope == 'all':
        return true()
    url = func.lower(url_column)
    origins = [f'https://{host}{port}' for host in HOSTS for port in ('', ':443')]
    official = or_(*(condition for origin in origins for condition in (url == origin, url.startswith(origin + '/'))))
    return official if scope == '16688' else ~official
