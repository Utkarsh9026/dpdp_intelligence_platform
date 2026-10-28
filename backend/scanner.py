"""Bounded, same-site public website observation for DPDP audits.

NOT an authenticated vulnerability scanner. Two crawl modes share one analysis path:

* browser - pages are rendered in headless Chromium (Playwright), so JavaScript-built
            sites (React/Vue/Angular single-page apps) are inspected as a visitor sees them.
* static  - plain HTTP fetch. Used when no browser is available (or SCAN_MODE=static).
            JavaScript-rendered sites are detected and reported as incomplete instead of
            being reported as having "no privacy link". Sitemap and common-path discovery
            partly compensate.

Environment (all optional):
    SCAN_MODE            auto (default) | browser | static
    SCAN_TIME_BUDGET     overall seconds per scan (default 45)
    SCAN_BROWSER_SLOTS   concurrent browser scans allowed (default 2)
"""
import hashlib
import html as htmllib
import os
import re
import socket
import ipaddress
import threading
import time
import urllib.parse
from collections import deque
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

import evidence as ev

UA = 'DPDP-Audit-Tool/0.2 (+consented public website audit)'
ROBOT_TOKEN = 'DPDP-Audit-Tool'
BANNED = {'localhost', 'localhost.localdomain'}
THIRD_PARTY_HINTS = ('google-analytics', 'googletagmanager', 'facebook.net', 'doubleclick', 'hotjar',
                     'mixpanel', 'segment.com', 'amplitude', 'clarity.ms')
MAX_BODY = 1_000_000
MAX_REDIRECTS = 5
HARD_PAGE_LIMIT = 15
MAX_QUEUE = 60
SCAN_MODE = os.getenv('SCAN_MODE', 'auto').strip().lower()
TIME_BUDGET = float(os.getenv('SCAN_TIME_BUDGET', '45'))
_BROWSER_SLOTS = threading.BoundedSemaphore(max(1, int(os.getenv('SCAN_BROWSER_SLOTS', '2'))))

PRIVACY_RE = re.compile(r'privacy|policy|consent|cookie|grievance|data-protection', re.I)
NOTICE_RE = re.compile(r'privacy|data[\s-]*protection|cookie[\s-]*(policy|notice)|grievance|redress', re.I)  # crawled first
SKIP_PATH_RE = re.compile(r'logout|signout|delete|admin|checkout|payment|cart', re.I)
ASSET_EXT_RE = re.compile(r'\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|gz|png|jpe?g|gif|svg|webp|ico|mp[34]|avi|mov|'
                          r'css|js|json|xml|txt|woff2?|ttf)$', re.I)
COOKIE_BANNER_RE = re.compile(r'we use cookies|this (web)?site uses cookies|(accept|reject|manage|decline)\W+(all\W+)?'
                              r'(cookies?|preferences)|cookie (consent|preferences|settings|policy)|consent preferences',
                              re.I)
COMMON_PATHS = ('/privacy-policy', '/privacy', '/privacy-notice', '/cookie-policy', '/terms', '/terms-and-conditions',
                '/contact', '/contact-us', '/about', '/grievance', '/grievance-redressal')
SPA_ROOT_SELECTOR = '#root, #app, #__next, #___gatsby, app-root, [ng-app], [data-reactroot]'


# --------------------------------------------------------------------------- URL safety

def _site_key(host):
    host = (host or '').lower().rstrip('.')
    return host[4:] if host.startswith('www.') else host


def same_site(a, b):
    """True when two hostnames are the same site (example.com and www.example.com count as one)."""
    return bool(a) and bool(b) and _site_key(a) == _site_key(b)


_dns_cache = {}
_dns_lock = threading.Lock()


def _assert_public(host):
    now = time.monotonic()
    with _dns_lock:
        if _dns_cache.get(host, 0) > now:
            return
    for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError('DNS resolves to a non-public address')
    with _dns_lock:
        _dns_cache[host] = now + 60


