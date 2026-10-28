"""Per-page evidence extraction for the DPDP website checklist.

Pure functions over a BeautifulSoup tree: no network, no state. The crawler (scanner.py) calls
`pre()` before it strips <script>/<style>, then `extract()` once the visible text is available.
Everything returned is JSON-serialisable and deliberately small (snippets, not whole pages),
because it is stored with the scan and re-evaluated whenever the owner answers a question.
"""
import re
import urllib.parse

PRIVACY_LINK_RE = re.compile(r'privacy|data[\s-]*protection|cookie[\s-]*(policy|notice)|personal[\s-]*data', re.I)

LINK_KINDS = {
    'privacy': PRIVACY_LINK_RE,
    'terms': re.compile(r'\bterms\b|conditions of use', re.I),
    'rights': re.compile(r'(data principal|privacy|data|your)[\s-]*(rights?|requests?)|exercise (your )?rights|dsar|subject access|'
                         r'access (my|your) data|delete (my |your )?(account|data)|erasure|data deletion', re.I),
    'grievance': re.compile(r'grievance|complaint|redress', re.I),
    'dpo': re.compile(r'\bdpo\b|data protection officer|privacy officer|nodal officer', re.I),
    'withdraw': re.compile(r'unsubscribe|withdraw(\s+your)?\s+consent|opt[\s-]?out|manage\s+(my\s+|your\s+)?(consent|preferences|subscriptions?)|'
                           r'(cookie|privacy)\s+(settings|preferences|choices)', re.I),
    'careers': re.compile(r'career|\bjobs?\b|join us|work with us|vacanc|we.re hiring', re.I),
    'login': re.compile(r'log\s?in|sign\s?in|my account|customer portal', re.I),
    'checkout': re.compile(r'check\s?out|\bcart\b|buy now|pay(ment)? now|add to cart', re.I),
    'language': re.compile(r'^(english|hindi|हिन्दी|हिंदी|தமிழ்|తెలుగు|ಕನ್ನಡ|മലയാളം|বাংলা|मराठी|ગુજરાતી|ਪੰਜਾਬੀ|اردو|ଓଡ଼ିଆ|অসমীয়া|'
                           r'tamil|telugu|kannada|malayalam|bengali|marathi|gujarati|punjabi|urdu|odia|assamese)$', re.I),
}
KIND_CAP = 8  # links kept per kind per page

CONTAINER_RE = re.compile(r'cookie|consent|gdpr|\bcmp\b|onetrust|cookiebot|ot-sdk|cc-window|cky-|truste|termly|didomi|usercentrics|osano', re.I)
BANNER_TEXT_RE = re.compile(r'we use cookies|this (web)?site uses cookies|uses cookies|cookie (consent|preferences|settings|policy|notice)|'
                            r'(accept|reject|manage|decline)\W+(all\W+)?(cookies?|preferences)|consent preferences', re.I)
ACCEPT_RE = re.compile(r'^(accept|agree|allow|got it|ok(ay)?|i agree|i understand|yes)\b|accept all|allow all|agree (&|and) (close|proceed|continue)', re.I)
REJECT_RE = re.compile(r'reject|decline|deny|refuse|disagree|(only|just)\s+(necessary|essential)|necessary only|essential only|no,?\s*thanks?', re.I)
MANAGE_RE = re.compile(r'manage|customi[sz]e|preferences|settings|choices|more options|cookie options', re.I)
IMPLIED_RE = re.compile(r'by\s+(continuing|using|browsing|accessing|visiting|clicking|submitting|signing up|registering|proceeding)'
                        r'[^.]{0,120}?(you\s+)?(agree|accept|consent|acknowledge)', re.I)
AGE_RE = re.compile(r'are you (over |above )?(18|eighteen)|(18|eighteen)\s*(\+|years|yrs)|date of birth|\bdob\b|parental consent|'
                    r'parent(s)? or (legal )?guardian|under (the age of )?18|age verification|verify your age|minors?\b', re.I)
PERSONAL_FIELD_RE = re.compile(r'e-?mail|phone|mobile|\btel\b|full[\s_-]?name|first[\s_-]?name|last[\s_-]?name|\bname\b|address|pincode|'
                               r'zip|dob|birth|aadhaar|aadhar|\bpan\b|passport|resume|\bcv\b|city', re.I)
SENSITIVE_FIELD_RE = re.compile(r'aadhaar|aadhar|\bpan\b|passport|\bdob\b|birth|gender|salary|income|religion|caste|marital|'
                                r'blood|health|medical|disease|card[\s_-]?(number|no)|cvv|bank|account[\s_-]?number|ifsc|biometric', re.I)
