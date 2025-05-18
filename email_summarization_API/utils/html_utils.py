import re
from html import unescape

def strip_html(html):
    return unescape(re.sub(r'<[^>]+>', '', html or ''))