def safe_url(url, original_host=None):
    """Validate a URL for crawling and return its lower-cased host.

    Only http(s) on standard ports, never private/internal hosts, and (when original_host
    is given) only the same site. DNS checks are best-effort: run behind egress filtering.
    """
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError('Only HTTP(S) public sites using standard ports are allowed')
    host = p.hostname.lower().rstrip('.')
    if host in BANNED or host.endswith(('.localhost', '.local', '.internal', '.test')):
        raise ValueError('Private hosts not allowed')
    if original_host and not same_site(host, original_host):
        raise ValueError('Redirect leaves the authorised website host')
    _assert_public(host)
    return host


def _normalize(url):
    """Drop #fragments, except client-side routes such as #/about or #!/about."""
    base, frag = urllib.parse.urldefrag(url)
    p = urllib.parse.urlsplit(base)
    if not p.path:  # https://host and https://host/ are the same page
        base = urllib.parse.urlunsplit((p.scheme, p.netloc, '/', p.query, ''))
    return base + '#' + frag if frag.startswith(('/', '!/')) else base


# --------------------------------------------------------------------------- static fetching

def _make_session():
    s = requests.Session()
    s.trust_env = False  # never let HTTP(S)_PROXY env vars bypass the destination checks
    s.headers['User-Agent'] = UA
    return s


def fetch(url, base_host, session=None, max_body=MAX_BODY):
    """GET a URL, following same-site redirects manually (each hop re-validated).

    Returns status, final url, redirect chain, headers, decoded `text`, and `html`
    (text only when the response is HTML). `base_host=None` allows other public hosts (used only for
    a notice the site itself links to).
    """
    session = session or _make_session()
    current, chain = url, []
    for _ in range(MAX_REDIRECTS + 1):
        safe_url(current, base_host)
        with session.get(current, timeout=(4, 9), allow_redirects=False, stream=True) as r:
            location = r.headers.get('Location')
            if 300 <= r.status_code < 400 and location:
                chain.append(current)
                current = urllib.parse.urljoin(current, location)
                continue
            try:
                declared = int(r.headers.get('content-length', '0') or '0')
            except ValueError:
                declared = 0
            if declared > max_body:
                raise ValueError(f'Page exceeds {max_body // 1_000_000}MB cap')
            chunks, size = [], 0
            for chunk in r.iter_content(chunk_size=16384):
                size += len(chunk)
                if size > max_body:
                    raise ValueError(f'Page exceeds {max_body // 1_000_000}MB cap')
                chunks.append(chunk)
            text = b''.join(chunks).decode(r.encoding or 'utf-8', errors='replace')
            ctype = r.headers.get('content-type', '').lower()
            return {'status': r.status_code, 'url': current, 'redirects': chain, 'headers': dict(r.headers),
                    'text': text, 'html': text if 'html' in ctype else ''}
    raise ValueError('Too many redirects')


def _load_robots(origin, host, session):
    """Return (RobotFileParser | None, sitemap URLs). None means "no usable rules" (allow all).

    A missing robots.txt (404), an HTML fallback page, or a fetch error all mean no rules.
    """
    try:
        r = fetch(origin + '/robots.txt', host, session)
    except Exception:
        return None, []
    ctype = r['headers'].get('Content-Type', r['headers'].get('content-type', '')).lower()
    if r['status'] != 200 or 'html' in ctype or not r['text'].strip():
        return None, []
    lines = r['text'].splitlines()
    parser = RobotFileParser()
    parser.parse(lines)
    sitemaps = [ln.split(':', 1)[1].strip() for ln in lines if ln.lower().startswith('sitemap:')]
    return parser, sitemaps


