"""Small original line icons shared by the reader's visual navigation."""
from html import escape

PATHS = {
    'compass': '<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6Z"/>',
    'server': '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 11h16M8 7.5h.01M8 15h.01M12 15h4"/>',
    'key': '<circle cx="8" cy="9" r="4"/><path d="m11 12 8 8m-4-4 3-3m-1 5 3-3"/>',
    'pulse': '<path d="M3 13h4l3-7 4 13 3-6h4"/><path d="M4 4h3m10 16h3"/>',
    'move': '<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
    'restore': '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6M12 7v5l4 2"/>',
    'network': '<circle cx="12" cy="12" r="3"/><circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="12" cy="21" r="1.5"/><path d="m6.5 6.5 3.5 3.5m4 0 3.5-3.5M12 15v4.5"/>',
    'search': '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6m-3-3v6"/>',
    'source': '<path d="M5 3h10l4 4v14H5ZM14 3v5h5M8 12h8m-8 4h6"/>',
    'spark': '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
    'internal': '<path d="M4 12h15m-5-5 5 5-5 5"/>',
    'term': '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1.5 1-1.5 1.5-1.5 2.5M12 17h.01"/>',
    'repository': '<circle cx="7" cy="5" r="2"/><circle cx="17" cy="6" r="2"/><circle cx="7" cy="19" r="2"/><path d="M7 7v10m0-4h5a5 5 0 0 0 5-5"/>',
    'external': '<path d="M14 3h7v7m0-7L10 14M10 5H4v15h15v-6"/>',
    'file': '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
}


def icon(name, css='ui-icon'):
    return (f'<svg class="{escape(css)}" viewBox="0 0 24 24" width="24" height="24" '
            f'aria-hidden="true" focusable="false">{PATHS[name]}</svg>')


def chapter_icon(source):
    kinds = {'01': 'server', '02': 'key', '03': 'pulse', '04': 'move', '05': 'move',
             '06': 'restore', '07': 'network', '08': 'search', '09': 'key'}
    return kinds.get(source.rsplit('/', 1)[-1][:2], 'source')