FORM_KINDS = (
    ('search', re.compile(r'search|find|\bq\b|query', re.I)),
    ('newsletter', re.compile(r'newsletter|subscribe|subscription|mailing|updates', re.I)),
    ('careers', re.compile(r'career|apply|resume|\bcv\b|job|vacanc', re.I)),
    ('checkout', re.compile(r'checkout|payment|card|billing|order', re.I)),
    ('login', re.compile(r'log\s?in|sign\s?in|signin|password|auth', re.I)),
    ('lead', re.compile(r'demo|quote|callback|call[\s-]?back|lead|enquir|inquir|book|appointment|register', re.I)),
    ('contact', re.compile(r'contact|message|feedback|support|query|reach', re.I)),
)


def _slug(el):
    return ' '.join(filter(None, [el.get('id', ''), ' '.join(el.get('class', []) or []), el.get('name', ''), el.get('action', '')]))


def pre(soup, page_url):
    """Collect what is lost once <script> is decompressed: inline JS and plain-HTTP sub-resources."""
    inline = ' '.join(s.get_text(' ') for s in soup.find_all('script') if not s.get('src'))[:300000]
    mixed = []
    if urllib.parse.urlsplit(page_url).scheme == 'https':
        for el in soup.select('script[src], img[src], iframe[src], source[src], video[src], audio[src], link[href], embed[src]'):
            u = el.get('src') or el.get('href') or ''
            if u.lower().startswith('http://') and el.name != 'a':
                mixed.append(u[:200])
            if len(mixed) >= 10:
                break
    return {'inline_js': inline, 'mixed': mixed,
            'consent_mode': bool(re.search(r'gtag\(\s*[\'"]consent[\'"]|__tcfapi|__cmp\b|OneTrust\.|Cookiebot\.|dataLayer[^;]{0,80}consent', inline))}