def _sitemap_urls(sitemaps, host, session, limit=60):
    """Collect same-site page URLs from sitemap(s), following one level of sitemap indexes."""
    urls, seen = [], set()
    queue = deque(sitemaps)
    while queue and len(urls) < limit and len(seen) < 6:
        sm = queue.popleft()
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = fetch(sm, host, session)
        except Exception:
            continue
        if r['status'] != 200:
            continue
        locs = [htmllib.unescape(x) for x in re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', r['text'])]
        if '<sitemapindex' in r['text'][:2000].lower():
            queue.extend(locs[:5])
            continue
        for loc in locs:
            if same_site(urllib.parse.urlsplit(loc).hostname, host) and loc not in urls:
                urls.append(loc)
            if len(urls) >= limit:
                break
    return urls


# --------------------------------------------------------------------------- browser rendering

class BrowserUnavailable(Exception):
    pass


class _Browser:
    """Headless Chromium whose every network request passes the same public-host checks."""

    def __init__(self, host):
        self.host = host
        self.network_hosts = set()
        self.blocked = []
        self._pw = self._browser = self._context = None
        if not _BROWSER_SLOTS.acquire(timeout=10):
            raise BrowserUnavailable('browser scanner is busy; try again shortly')
        self._slot = True
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self._context = self._browser.new_context(user_agent=UA, locale='en-IN', service_workers='block',
                                                      accept_downloads=False,
                                                      viewport={'width': 1280, 'height': 900})
            self._context.route('**/*', self._route)
            try:
                self._context.route_web_socket('**/*', lambda ws: ws.close())
            except Exception:
                pass
        except Exception as e:
            self.close()
            raise BrowserUnavailable(str(e).splitlines()[0][:200] if str(e) else type(e).__name__)

    def _route(self, route):
        req = route.request
        try:
            if urllib.parse.urlsplit(req.url).scheme in ('data', 'blob', 'about'):
                route.continue_()
                return
            host = safe_url(req.url)  # raises for non-public / non-standard destinations
            self.network_hosts.add(host)
            if req.resource_type in ('image', 'media', 'font'):
                route.abort()
                return
            if (req.is_navigation_request() and req.frame.parent_frame is None
                    and not same_site(host, self.host)):
                self.blocked.append(req.url)
                route.abort()
                return
            route.continue_()
        except Exception:
            self.blocked.append(req.url)
            try:
                route.abort()
            except Exception:
                pass

    def render(self, url, first=False):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        page = self._context.new_page()
        self.blocked.clear()
        try:
            try:
                resp = page.goto(url, wait_until='domcontentloaded', timeout=15000)
            except Exception as e:
                if self.blocked:
                    raise ValueError('Redirect leaves the authorised website host')
                raise ValueError(str(e).splitlines()[0][:200])
            try:
                page.wait_for_load_state('networkidle', timeout=2500)
            except PlaywrightTimeout:
                pass
            # Scroll like a visitor so lazily-rendered footers (where privacy links usually live) and widgets load.
            try:
                for _ in range(4):
                    page.evaluate('window.scrollBy(0, Math.max(600, document.body.scrollHeight / 3))')
                    page.wait_for_timeout(180)
            except Exception:
                pass
            page.wait_for_timeout(250)
            html = page.content()
            out = {'status': resp.status if resp else 0, 'url': page.url, 'redirects': [], 'html': html,
                   'text': html, 'headers': {k.lower(): v for k, v in resp.headers.items()} if resp else {}}
            if first:
                out['cookies'] = self._context.cookies()
            return out
        finally:
            page.close()

    def close(self):
        for closer in (lambda: self._context and self._context.close(),
                       lambda: self._browser and self._browser.close(),
                       lambda: self._pw and self._pw.stop()):
            try:
                closer()
            except Exception:
                pass
        if getattr(self, '_slot', False):
            self._slot = False
            _BROWSER_SLOTS.release()


# --------------------------------------------------------------------------- crawl state + analysis

class _Crawl:
    def __init__(self, host, max_pages):
        self.host, self.max_pages = host, max_pages
        self.queue, self.queued, self.seen = deque(), set(), set()
        self.pages, self.findings, self.forms = [], [], []
        self.privacy, self.third_party = set(), set()
        self.probes = set()
        self.page_ev, self.cookies, self.first_headers = [], [], {}
        self.deadline = time.monotonic() + TIME_BUDGET

    def finding(self, url, type_, detail, severity):
        self.findings.append({'url': url, 'type': type_, 'detail': detail, 'severity': severity})

    def enqueue(self, url, front=False):
        """Queue a page. Notices go to the front so they are read before the page limit is hit."""
        n = _normalize(url)
        if n not in self.seen and n not in self.queued and (front or len(self.queue) < MAX_QUEUE):  # notices bypass the cap
            self.queued.add(n)
            (self.queue.appendleft if front else self.queue.append)(n)

    def ingest(self, html, page_url):
        """Extract links, forms and third-party resources. Returns stats used for SPA detection."""
        soup = BeautifulSoup(html, 'html.parser')
        anchors = soup.select('a[href]')
        for link in anchors:
            raw = (link.get('href') or '').strip()
            if not raw or raw.lower().startswith(('javascript:', 'mailto:', 'tel:')):
                continue
            href = urllib.parse.urljoin(page_url, raw)
            p = urllib.parse.urlsplit(href)
            if p.scheme not in ('http', 'https') or not p.hostname:
                continue
            label = link.get_text(' ', strip=True)
            if not same_site(p.hostname, self.host):
                # Policies are often hosted on another domain: record when the link text says so, never crawl it.
                if PRIVACY_RE.search(label):
                    self.privacy.add(_normalize(href))
                continue
            if PRIVACY_RE.search(href + ' ' + label):
                self.privacy.add(_normalize(href))
            if not ASSET_EXT_RE.search(p.path) and not SKIP_PATH_RE.search(p.path):
                self.enqueue(href, front=bool(NOTICE_RE.search(href + ' ' + label)))
        for f in soup.find_all('form'):
            fields = [{'name': x.get('name', ''), 'type': x.get('type', 'text')}
                      for x in f.select('input,textarea,select')][:30]
            details = {'url': page_url, 'method': f.get('method', 'get').upper(), 'action': f.get('action', ''),
                       'fields': fields}
            self.forms.append(details)
            if details['method'] == 'GET' and any(x['type'] in ('password', 'email', 'tel') for x in fields):
                self.finding(page_url, 'form_get_personal_data',
                             'Form uses GET while requesting common personal-data fields; review URI exposure', 'review')
        scripts = soup.select('script[src]')
        for el in soup.select('script[src], iframe[src], img[src]'):
            h = urllib.parse.urlsplit(urllib.parse.urljoin(page_url, el.get('src', ''))).hostname
            if h and not same_site(h, self.host):
                self.third_party.add(h.lower())
        try:
            pre_info = ev.pre(soup, page_url)
        except Exception:
            pre_info = {'inline_js': '', 'mixed': [], 'consent_mode': False}
        for t in soup(['script', 'style', 'noscript']):
            t.decompose()
        text = soup.get_text(' ', strip=True)
        try:  # evidence is best-effort: a parsing oddity must never fail the whole scan
            self.page_ev.append(ev.extract(soup, text, page_url, self.host, pre_info))
        except Exception as e:
            self.page_ev.append({'url': page_url, 'error': str(e)[:120], 'forms': [], 'links': {}, 'kind': None})
        # A JS app shell has an empty mount point and (almost) no visible text before scripts run.
        shell = (len(text) < 150 and bool(soup.select_one(SPA_ROOT_SELECTOR))) or \
                (len(text) < 60 and bool(scripts) and not anchors)
        return {'anchors': len(anchors), 'text_len': len(text), 'shell': shell, 'text': text}


def _cookie_findings(crawl, url, cookies, banner_seen):
    if not cookies:
        return
    first = sorted({c['name'] for c in cookies if same_site(c.get('domain', '').lstrip('.'), crawl.host)})
    third = sorted({c.get('domain', '').lstrip('.') for c in cookies if not same_site(c.get('domain', '').lstrip('.'), crawl.host)})
    detail = (f'{len(cookies)} cookie(s) were set on first page load before any consent interaction '
              f'(first-party names: {", ".join(first[:10]) or "none"}; third-party domains: {", ".join(third[:10]) or "none"}). '
              'Assess whether any are non-essential and whether consent is obtained first. Cookie values were not recorded.')
    crawl.finding(url, 'cookies_set_before_consent', detail, 'review')
    if not banner_seen:
        crawl.finding(url, 'consent_mechanism_not_detected',
                      'Cookies were set but no cookie/consent banner text was detected in the rendered first page. '
                      'Manual review needed (banners can load late or be hidden from automation).', 'review')


def _http_probe(host, session):
    """What does plain http://host/ do? Evidence for the HTTPS-everywhere check."""
    try:
        safe_url('http://' + host + '/')
        with session.get('http://' + host + '/', timeout=(4, 6), allow_redirects=False, stream=True) as r:
            loc = r.headers.get('Location', '')
            if 300 <= r.status_code < 400:
                return 'redirects_to_https' if loc.lower().startswith('https://') else 'redirects_other'
            return 'served_over_http' if r.status_code < 400 else 'error'
    except Exception:
        return 'unreachable'


NOTICE_PATHS = ('/privacy-policy', '/privacy', '/privacy-notice', '/privacy_policy', '/legal/privacy', '/privacy-policy/')


def _read_missing_notices(crawl, host, origin, session, robots, max_tries=5):
    """Make sure the privacy notice gets read; the checklist's A, B, E and I checks depend on its text.

    If the crawl did not read one, fetch (one static GET each): privacy links discovered but not visited, then
    policies hosted on another domain that the site itself links to (a visitor clicking the link would do the same),
    then conventional paths. Public hosts only; each hop is re-validated by fetch().
    """
    if any(p.get('kind') == 'privacy' and p.get('text') for p in crawl.page_ev):
        return
    visited = {_normalize(p['url']) for p in crawl.page_ev}
    local = [u for u in sorted(crawl.privacy) if same_site(urllib.parse.urlsplit(u).hostname, host) and u not in visited]
    remote = [u for u in sorted(crawl.privacy) if not same_site(urllib.parse.urlsplit(u).hostname, host)]
    guesses = [origin + p for p in NOTICE_PATHS]
    tries = 0
    for u in local + remote + guesses:
        if tries >= max_tries or time.monotonic() > crawl.deadline + 15:
            break
        if ASSET_EXT_RE.search(urllib.parse.urlsplit(u).path):
            continue
        offsite = not same_site(urllib.parse.urlsplit(u).hostname, host)
        if not offsite and robots is not None and not robots.can_fetch(ROBOT_TOKEN, u):
            continue
        tries += 1
        try:
            d = fetch(u, None if offsite else host, session, max_body=4_000_000)
            if d['status'] != 200 or not d['html']:
                continue
            soup = BeautifulSoup(d['html'], 'html.parser')
            pre_info = ev.pre(soup, d['url'])
            for t in soup(['script', 'style', 'noscript']):
                t.decompose()
            text = soup.get_text(' ', strip=True)
            if len(text) < 300:  # an empty JavaScript shell or an error page, not a notice
                continue
            page = ev.extract(soup, text, d['url'], host, pre_info)
            if page['kind'] not in ('privacy', 'cookie'):
                if not re.search(r'privacy|personal (data|information)', text[:3000], re.I):
                    continue
                page['kind'] = 'privacy'
            page.update({'offsite': offsite, 'text': text[:60000]})
            crawl.page_ev.append(page)
            if page['kind'] == 'privacy':
                return
        except Exception:
            continue


def _server_ip(host):
    try:
        for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
            return info[4][0]
    except Exception:
        pass
    return ''


def scan(url, max_pages=8, progress=None):
    """Crawl `url` and return observations plus a structured `evidence` block.

    `progress(stage, **info)` is called (best-effort, exceptions ignored) so a caller can show live status.
    """
    def note(stage, **info):
        if progress:
            try:
                progress(stage, **info)
            except Exception:
                pass

    if not url.startswith(('https://', 'http://')):
        url = 'https://' + url
    host = safe_url(url)
    parsed = urllib.parse.urlsplit(url)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    max_pages = max(1, min(max_pages, HARD_PAGE_LIMIT))
    session = _make_session()
    crawl = _Crawl(host, max_pages)
    deadline = crawl.deadline
    note('start', host=host)
    robots, sitemaps = _load_robots(origin, host, session)
    http_probe = _http_probe(host, session) if parsed.scheme == 'https' else 'n/a'
    note('robots', sitemaps=len(sitemaps))

    browser = None
    if SCAN_MODE in ('auto', 'browser'):
        try:
            browser = _Browser(host)
        except BrowserUnavailable as e:
            if SCAN_MODE == 'browser':
                raise ValueError(f'Browser rendering unavailable: {e}')
            crawl.finding(url, 'browser_rendering_unavailable',
                          f'Headless browser could not start ({e}); fell back to static HTML analysis. '
                          'JavaScript-built content cannot be inspected in this mode.', 'info')
    mode = 'browser' if browser else 'static'
    note('browser', mode=mode)
    state = {'spa': False, 'home_hash': None, 'timed_out': False}

    def drain():
        while crawl.queue and len(crawl.pages) < crawl.max_pages:
            if time.monotonic() > deadline:
                state['timed_out'] = True
                return
            current = crawl.queue.popleft()
            crawl.queued.discard(current)
            if current in crawl.seen:
                continue
            crawl.seen.add(current)
            if robots is not None and not robots.can_fetch(ROBOT_TOKEN, current):
                crawl.finding(current, 'blocked_by_robots', 'Skipped: disallowed by robots.txt', 'info')
                continue
            first = not crawl.pages
            note('page', url=current, n=len(crawl.pages) + 1, max=crawl.max_pages)
            try:
                data = browser.render(current, first) if browser else fetch(current, host, session)
            except Exception as e:
                if current not in crawl.probes:
                    crawl.finding(current, 'fetch_error', str(e)[:300], 'info')
                continue
            final = data['url']
            crawl.seen.add(_normalize(final))
            if current in crawl.probes:  # guessed path: keep only if it is a genuine, distinct page
                body_hash = hashlib.sha1(data['html'].encode('utf-8', 'ignore')).hexdigest()
                if (data['status'] != 200 or not data['html'] or body_hash == state['home_hash']
                        or urllib.parse.urlsplit(final).path in ('', '/')):
                    continue
                if PRIVACY_RE.search(final):
                    crawl.privacy.add(_normalize(final))
            crawl.pages.append({'url': current, 'final_url': final, 'status': data['status'],
                                'redirect': final if final != current else '', 'rendered': bool(browser)})
            headers = {k.lower(): v for k, v in data['headers'].items()}
            if first:
                crawl.first_headers = {n: headers[n] for n in ('strict-transport-security', 'content-security-policy',
                                                               'x-content-type-options', 'referrer-policy', 'x-frame-options',
                                                               'permissions-policy', 'server', 'x-powered-by') if n in headers}
                crawl.cookies = [{'name': c.get('name', '')[:60], 'domain': c.get('domain', '').lstrip('.')[:120],
                                  'secure': bool(c.get('secure')), 'http_only': bool(c.get('httpOnly')),
                                  'first_party': same_site(c.get('domain', '').lstrip('.'), host)}
                                 for c in (data.get('cookies') or [])][:60]
                if urllib.parse.urlsplit(final).scheme == 'http':
                    crawl.finding(final, 'site_not_https', 'First page was served over plain HTTP', 'advisory')
                for name in ('strict-transport-security', 'content-security-policy', 'x-content-type-options',
                             'referrer-policy'):
                    if name not in headers and not (name == 'strict-transport-security'
                                                    and urllib.parse.urlsplit(final).scheme == 'http'):
                        crawl.finding(final, 'missing_security_header',
                                      'Missing ' + name + ' (security hardening observation; not independently a DPDP violation)',
                                      'advisory')
                state['home_hash'] = hashlib.sha1(data['html'].encode('utf-8', 'ignore')).hexdigest()
            if not data['html']:
                continue
            stats = crawl.ingest(data['html'], final)
            if first:
                state['spa'] = stats['shell'] and not browser
                if browser:
                    _cookie_findings(crawl, final, data.get('cookies', []),
                                     bool(COOKIE_BANNER_RE.search(stats['text'])))

    crawl.enqueue(url)
    try:
        drain()
        if browser is None and not state['timed_out'] and (state['spa'] or len(crawl.pages) <= 1):
            # Static fallback discovery: sitemaps (all sites) and common paths (non-SPA only, since a
            # SPA answers every path with the same empty shell).
            for u in _sitemap_urls(list(dict.fromkeys(sitemaps + [origin + '/sitemap.xml'])), host, session):
                if PRIVACY_RE.search(u):
                    crawl.privacy.add(_normalize(u))
                if not state['spa']:
                    crawl.enqueue(u)
            if not state['spa']:
                for path in COMMON_PATHS:
                    crawl.probes.add(origin + path)
                    crawl.enqueue(origin + path)
            drain()
    finally:
        network_hosts = set(browser.network_hosts) if browser else set()
        if browser:
            browser.close()

    crawl.third_party |= {h for h in network_hosts if not same_site(h, host)}
    if state['timed_out']:
        crawl.finding(url, 'scan_time_limit', f'Stopped after the {int(TIME_BUDGET)}s time budget; some pages were not visited.', 'info')
    if state['spa']:
        crawl.finding(url, 'javascript_rendered_site',
                      'This site builds its pages with JavaScript. A static crawl only sees an empty shell, so links, '
                      'forms and privacy notices could not be inspected and this result is INCOMPLETE. '
                      'Enable browser rendering (see README) and scan again.', 'review')
    elif not crawl.privacy:
        crawl.finding(url, 'privacy_link_not_discovered',
                      'No privacy-related link discovered in visited pages. Manual review needed.', 'review')
    for d in sorted(crawl.third_party):
        if any(hint in d for hint in THIRD_PARTY_HINTS):
            crawl.finding(url, 'third_party_analytics',
                          f'Third-party resource detected: {d}; assess data transfers and lawful purpose', 'review')
    caveats = ['Public pages only; no form submission or authentication',
               'No proof of actual consent collection, storage, sharing, deletion or legal violation',
               'DNS checks are best-effort; deploy scanner behind egress filtering / network isolation in production',
               'Review robots restrictions and only scan sites you are authorised to assess']
    if mode == 'browser':
        caveats.append('Pages were rendered in a headless browser; cookies seen are those set on the first page load only')
    else:
        caveats.append('Static HTML analysis only: content created by JavaScript was not evaluated')
    note('analysing', pages=len(crawl.pages))
    _read_missing_notices(crawl, host, origin, session, robots)
    kept = 0
    for p in crawl.page_ev:  # keep the full text of at most 5 notice-type pages; everything else only keeps a sample
        if p.get('text'):
            kept += 1
            if kept > 5:
                p['text'] = ''
    evidence_block = {'pages': crawl.page_ev, 'cookies': crawl.cookies, 'headers': crawl.first_headers,
                      'http_probe': http_probe, 'server_ip': _server_ip(host),
                      'final_scheme': urllib.parse.urlsplit(crawl.pages[0]['final_url']).scheme if crawl.pages else '',
                      'incomplete_spa': state['spa'], 'timed_out': state['timed_out'], 'host': host}
    return {'target': url, 'mode': mode, 'evidence': evidence_block, 'pages': crawl.pages, 'forms': crawl.forms,
            'third_party_hosts': sorted(crawl.third_party), 'privacy_urls': sorted(crawl.privacy),
            'findings': crawl.findings, 'caveats': caveats}