def _snippet(text, rx, width=150):
    m = rx.search(text or '')
    if not m:
        return ''
    a, b = max(0, m.start() - width // 2), min(len(text), m.end() + width // 2)
    return re.sub(r'\s+', ' ', text[a:b]).strip()


def _label_for(soup, el):
    ident = el.get('id')
    if ident:
        lab = soup.find('label', attrs={'for': ident})
        if lab:
            return lab.get_text(' ', strip=True)[:200]
    lab = el.find_parent('label')
    if lab:
        return lab.get_text(' ', strip=True)[:200]
    nxt = el.find_next_sibling(string=True)
    if nxt and nxt.strip():
        return nxt.strip()[:200]
    parent = el.parent
    return parent.get_text(' ', strip=True)[:200] if parent else ''


def _form(soup, f, page_url):
    fields, checks = [], []
    for x in f.select('input,textarea,select'):
        t = (x.get('type') or ('textarea' if x.name == 'textarea' else 'text')).lower()
        if t in ('hidden', 'submit', 'button', 'image', 'reset'):
            continue
        if t in ('checkbox', 'radio'):
            checks.append({'label': _label_for(soup, x), 'checked': x.has_attr('checked'), 'required': x.has_attr('required'),
                           'name': x.get('name', '')[:60]})
            continue
        fields.append({'name': (x.get('name') or x.get('id') or '')[:60], 'type': t,
                       'hint': (x.get('placeholder') or x.get('aria-label') or '')[:60]})
    buttons = [b.get_text(' ', strip=True)[:60] or b.get('value', '')[:60] for b in f.select('button, input[type=submit]')]
    text = f.get_text(' ', strip=True)
    slug = _slug(f) + ' ' + ' '.join(buttons)
    types = {x['type'] for x in fields}
    kind = 'other'
    if 'password' in types:
        kind = 'login'
    else:
        for k, rx in FORM_KINDS:
            if rx.search(slug):
                kind = k
                break
        else:
            if types and types <= {'search'}:
                kind = 'search'
    # A privacy/notice link counts as "at the collection point" if it sits in the form or its nearest containers.
    near = False
    node = f
    for _ in range(3):
        if node is None:
            break
        if any(PRIVACY_LINK_RE.search((a.get_text(' ', strip=True) or '') + ' ' + (a.get('href') or '')) for a in node.find_all('a', href=True)):
            near = True
            break
        node = node.parent
    sig = ' '.join(x['name'] + ' ' + x['hint'] for x in fields)
    return {'url': page_url, 'kind': kind, 'method': f.get('method', 'get').upper(), 'action': (f.get('action') or '')[:200],
            'action_http': (f.get('action') or '').lower().startswith('http://'),
            'fields': fields[:25], 'checkboxes': checks[:8], 'buttons': [b for b in buttons if b][:4],
            'privacy_near': near, 'personal': kind != 'search' and (bool(PERSONAL_FIELD_RE.search(sig)) or bool({'email', 'tel'} & types)),
            'sensitive': sorted({m.group(0).lower() for m in SENSITIVE_FIELD_RE.finditer(sig)})[:6],
            'implied': _snippet(text, IMPLIED_RE) if not checks else ''}


def _banner(soup, text):
    """Describe a cookie/consent banner on this page, or None."""
    labels, container_text = [], ''
    for el in soup.find_all(True, attrs={'id': True}) + soup.find_all(True, attrs={'class': True}):
        if el.name in ('html', 'body', 'main', 'head'):
            continue
        if CONTAINER_RE.search(_slug(el)) and len(el.get_text(strip=True)) < 2500:
            container_text = container_text or el.get_text(' ', strip=True)
            for b in el.select('button, a, [role=button], input[type=button], input[type=submit]'):
                lab = (b.get_text(' ', strip=True) or b.get('value', '') or b.get('aria-label', '')).strip()
                if lab and len(lab) <= 50 and lab not in labels:
                    labels.append(lab)
    if not labels:
        for b in soup.select('button, [role=button], a'):
            lab = b.get_text(' ', strip=True)
            if lab and len(lab) <= 40 and (ACCEPT_RE.search(lab) or REJECT_RE.search(lab)) and lab not in labels:
                labels.append(lab)
    detected = bool(BANNER_TEXT_RE.search(text)) or bool(container_text and BANNER_TEXT_RE.search(container_text))
    if not detected and not (labels and any(REJECT_RE.search(x) for x in labels) and any(ACCEPT_RE.search(x) for x in labels)):
        return None
    ctx = container_text or text
    return {'buttons': labels[:10], 'accept': any(ACCEPT_RE.search(x) for x in labels), 'reject': any(REJECT_RE.search(x) for x in labels),
            'manage': any(MANAGE_RE.search(x) for x in labels),
            'implied': _snippet(ctx, IMPLIED_RE), 'excerpt': re.sub(r'\s+', ' ', ctx)[:240]}


def _in_footer(a):
    for p in a.parents:
        if p.name == 'footer' or re.search(r'footer', ' '.join([p.get('id', '') or '', ' '.join(p.get('class', []) or [])]), re.I):
            return True
    return False


def extract(soup, text, page_url, site_host, pre_info):
    """Evidence for one rendered page. `soup` has scripts removed; `text` is its visible text."""
    title = (soup.title.get_text(' ', strip=True) if soup.title else '')[:160]
    h1 = (soup.h1.get_text(' ', strip=True) if soup.h1 else '')[:160]
    path = urllib.parse.urlsplit(page_url).path.lower()
    head = f'{path} {title} {h1}'
    kind = None
    if re.search(r'privacy|data[\s-]*protection|personal[\s-]*data', head, re.I) and not re.search(r'terms', path):
        kind = 'privacy'
    elif re.search(r'cookie', head, re.I):
        kind = 'cookie'
    elif re.search(r'grievance|redress', head, re.I):
        kind = 'grievance'
    elif re.search(r'terms|conditions', head, re.I):
        kind = 'terms'

    links, privacy_any, privacy_footer = {}, False, False
    for a in soup.select('a[href]'):
        label = (a.get_text(' ', strip=True) or a.get('aria-label', '') or a.get('title', '')).strip()[:80]
        href = (a.get('href') or '').strip()
        if not href or href.startswith(('javascript:', '#')):
            continue
        probe = f'{label} {urllib.parse.urlsplit(href).path}'
        footer = None
        for k, rx in LINK_KINDS.items():
            if rx.search(label if k == 'language' else probe) and (label or k != 'language'):
                if k == 'privacy':
                    privacy_any = True
                    footer = _in_footer(a) if footer is None else footer
                    privacy_footer = privacy_footer or footer
                lst = links.setdefault(k, [])
                if len(lst) < KIND_CAP:
                    lst.append({'text': label, 'href': urllib.parse.urljoin(page_url, href)[:240]})
    mail = sorted({a['href'][7:].split('?')[0].lower() for a in soup.select('a[href^="mailto:"]')})[:6]

    forms = [_form(soup, f, page_url) for f in soup.find_all('form')][:12]
    switchers = []
    for sel in soup.find_all('select'):
        opts = [o.get_text(' ', strip=True) for o in sel.find_all('option')]
        if sum(1 for o in opts if LINK_KINDS['language'].match(o) or o.lower() in ('english', 'hindi')) >= 2:
            switchers.append(opts[:12])
    hreflangs = sorted({l.get('hreflang', '') for l in soup.select('link[rel=alternate][hreflang]') if l.get('hreflang') not in (None, 'x-default')})[:12]

    kept = text[:60000] if kind else ''
    return {
        'url': page_url, 'title': title, 'kind': kind, 'lang': (soup.html.get('lang', '') if soup.html else '')[:12],
        'links': links, 'emails': mail, 'privacy_link': privacy_any, 'footer_privacy_link': privacy_footer,
        'forms': forms, 'banner': _banner(soup, text), 'mixed': pre_info['mixed'], 'consent_mode': pre_info['consent_mode'],
        'age_hint': _snippet(text, AGE_RE), 'lang_switch': switchers, 'hreflangs': hreflangs,
        'translate_widget': bool(re.search(r'goog-te|translate\.google|googtrans', pre_info['inline_js'])),
        'text': kept, 'text_len': len(text), 'text_sample': '' if kind else re.sub(r'\s+', ' ', text[:1500]),
    }
