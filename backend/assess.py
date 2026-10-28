"""Rule engine: evidence from a website scan  +  the owner's answers  ->  a status for each of the 76 checklist items.

Design rules (they are what keeps the tool honest):
  * `met` / `not_met` only when the scan actually observed something. Evidence (page URL + quote) is attached.
  * Things a URL scan cannot see are `input` (a scoping question can settle it) or `not_testable`
    (internal practice: breach plan, contracts...). They are never reported as compliant.
  * Owner answers produce `declared_met` / `declared_gap`: self-declared, unverified, and labelled as such.
  * `na` always says why (usually "you answered X to question Sn").

`evaluate()` is pure and cheap, so it re-runs on every request: answering a question or declaring a check
updates the report instantly without re-crawling.
"""
import json
import re
import urllib.parse
from pathlib import Path

from remediation import FIX

DATA = json.loads((Path(__file__).parent / 'checklist.json').read_text(encoding='utf-8'))
CHECKS = {c['id']: c for c in DATA['checks']}
QUESTIONS = {q['id']: q for q in DATA['questions']}
SECTIONS = {s['letter']: s for s in DATA['sections']}

STATUSES = ('not_met', 'declared_gap', 'review', 'input', 'not_testable', 'declared_met', 'met', 'na')
RISK_ORDER = {'H': 0, 'M': 1, 'L': 2}

def penalty_for(cid):
    """Maximum penalty tier linked to a check (Schedule to the Act, s.33; Penalties sheet rows in order)."""
    sec, num = cid[0], int(cid[1:])
    pens = DATA['penalties']
    if CHECKS[cid]['basis'].strip().lower().startswith('good to have'):  # best practice, not an Act/Rules duty: no penalty tier
        return {'label': 'Good practice (no direct statutory penalty)', 'max': '', 'crore': 0}
    if sec == 'F' and num in (10, 11):
        p, crore = pens[1], 200
    elif sec == 'F':
        p, crore = pens[0], 250
    elif sec == 'D':
        p, crore = pens[2], 200
    elif sec == 'J':
        p, crore = pens[3], 150
    else:
        p, crore = pens[4], 50
    return {'label': p['breach'].split('(')[0].strip() if sec in 'DFJ' else 'Other provisions of the Act or Rules',
            'max': p['max'], 'crore': crore}


# --------------------------------------------------------------------------------------------- vocab

AD_HOSTS = ('doubleclick', 'googlesyndication', 'googleadservices', 'adservice.google', 'facebook.net', 'facebook.com', 'ads-twitter',
            'analytics.twitter', 'px.ads.linkedin', 'snap.licdn', 'tiktok', 'criteo', 'taboola', 'outbrain', 'adnxs', 'adsrvr',
            'bat.bing', 'sc-static.net', 'ct.pinterest', 'ads.linkedin', 'quantserve', 'amazon-adsystem')
ANALYTICS_HOSTS = ('google-analytics', 'analytics.google', 'hotjar', 'clarity.ms', 'mixpanel', 'segment.', 'amplitude', 'fullstory',
                   'mouseflow', 'clevertap', 'moengage', 'webengage', 'heapanalytics', 'crazyegg', 'newrelic', 'nr-data', 'sentry.io',
                   'branch.io', 'appsflyer', 'hs-analytics', 'hubspot')
TAGMANAGER_HOSTS = ('googletagmanager',)
CMP_HOSTS = {'cookielaw.org': 'OneTrust', 'onetrust': 'OneTrust', 'cookiebot': 'Cookiebot', 'cookieyes': 'CookieYes', 'termly': 'Termly',
             'trustarc': 'TrustArc', 'usercentrics': 'Usercentrics', 'osano': 'Osano', 'didomi': 'Didomi', 'quantcast': 'Quantcast Choice',
             'iubenda': 'iubenda', 'cookiefirst': 'CookieFirst', 'consentmanager': 'consentmanager', 'cookie-script': 'Cookie-Script'}
EMBED_HOSTS = {
    'video': ('youtube', 'youtu.be', 'vimeo', 'wistia', 'jwplatform'),
    'maps': ('maps.googleapis', 'maps.google', 'mapbox', 'google.com/maps'),
    'chat': ('intercom', 'drift.com', 'tawk.to', 'zendesk', 'zopim', 'freshchat', 'freshworks', 'crisp.chat', 'livechatinc', 'tidio',
             'gupshup', 'botpress', 'landbot', 'kommunicate', 'haptik', 'yellow.ai', 'hs-scripts', 'hubspot'),
    'social widgets': ('platform.twitter', 'connect.facebook', 'instagram.com', 'linkedin.com', 'addthis', 'sharethis', 'twitter.com'),
    'hosted fonts': ('fonts.googleapis', 'fonts.gstatic', 'typekit', 'fontawesome'),
    'payments': ('razorpay', 'stripe', 'paytm', 'payu', 'ccavenue', 'billdesk', 'cashfree', 'phonepe', 'paypal', 'instamojo', 'juspay'),
    'cdn': ('cloudflare', 'cloudfront', 'akamai', 'jsdelivr', 'unpkg', 'cdnjs', 'fastly', 'azureedge', 'gstatic', 'bootstrapcdn'),
}
TRACKING_COOKIE_RE = re.compile(r'^(_ga|_gid|_gat|_gcl|_fbp|_fbc|_hj|_clck|_clsk|ajs_|amplitude|mp_|__utm|_pin_|_ttp|_uet|IDE$|fr$|_scid|_li_|li_fat_id|hubspotutk|__hs)', re.I)
SESSION_COOKIE_RE = re.compile(r'sess|sid\b|token|auth|jwt|csrf|xsrf|login|phpsessid', re.I)

DATA_CATS = {'name': r'\bname\b', 'email': r'e-?mail', 'phone': r'phone|mobile|telephone|contact number', 'address': r'\baddress\b|postal|pin ?code',
             'date of birth': r'date of birth|\bdob\b|\bage\b', 'device / IP / cookies': r'ip address|device|browser|cookies?|identifiers?',
             'location': r'location|gps|geolocation', 'payment / financial': r'payment|card|bank|financial|transaction',
             'government ID': r'aadhaar|aadhar|\bpan\b|passport|identity (proof|document)', 'employment': r'resume|\bcv\b|employment|job application'}
FORM_CAT_MAP = {'email': r'e-?mail', 'phone': r'phone|mobile|\btel\b', 'name': r'\bname\b|first|last', 'address': r'address|pin|zip|city',
                'date of birth': r'dob|birth', 'government ID': r'aadhaar|aadhar|\bpan\b|passport', 'employment': r'resume|\bcv\b'}
RIGHTS_RX = {
    'access': r'right to access|access (to )?(your |the )?(personal )?(data|information)|(request|obtain|receive) (a )?(copy|summary|access)',
    'correction': r'correct(ion)?\b|rectif|update (your|the) (personal )?(data|information)|complet(e|ion) (of )?(your )?(data|information)',
    'erasure': r'erasure|erase\b|delet(e|ion)|remov(e|al) (of )?(your )?(personal )?(data|information)',
    'grievance': r'grievance|complain|redress',
    'nomination': r'nominat',
}
WITHDRAW_RX = r'withdraw(al)?( of)?( your)? consent|opt[\s-]?out|unsubscribe|revoke (your )?consent|withdraw your'
BOARD_RX = r'data protection board|\bdpb\b'
DPO_RX = r'data protection officer|\bdpo\b|grievance officer|nodal officer|privacy officer|designated (person|officer)|contact person'
EMAIL_RX = r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'
PHONE_RX = r'(?:\+?\d[\d\s\-()]{8,}\d)'
IDENT_RX = r'verify (your )?(identity|account)|identif(y|ication) (you|of the (user|requester))|registered (e-?mail|mobile|phone)|proof of identity|username|account (id|identifier)'
PURPOSE_RX = r'purposes?\b|we (use|collect|process|share)[^.]{0,100}\b(to|for)\b|used (to|for)|in order to'
RETENTION_RX = r'retain|retention|stored for|keep (your )?(data|information)|as long as (necessary|required|needed)'
OVERSEAS_RX = r'outside india|overseas|cross[\s-]?border|international(ly)? (transfer|data)|other countries|transfer(red)? (of )?(your )?(personal )?(data|information)|servers? (are )?(located )?(in|outside)'
WAIVER_RX = r'\bwaive[sdr]?\b|\bwaiver\b|release[sd]? us from|you (hereby )?agree not to (file|bring|raise|complain)|class[\s-]?action waiver'
DATE_RX = r'(last (updated|modified|revised)|effective( date| from)?|updated on|version)\s*[:\-]?\s*[\w./ ,-]{3,25}'
CONSENT_LABEL_RX = r'consent|agree|accept|marketing|newsletter|subscribe|updates|promotion|terms|privacy|contact me|communicat'
MARKETING_RX = r'marketing|newsletter|promotion|offers?|updates|communicat|subscribe|contact me'
TERMS_RX = r'terms|privacy|policy|conditions'
CHILDREN_RX = r'\bchild(ren)?\b|\bkids?\b|\bminors?\b|students?|school|under\s*18'
ENGLISH_STOP = {'the', 'and', 'of', 'to', 'your', 'we', 'you', 'is', 'for', 'in', 'that', 'with', 'this', 'are', 'data', 'personal'}


# --------------------------------------------------------------------------------------------- helpers

def r(status, note, ev=None, ask=None):
    return {'status': status, 'note': note, 'evidence': ev or [], 'ask': ask or []}


def E(label, detail='', url=None):
    return {'label': label, 'detail': (detail or '')[:420], 'url': url}


def snip(rx, text, width=170):
    m = re.search(rx, text or '', re.I)
    if not m:
        return ''
    a, b = max(0, m.start() - width // 2), min(len(text), m.end() + width // 2)
    return ('…' if a else '') + re.sub(r'\s+', ' ', text[a:b]).strip() + ('…' if b < len(text) else '')


def host_of(u):
    return (urllib.parse.urlsplit(u).hostname or '').lower()


def brand(host):
    """Registrable-name label: shop.example.co.in -> 'example'. Same brand on another TLD is treated as the same owner."""
    parts = (host or '').lower().rstrip('.').split('.')
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ('co', 'com', 'org', 'net', 'gov', 'ac', 'edu', 'nic', 'res', 'ltd'):
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else '')


def classify(host):
    h = host.lower()
    for k in AD_HOSTS:
        if k in h:
            return 'advertising'
    for k in ANALYTICS_HOSTS:
        if k in h:
            return 'analytics'
    for k in TAGMANAGER_HOSTS:
        if k in h:
            return 'tag manager'
    for k in CMP_HOSTS:
        if k in h:
            return 'consent platform'
    for cat, keys in EMBED_HOSTS.items():
        if any(k in h for k in keys):
            return cat
    return 'other'


class Ctx:
    """Everything the rules need, derived once from the scan evidence and the owner's answers."""

    def __init__(self, scan, scope):
        e = scan.get('evidence') or {}
        self.scan, self.e, self.scope = scan, e, scope
        self.mode = scan.get('mode', 'static')
        all_pages = e.get('pages') or []
        self.pages = [p for p in all_pages if not p.get('offsite')]  # pages of the site itself
        self.cookies = e.get('cookies') or []
        self.headers = e.get('headers') or {}
        self.findings = scan.get('findings') or []
        self.blind = bool(e.get('incomplete_spa'))
        own = brand(e.get('host') or urllib.parse.urlsplit(scan.get('target', '')).hostname or '')
        # subdomains and same-brand domains (blog.example.in for example.com) are the site's own, not third parties
        self.hosts = [h for h in (scan.get('third_party_hosts') or []) if not own or brand(h) != own]
        self.cat = {h: classify(h) for h in self.hosts}
        self.trackers = [h for h in self.hosts if self.cat[h] in ('advertising', 'analytics')]
        self.ad_hosts = [h for h in self.hosts if self.cat[h] == 'advertising']
        self.cmps = sorted({v for h in self.hosts for k, v in CMP_HOSTS.items() if k in h})
        read = [p for p in all_pages if p.get('text')]  # includes an off-site notice the site links to
        self.privacy_pages = [p for p in read if p.get('kind') == 'privacy']
        self.other_notice = [p for p in read if p.get('kind') in ('cookie', 'grievance')]
        self.terms_pages = [p for p in read if p.get('kind') == 'terms']
        self.notice_text = '\n'.join(p['text'] for p in self.privacy_pages + self.other_notice)
        self.policy_text = self.notice_text + '\n' + '\n'.join(p['text'] for p in self.terms_pages)
        self.notice_url = (self.privacy_pages or self.other_notice or [{}])[0].get('url')
        self.banner = next((p['banner'] for p in self.pages if p.get('banner')), None)
        self.banner_url = next((p['url'] for p in self.pages if p.get('banner')), None)
        seen, self.forms = set(), []
        for p in self.pages:
            for f in p.get('forms') or []:
                key = (f['kind'], tuple(sorted(x['name'] for x in f['fields'])), f['action'])
                if key not in seen:
                    seen.add(key)
                    self.forms.append(f)
        # forms that actually collect personal data (a search box or a login form is not a collection point for the notice)
        self.pforms = [f for f in self.forms if f['personal'] and f['kind'] not in ('login', 'search')]
        self._links = {}
        for p in self.pages:
            for kind, lst in (p.get('links') or {}).items():
                for l in lst:
                    d = self._links.setdefault(kind, {})
                    d.setdefault(l['href'], {**l, 'page': p['url']})
        self.emails = sorted({m.lower() for m in re.findall(EMAIL_RX, self.notice_text)} | {x for p in self.pages for x in p.get('emails') or []})
        # a notice is linked from the site but its text was not read: absence of wording proves nothing then
        self.unread = (not self.notice_text.strip()) and bool(self._links.get('privacy'))

    # owner answers ---------------------------------------------------------------------------
    def s(self, qid):
        return self.scope.get(qid)

    def tri(self, qid):
        v = self.scope.get(qid)
        if v in (None, '', []):
            return None
        v = (v[0] if isinstance(v, list) and v else v)
        v = str(v).strip().lower()
        if v.startswith('yes'):
            return 'yes'
        if v.startswith('no'):
            return 'no'
        return 'unsure'

    def has(self, qid, text):
        v = self.scope.get(qid)
        if v in (None, '', []):
            return False
        items = v if isinstance(v, list) else [v]
        return any(text.lower() in str(i).lower() for i in items)

    def answered(self, qid):
        return self.scope.get(qid) not in (None, '', [])

    def links(self, kind):
        return list(self._links.get(kind, {}).values())

    def link_ev(self, kind, n=4):
        return [E(f'{kind} link', f"“{l['text'] or l['href']}”", l['href']) for l in self.links(kind)[:n]]

    def kids(self):
        """True / False / None (not yet answered) - are children in scope?"""
        v = [self.tri('S4'), self.tri('S31')]
        if 'yes' in v or 'unsure' in v:
            return True
        return False if 'no' in v else None

    def english(self, text):
        words = re.findall(r'[a-z]+', text.lower())
        return len(words) > 80 and sum(w in ENGLISH_STOP for w in words) / len(words) > 0.12


def blind_result():
    return r('review', 'This site builds its pages with JavaScript and the scan ran without a browser, so this could not be observed. '
                       'Enable browser rendering and scan again.')


def notice_gate(c, what='this'):
    """Early exit for rules that read the privacy notice. Returns a result dict, or None when a notice was read."""
    if c.blind:
        return blind_result()
    if c.notice_text:
        return None
    links = c.links('privacy')
    if links:
        return r('review', f'A privacy link was found but its page could not be read ({links[0]["href"]}). It may be hosted on another '
                           f'domain or beyond the page limit, so {what} could not be checked.', c.link_ev('privacy', 3))
    return r('not_met', f'No privacy notice was found on the pages scanned, so {what} cannot be satisfied.')


RULES = {}


def rule(*ids):
    def deco(fn):
        for i in ids:
            RULES[i] = fn
        return fn
    return deco


# --------------------------------------------------------------------------------------------- A. Notice

@rule('A1')
def a1(c):
    if c.blind:
        return blind_result()
    pf = c.pforms
    if not pf:
        return r('input', 'No data-collection forms were found on the pages scanned. Tell us which collection points exist.', ask=['S13'])
    ev = [E(f'{f["kind"]} form', 'Fields: ' + ', '.join(x['name'] or x['type'] for x in f['fields'][:6]) + ('. Privacy notice link at the form.'
          if f['privacy_near'] else '. No privacy notice link at the form.'), f['url']) for f in pf[:8]]
    missing = [f for f in pf if not f['privacy_near']]
    if missing:
        return r('not_met', f'{len(missing)} of {len(pf)} forms collect personal data with no privacy notice link at the point of collection.', ev, ['S13'])
    return r('met', f'All {len(pf)} personal-data forms found have a privacy notice link at the point of collection.', ev, ['S13'])


@rule('A2')
def a2(c):
    g = notice_gate(c, 'itemised data categories')
    if g:
        return g
    found = {k: snip(rx, c.notice_text) for k, rx in DATA_CATS.items() if re.search(rx, c.notice_text, re.I)}
    collected = set()
    for f in c.forms:
        sig = ' '.join(x['name'] + ' ' + x.get('hint', '') for x in f['fields'])
        for cat, rx in FORM_CAT_MAP.items():
            if re.search(rx, sig, re.I):
                collected.add(cat)
        if any(x['type'] in ('email',) for x in f['fields']):
            collected.add('email')
        if any(x['type'] == 'tel' for x in f['fields']):
            collected.add('phone')
    gaps = sorted(k for k in collected if k not in found)
    ev = [E(f'Notice mentions “{k}”', s, c.notice_url) for k, s in list(found.items())[:5]]
    if gaps:
        ev.append(E('Collected by forms but not found in notice text', ', '.join(gaps)))
    if len(found) == 0:
        return r('not_met', 'The notice does not itemise the personal data it collects (no data categories found in its text).', ev, ['S17'])
    if gaps:
        return r('review', f'Forms collect {", ".join(gaps)} but the notice text does not name it. Check that the notice itemises every category.', ev, ['S17'])
    return r('met' if len(found) >= 3 else 'review',
             f'The notice names {len(found)} data categories' + ('.' if len(found) >= 3 else '; fewer than expected, check it is complete.'), ev, ['S17'])


@rule('A3')
def a3(c):
    g = notice_gate(c, 'specified purposes')
    if g:
        return g
    hits = len(re.findall(PURPOSE_RX, c.notice_text, re.I))
    q = snip(PURPOSE_RX, c.notice_text)
    if hits == 0:
        return r('not_met', 'No statement of purposes was found in the notice text.')
    return r('review', f'The notice describes purposes ({hits} mentions). A person must judge whether each purpose is specific and tied to the service '
                       'it enables; vague purposes ("improve our services") do not meet s.5.', [E('Purpose wording', q, c.notice_url)])


@rule('A4')
def a4(c):
    g = notice_gate(c, 'plain language')
    if g:
        return g
    p = (c.privacy_pages or c.other_notice)[0]
    words = re.findall(r'[A-Za-z]+', p['text'])
    sentences = max(1, len(re.findall(r'[.!?]+', p['text'])))
    sample = words[:3000]
    syll = sum(max(1, len(re.findall(r'[aeiouy]+', w.lower()))) for w in sample)
    ease = round(206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syll / max(1, len(sample))))
    standalone = bool(c.privacy_pages)
    ev = [E('Notice page', f'{len(words)} words; Flesch reading ease ≈ {ease} (higher is easier; 30-50 is typical legal English)', p['url'])]
    ev.append(E('Standalone page', 'The notice is its own page, not only a clause in the terms.' if standalone
                else 'Only a cookie/grievance page was found; no standalone privacy notice page.'))
    return r('review', 'A standalone notice exists; plain language and independent readability need human judgement.' if standalone
             else 'No standalone privacy notice page was found; check the notice is not buried in the terms.', ev)


@rule('A5')
def a5(c):
    g = notice_gate(c, 'a withdrawal route')
    if g:
        return g
    q = snip(WITHDRAW_RX, c.notice_text)
    if not q:
        return r('not_met', 'The notice does not say how consent can be withdrawn.')
    contact = bool(re.search(EMAIL_RX, c.notice_text)) or bool(c.links('withdraw'))
    return r('met' if contact else 'review',
             'The notice describes withdrawal and gives a way to do it.' if contact else 'The notice mentions withdrawal but gives no email or link to do it.',
             [E('Withdrawal wording', q, c.notice_url)] + c.link_ev('withdraw', 2))


@rule('A6')
def a6(c):
    g = notice_gate(c, 'a rights description')
    if g:
        return g
    found = {k: snip(rx, c.notice_text) for k, rx in RIGHTS_RX.items() if re.search(rx, c.notice_text, re.I)}
    missing = [k for k in RIGHTS_RX if k not in found]
    ev = [E(f'Mentions {k}', s, c.notice_url) for k, s in found.items()]
    if not missing:
        return r('met', 'The notice covers access, correction, erasure, grievance and nomination.', ev)
    note = f'Not found in the notice text: {", ".join(missing)}.'
    return r('review' if len(found) >= 3 else 'not_met', note, ev)


@rule('A7')
def a7(c):
    g = notice_gate(c, 'the Board complaint route')
    if g:
        return g
    q = snip(BOARD_RX, c.notice_text)
    if q:
        return r('met', 'The notice names the Data Protection Board as the complaint route.', [E('Notice wording', q, c.notice_url)])
    q = snip(r'\bboard\b[^.]{0,80}complain|complain[^.]{0,80}\bboard\b', c.notice_text)
    if q:
        return r('review', 'A complaint to a "board" is mentioned but the Data Protection Board is not named.', [E('Notice wording', q, c.notice_url)])
    return r('not_met', 'The notice does not mention the right to complain to the Data Protection Board.')


@rule('A8')
def a8(c):
    if c.blind:
        return blind_result()
    sw = [p for p in c.pages if p.get('lang_switch') or p.get('hreflangs') or p.get('translate_widget')]
    ev = []
    if sw:
        p = sw[0]
        ev.append(E('Language options found', ', '.join((p['lang_switch'][0] if p.get('lang_switch') else p.get('hreflangs') or ['translate widget'])[:8]), p['url']))
    if c.notice_text and c.english(c.notice_text):
        return r('met', 'The notice is available in English, which satisfies s.5(3). ' + ('A language switcher is also present.' if sw else ''), ev)
    if c.s('S22'):
        return r('review', 'Languages declared by you: ' + ', '.join(c.s('S22') if isinstance(c.s('S22'), list) else [c.s('S22')]) +
                 '. Confirm the notice and consent request exist in each.', ev, ['S22'])
    return r('input', 'Could not confirm the notice is in English or another listed language. Tell us which languages it is offered in.', ev, ['S22'])


@rule('A9')
def a9(c):
    t = c.tri('S20')
    if t == 'no':
        return r('na', 'You said no personal data predates commencement (S20).', ask=['S20'])
    if t is None:
        return r('input', 'Do you hold personal data collected before the Act commenced (old mailing lists, user databases)?', ask=['S20'])
    return r('not_testable', 'Not visible from outside. Confirm a notice has been sent to existing users and attach a copy.', ask=['S20'])


@rule('A10')
def a10(c):
    g = notice_gate(c, 'notice dating')
    if g:
        return g
    q = snip(DATE_RX, c.notice_text)
    if q:
        return r('review', 'The notice shows a date or version. Whether every earlier version is retained cannot be seen from outside.',
                 [E('Date / version', q, c.notice_url)])
    return r('not_met', 'No "last updated", effective date or version number was found on the notice.', [E('Notice page', '', c.notice_url)])


@rule('A11')
def a11(c):
    if c.blind:
        return blind_result()
    pages = [p for p in c.pages if p.get('text_len', 0) > 0 or p.get('links')]
    if not pages:
        return r('review', 'No pages could be analysed.')
    without = [p for p in pages if not p.get('privacy_link')]
    foot = sum(1 for p in pages if p.get('footer_privacy_link'))
    ev = [E('Page without a privacy link', '', p['url']) for p in without[:6]]
    if not without:
        return r('met', f'A privacy link appears on all {len(pages)} pages scanned ({foot} in the footer).', c.link_ev('privacy', 2))
    if len(without) == len(pages):
        return r('not_met', 'No privacy link was found on any page scanned.', ev)
    return r('not_met', f'{len(without)} of {len(pages)} pages scanned {"has" if len(without) == 1 else "have"} no privacy link.', ev)


# --------------------------------------------------------------------------------------------- B. Consent

@rule('B1')
def b1(c):
    if not c.answered('S19'):
        return r('input', 'Which lawful basis do you rely on for each collection point (consent, voluntary provision, employment…)?', ask=['S19'])
    return r('declared_met', 'Basis declared: ' + ', '.join(c.s('S19') if isinstance(c.s('S19'), list) else [c.s('S19')]) +
             '. Unverified: attach the record of processing or a legal note.', ask=['S19'])


@rule('B2')
def b2(c):
    if c.blind:
        return blind_result()
    ticked = [(f, cb) for f in c.forms for cb in f['checkboxes'] if cb['checked'] and re.search(CONSENT_LABEL_RX, cb['label'], re.I)]
    ev = [E('Pre-ticked box', f'“{cb["label"][:120]}”', f['url']) for f, cb in ticked[:5]]
    if c.banner and c.banner.get('implied'):
        ev.append(E('Banner relies on implied consent', c.banner['implied'], c.banner_url))
        return r('not_met', 'The cookie/consent banner treats continued browsing as agreement, which is not a clear affirmative action.', ev)
    if ticked:
        return r('not_met', f'{len(ticked)} consent checkbox(es) are pre-ticked.', ev)
    boxes = [(f, cb) for f in c.forms for cb in f['checkboxes'] if re.search(CONSENT_LABEL_RX, cb['label'], re.I)]
    if boxes:
        ev = [E('Unticked consent box', f'“{cb["label"][:120]}”', f['url']) for f, cb in boxes[:4]]
        return r('met', f'{len(boxes)} consent checkbox(es) found, none pre-ticked, and no "by continuing you agree" wording in the banner.', ev)
    implied = [f for f in c.pforms if f.get('implied')]
    if implied:
        return r('review', 'Forms say "by submitting you agree…" with no consent checkbox. Pressing submit may count as an affirmative action, but a separate tick is safer.',
                 [E('Wording', f['implied'], f['url']) for f in implied[:3]])
    if c.pforms:
        return r('review', 'Forms were found but none show a consent checkbox or consent wording.', [E(f'{f["kind"]} form', '', f['url']) for f in c.pforms[:4]], ['S13'])
    return r('input', 'No data-collection forms or consent controls were found. Tell us which collection points exist.', ask=['S13'])


@rule('B3')
def b3(c):
    if c.blind:
        return blind_result()
    bundled, separate = [], []
    for f in c.forms:
        labs = [cb['label'] for cb in f['checkboxes']]
        for lab in labs:
            if re.search(TERMS_RX, lab, re.I) and re.search(MARKETING_RX, lab, re.I):
                bundled.append((f, lab))
        if len(labs) >= 2 and any(re.search(MARKETING_RX, l, re.I) for l in labs):
            separate.append(f)
    if bundled:
        return r('not_met', 'A single checkbox bundles agreement to terms/privacy with marketing, so consent is not specific.',
                 [E('Bundled checkbox', f'“{lab[:140]}”', f['url']) for f, lab in bundled[:4]])
    if separate:
        return r('met', 'Marketing has its own separate checkbox, apart from the terms.',
                 [E('Separate choices', ' | '.join(cb['label'][:60] for cb in f['checkboxes']), f['url']) for f in separate[:3]])
    if c.pforms:
        return r('review', 'Forms were found but no separate per-purpose choices could be observed. Confirm marketing is not bundled with the service.',
                 [E(f'{f["kind"]} form', ' | '.join(cb['label'][:60] for cb in f['checkboxes']) or 'no checkboxes', f['url']) for f in c.pforms[:4]], ['S24'])
    return r('input', 'No forms were found to test. Tell us which collection points and marketing channels exist.', ask=['S13', 'S24'])


@rule('B4')
def b4(c):
    if c.blind:
        return blind_result()
    pf = c.pforms
    if not pf:
        return r('input', 'No data-collection forms were found. Tell us which collection points exist.', ask=['S13'])
    ev = [E(f'{f["kind"]} form', 'Asks for: ' + ', '.join((x['name'] or x['hint'] or x['type']) for x in f['fields'][:8]) +
            (f'. Sensitive-looking: {", ".join(f["sensitive"])}' if f['sensitive'] else ''), f['url']) for f in pf[:8]]
    flagged = [f for f in pf if f['sensitive'] and f['kind'] in ('contact', 'newsletter', 'lead', 'other')]
    return r('review', ('Some simple forms ask for sensitive fields; check each is necessary for the stated purpose.' if flagged else
                        'Fields collected are listed below. Only a person can judge whether each is necessary for its purpose.'), ev, ['S17'])


@rule('B5')
def b5(c):
    g = notice_gate(c, 'contact details')
    if g:
        return g
    m = re.search(DPO_RX, c.notice_text, re.I)
    em = sorted(c.emails)[:3]
    ev = ([E('Contact wording', snip(DPO_RX, c.notice_text), c.notice_url)] if m else []) + ([E('Email', ', '.join(em))] if em else [])
    if m or em:
        return r('review', 'Contact details appear in the notice. Confirm the consent request itself (form/banner) carries or links to them.', ev, ['S35'])
    return r('not_met', 'No DPO or contact person details were found in the notice.', ask=['S35'])


@rule('B6')
def b6(c):
    if c.blind:
        return blind_result()
    if not c.policy_text.strip():
        return r('review', 'No notice or terms text was read, so waiver clauses could not be checked.')
    q = snip(WAIVER_RX, c.policy_text)
    if q:
        return r('review', 'Wording that may waive a statutory right was found. Under s.6(2) such a term is invalid; have it reviewed.', [E('Possible waiver wording', q)])
    return r('met', f'No waiver-of-rights wording was found in the {len(c.privacy_pages) + len(c.other_notice) + len(c.terms_pages)} policy page(s) read. '
                    'A full legal review of the terms is still advisable.')


@rule('B7')
def b7(c):
    if c.blind:
        return blind_result()
    links = c.links('withdraw')
    note_q = snip(WITHDRAW_RX, c.notice_text)
    if links:
        return r('review', 'A withdrawal / unsubscribe / preferences link exists. Check it takes no more clicks than giving consent did, and '
                           'test the in-account route if there is a login.', c.link_ev('withdraw', 5), ['S14'])
    if note_q:
        return r('review', 'The notice describes withdrawal but no withdrawal link was found on the site.', [E('Notice wording', note_q, c.notice_url)], ['S14'])
    if not c.notice_text.strip():
        return r('review', 'No withdrawal link was found on the site and the privacy notice could not be read, so how consent is withdrawn is unknown.', c.link_ev('privacy', 2), ['S14'])
    return r('not_met', 'No withdrawal, unsubscribe or consent-preferences link was found, and the notice does not describe how to withdraw.', ask=['S14'])


@rule('B8')
def b8(c):
    return r('not_testable', 'Internal: when consent is withdrawn, processing (including at processors) must stop. Describe the process and attach the procedure.')


@rule('B9')
def b9(c):
    if not c.answered('S21'):
        return r('input', 'What does your consent log record for each consent?', ask=['S21'])
    need = ['user or session id', 'timestamp', 'purposes', 'notice version', 'channel']
    if c.has('S21', 'none'):
        return r('declared_gap', 'You said no consent log is kept, so notice and consent cannot be proved (s.6(10)).', ask=['S21'])
    missing = [n for n in need if not c.has('S21', n)]
    if missing:
        return r('declared_gap', 'Your consent log is missing: ' + ', '.join(missing) + '. Without these, proof of notice and consent is incomplete.', ask=['S21'])
    return r('declared_met', 'You declared the consent log records ID, timestamp, purposes, notice version and channel. Unverified: attach a sample log.', ask=['S21'])


@rule('B10')
def b10(c):
    return r('not_testable', 'Optional for the Data Principal and relevant from Nov 2026. Confirm whether your consent flow can accept a registered Consent Manager.')


@rule('B11')
def b11(c):
    if c.blind:
        return blind_result()
    if c.mode != 'browser':
        return r('review', 'Cookie and tracker behaviour at page load can only be observed with browser rendering, which was not available. Re-scan with it enabled.')
    track_cookies = [k for k in c.cookies if TRACKING_COOKIE_RE.search(k['name'])]
    ev = [E('Tracker contacted at page load', f'{h} ({c.cat[h]})', c.pages[0]['url'] if c.pages else None) for h in c.trackers[:8]]
    ev += [E('Tracking cookie set at page load', f'{k["name"]} ({k["domain"]})') for k in track_cookies[:6]]
    b = c.banner
    if b:
        ev.append(E('Banner buttons found', ', '.join(b['buttons'][:8]) or '(none labelled)', c.banner_url))
    if c.trackers or track_cookies:
        return r('not_met', f'{len(c.trackers)} analytics/advertising host(s) and {len(track_cookies)} tracking cookie(s) were active on first load, '
                            'before any consent choice was made.' + ('' if b else ' No consent banner was detected.'), ev)
    if not b:
        return r('met', 'No analytics/advertising trackers or tracking cookies fired on first load, so no consent banner is needed for them.', ev)
    if b['reject'] and b['manage']:
        return r('review', 'A banner with Accept, Reject and a manage option exists and no trackers fired before consent. Confirm Reject has equal prominence.', ev)
    return r('review', 'A banner exists and no trackers fired before consent, but ' + ('there is no Reject option on the first layer.' if not b['reject'] else 'no granular categories were found.'), ev)


@rule('B12')
def b12(c):
    if c.blind:
        return blind_result()
    b = c.banner
    if not b:
        return r('review', 'No consent banner was observed. If consent is requested elsewhere, check it for hidden declines or nudging.')
    ev = [E('Banner buttons', ', '.join(b['buttons'][:8]) or '(none labelled)', c.banner_url), E('Banner text', b.get('excerpt', ''))]
    if b['accept'] and not b['reject']:
        return r('not_met', 'The banner offers Accept but no Reject / decline control on its first layer, which makes declining harder than accepting.', ev)
    return r('review', 'Accept and Reject controls both exist. Visual prominence and confusing toggles need a human look at the banner.', ev)


@rule('B13')
def b13(c):
    if c.blind:
        return blind_result()
    consent_mode = any(p.get('consent_mode') for p in c.pages)
    if not c.trackers and not any(h for h in c.hosts if c.cat[h] == 'tag manager'):
        return r('na', 'No analytics or advertising tags were observed, so there is nothing to pass consent changes to.')
    ev = [E('Consent platform detected', ', '.join(c.cmps))] if c.cmps else []
    if consent_mode:
        ev.append(E('Consent signalling in page code', 'consent API call found (e.g. Google Consent Mode / TCF)'))
    if c.cmps or consent_mode:
        return r('review', 'A consent platform or consent signalling exists. Check that tags actually stop/start when the choice changes.', ev)
    return r('not_met', 'Tags are present but no consent platform or consent signal (Consent Mode, TCF) was detected.',
             [E('Tag', h) for h in (c.trackers or c.hosts)[:5]])


# --------------------------------------------------------------------------------------------- C. Legitimate uses

@rule('C1')
def c1(c):
    if not c.answered('S19'):
        return r('input', 'Do you rely on voluntary provision (s.7(a)) for any collection point?', ask=['S19'])
    if not c.has('S19', 'voluntary'):
        return r('na', 'You rely on consent rather than voluntary provision (S19).', ask=['S19'])
    return r('not_testable', 'You rely on s.7(a). Confirm use is limited to the purpose given and stops when the person no longer needs the service.', ask=['S19'])


@rule('C2')
def c2(c):
    t = c.tri('S15')
    ev = c.link_ev('careers', 2)
    if t == 'no':
        return r('na', 'You said the site collects no applicant or employee data (S15).', ask=['S15'])
    if t == 'yes' or c.has('S19', 'employment'):
        return r('not_testable', 'You process employment data. Confirm it is limited to employment purposes and attach the HR privacy notice.', ev, ['S15'])
    return r('input', 'A careers page was detected. Do you collect job-applicant or employee data?' if ev else 'Do you collect job-applicant or employee data?', ev, ['S15'])


@rule('C3')
def c3(c):
    return r('not_testable', 'Internal: keep a record of each disclosure required by law or court order.')


# --------------------------------------------------------------------------------------------- D. Children

@rule('D1')
def d1(c):
    k = c.kids()
    hints = [E('Age wording', p['age_hint'], p['url']) for p in c.pages if p.get('age_hint')][:3]
    dob = [f for f in c.forms if any(re.search(r'dob|birth|\bage\b', x['name'] + x.get('hint', ''), re.I) for x in f['fields'])]
    hints += [E('Date-of-birth field', 'Form asks for age / date of birth', f['url']) for f in dob[:2]]
    if k is False:
        return r('na', 'You said the site is not used by children (S4 / S31).', ask=['S4', 'S31'])
    if k is None:
        return r('input', 'Could children (under 18) use this site? This switches on checks D1 to D6.', hints, ['S4', 'S31'])
    if hints:
        return r('review', 'An age declaration or age-related wording exists. Confirm it works as a gate and routes under-18s to parental consent.', hints, ['S4', 'S32'])
    return r('not_met', 'Children may use the site but no age gate, age field or age wording was found.', ask=['S4', 'S32'])


@rule('D2')
def d2(c):
    k = c.kids()
    if k is False:
        return r('na', 'You said the site is not used by children (S4 / S31).')
    if k is None:
        return r('input', 'Answer whether children may use the site first.', ask=['S4', 'S31'])
    v = c.s('S32')
    if not v:
        return r('input', 'How is a parent’s identity and age verified?', ask=['S32'])
    v = str(v).lower()
    if v.startswith('none') or v.startswith('self'):
        return r('declared_gap', 'Self-declaration or no check does not meet R.10 due diligence that the parent is an identifiable adult.', ask=['S32'])
    return r('declared_met', f'You declared: {c.s("S32")}. Unverified: attach the verification flow.', ask=['S32'])


@rule('D3')
def d3(c):
    t = c.tri('S34')
    if t == 'no':
        return r('na', 'You said the site does not serve persons with a lawful guardian (S34).', ask=['S34'])
    if t is None:
        return r('input', 'Does the site serve persons with disability who act through a lawful guardian?', ask=['S34'])
    return r('not_testable', 'Confirm how a guardian’s appointment is verified and attach the procedure.', ask=['S34'])


@rule('D4')
def d4(c):
    k = c.kids()
    if c.blind:
        return blind_result()
    ev = [E('Tracker at page load', f'{h} ({c.cat[h]})') for h in c.trackers[:8]]
    if k is False:
        return r('na', 'You said the site is not used by children (S4 / S31).', ask=['S4', 'S31'])
    if c.mode != 'browser':
        return r('review', 'Trackers can only be observed with browser rendering, which was unavailable.', ask=['S4'])
    if c.trackers and k is None:
        return r('input', f'{len(c.trackers)} tracker(s) fire on load. If children may use the site this is a problem; tell us whether they can.', ev, ['S4', 'S31'])
    if c.trackers:
        return r('not_met', 'Children may use the site and advertising/analytics trackers fire on page load. Behavioural monitoring and targeted ads aimed at children are prohibited (s.9(3)).', ev)
    if k is None:
        return r('input', 'No trackers were observed. Confirm whether children may use the site.', ask=['S4', 'S31'])
    return r('met', 'No analytics or advertising trackers fired on page load.', ev)


@rule('D5')
def d5(c):
    k = c.kids()
    if k is False:
        return r('na', 'You said the site is not used by children (S4 / S31).')
    if k is None:
        return r('input', 'Answer whether children may use the site first.', ask=['S4', 'S31'])
    return r('not_testable', 'Internal: assess whether any processing could harm a child’s well-being and document the outcome.')


@rule('D6')
def d6(c):
    k = c.kids()
    if k is False:
        return r('na', 'You said the site is not used by children (S4 / S31).')
    if not c.answered('S33'):
        return r('input', 'Are you a clinical establishment, school, crèche or child transport provider (Fourth Schedule)?', ask=['S33'])
    if c.has('S33', 'none') and not [x for x in (c.s('S33') or []) if 'none' not in str(x).lower()]:
        return r('na', 'You are not in a Fourth Schedule class (S33).', ask=['S33'])
    return r('not_testable', 'Fourth Schedule exemption claimed. Document that the conditions are met and attach the evidence.', ask=['S33'])


# --------------------------------------------------------------------------------------------- E. Rights and grievance

@rule('E1')
def e1(c):
    if c.blind:
        return blind_result()
    links = c.links('rights') + c.links('grievance')
    rights_mail = [e for e in c.emails if re.match(r'(privacy|dpo|grievance|dataprotection|data\.protection|compliance|nodal|redress)', e)]
    ev = c.link_ev('rights', 3) + c.link_ev('grievance', 2) + ([E('Email', ', '.join(rights_mail[:3]))] if rights_mail else [])
    if links or rights_mail:
        return r('met', 'A way to make a rights request (link or dedicated email) is published.', ev, ['S37'])
    t = c.s('S37')
    if t:
        return r('review' if str(t).lower() not in ('none',) else 'not_met', 'No rights-request link was found on the site. You declared: ' + str(t) + '.', ev, ['S37'])
    if c.emails:
        return r('review', 'Only a general contact email was found. Rights requests need a published, clear route.', [E('Email', ', '.join(c.emails[:3]))], ['S37'])
    if c.unread:
        return r('review', 'No rights-request link was found on the site, and the privacy notice (where the route is often described) could not be read.', c.link_ev('privacy', 2), ['S37'])
    return r('not_met', 'No rights-request link or email was found on the pages scanned.', ask=['S37'])


@rule('E2')
def e2(c):
    g = notice_gate(c, 'identification particulars')
    if g:
        return g
    q = snip(IDENT_RX, c.notice_text)
    if q:
        return r('met', 'The notice says what is used to identify a requester.', [E('Notice wording', q, c.notice_url)], ['S14'])
    return r('not_met', 'No statement of the particulars needed to identify a requester (username, registered email…) was found in the notice.', ask=['S14'])


@rule('E3')
def e3(c):
    if c.blind:
        return blind_result()
    ev = c.link_ev('dpo', 3)
    for m in re.finditer(DPO_RX, c.policy_text, re.I):
        window = c.policy_text[max(0, m.start() - 200): m.end() + 250]
        if re.search(EMAIL_RX, window) or re.search(PHONE_RX, window):
            ev.append(E('DPO / contact wording', snip(DPO_RX, c.policy_text), c.notice_url))
            return r('met', 'A DPO or designated contact with an email/phone is published. Check it is repeated in every response to a rights request.', ev, ['S35'])
    if ev or re.search(DPO_RX, c.policy_text, re.I):
        return r('review', 'A DPO / contact role is mentioned but no email or phone number sits next to it.', ev, ['S35'])
    if c.has('S35', 'none'):
        return r('not_met', 'No DPO or contact person is published, and you said none exists.', ask=['S35'])
    if c.emails:
        return r('review', 'Only a general email was found; no DPO or designated contact is named.', [E('Email', ', '.join(c.emails[:3]))], ['S35'])
    if c.unread:
        return r('review', 'No DPO or contact person was found on the site, and the privacy notice (where it is usually named) could not be read.', c.link_ev('privacy', 2), ['S35'])
    return r('not_met', 'No DPO or contact person for data-protection queries was found.', ask=['S35'])


_TIME = re.compile(r'(\d{1,3})\s*(?:\(\w+\)\s*)?(business |working |calendar )?(hours?|days?|weeks?|months?)', re.I)


@rule('E4')
def e4(c):
    g = notice_gate(c, 'the grievance timeframe')
    if g:
        v = c.s('S36')
        if g['status'] == 'review' and v:
            return _from_s36(c, v)
        return g
    text = c.policy_text
    mech = bool(re.search(r'grievance|complain|redress', text, re.I)) or bool(c.links('grievance'))
    days = []
    for m in re.finditer(r'grievance|complain|redress|respond|resolv|acknowledg', text, re.I):
        for t in _TIME.finditer(text[max(0, m.start() - 180): m.end() + 220]):
            n, unit = int(t.group(1)), t.group(3).lower()
            days.append(n / 24 if unit.startswith('hour') else n * 7 if unit.startswith('week') else n * 30 if unit.startswith('month') else n)
    ev = [E('Grievance wording', snip(r'grievance|complain|redress', text), c.notice_url)] if mech else []
    if not mech:
        return r('not_met', 'No grievance redressal mechanism was found in the notice or on the site.', ev, ['S36'])
    if not days:
        return r('not_met', 'A grievance mechanism is described but no response time is published (R.14(3) requires one, at most 90 days).', ev, ['S36'])
    longest = max(days)
    ev.append(E('Timeframes found', ', '.join(sorted({f'{d:g} day(s)' for d in days}))))
    if longest > 90:
        return r('not_met', f'A response time of {longest:g} days appears near the grievance wording, which is longer than the 90-day limit.', ev, ['S36'])
    return r('met', f'A grievance mechanism is described, and the longest response time found near the grievance wording is {longest:g} day(s) (limit: 90).', ev, ['S36'])


def _from_s36(c, v):
    v = str(v).lower()
    if 'no grievance' in v or 'no response time' in v or 'but no' in v:
        return r('declared_gap', 'You declared there is no grievance mechanism or no published response time.', ask=['S36'])
    if 'over 90' in v:
        return r('declared_gap', 'You declared a response time of more than 90 days (limit 90).', ask=['S36'])
    return r('declared_met', 'You declared a grievance mechanism with a response time of 90 days or less. Unverified: the notice could not be read.', ask=['S36'])


@rule('E5')
def e5(c):
    ev = []
    q = snip(RIGHTS_RX['access'], c.notice_text)
    if q:
        ev.append(E('Notice promises access', q, c.notice_url))
    return r('not_testable', 'Internal: you must be able to give a summary of data processed and the other fiduciaries/processors it is shared with. Describe the process.', ev, ['S26'])


@rule('E6')
def e6(c):
    ev = [E(f'Notice promises {k}', snip(RIGHTS_RX[k], c.notice_text), c.notice_url) for k in ('correction', 'erasure') if re.search(RIGHTS_RX[k], c.notice_text, re.I)]
    return r('not_testable', 'Internal: correction, completion, updating and erasure on request. Describe the process and attach a sample request log.', ev)


@rule('E7')
def e7(c):
    g = notice_gate(c, 'the nomination right')
    if g:
        return g
    q = snip(RIGHTS_RX['nomination'], c.notice_text)
    if q:
        return r('review', 'The notice mentions nomination. Test that the route works in practice (and inside the account area if there is one).', [E('Notice wording', q, c.notice_url)], ['S14'])
    return r('not_met', 'The notice does not mention the right to nominate another person (s.14).', ask=['S14'])


@rule('E8')
def e8(c):
    v = c.s('S37')
    if not v:
        return r('input', 'How do you receive and track rights requests?', ask=['S37'])
    v = str(v).lower()
    if v == 'none':
        return r('declared_gap', 'You said there is no way to receive or track rights requests.', ask=['S37'])
    if v in ('dedicated portal', 'web form'):
        return r('declared_met', f'You declared requests come through a {v}. Unverified: attach a sample ticket with identity check and deadline.', ask=['S37'])
    return r('review', f'Requests are handled by {v}. Check there is ticketing, identity verification and deadline tracking.', ask=['S37'])


# --------------------------------------------------------------------------------------------- F. Security

def _s42(c, key, label, why):
    if not c.answered('S42'):
        return r('input', f'Which safeguards are in place? ({label})', ask=['S42'])
    if c.has('S42', 'none') and len(c.s('S42') or []) == 1:
        return r('declared_gap', 'You declared none of the listed safeguards are in place.', ask=['S42'])
    if c.has('S42', key):
        return r('declared_met', f'You declared: {label}. Self-declared and cannot be verified from outside; attach evidence.', ask=['S42'])
    return r('declared_gap', f'You did not select "{label}". {why}', ask=['S42'])


@rule('F1')
def f1(c):
    if c.blind and c.e.get('final_scheme') != 'https':
        return blind_result()
    issues, ev = [], []
    if c.e.get('final_scheme') and c.e['final_scheme'] != 'https':
        issues.append('the first page was served over plain HTTP')
    if c.e.get('http_probe') in ('served_over_http',):
        issues.append('http:// is served without redirecting to https://')
    mixed = [(p['url'], m) for p in c.pages for m in p.get('mixed') or []]
    if mixed:
        issues.append(f'{len(mixed)} resource(s) load over plain HTTP on HTTPS pages')
        ev += [E('Mixed content', m, u) for u, m in mixed[:5]]
    http_forms = [f for f in c.forms if f.get('action_http')]
    if http_forms:
        issues.append(f'{len(http_forms)} form(s) post to http://')
        ev += [E('Form posts over HTTP', f['action'], f['url']) for f in http_forms[:3]]
    tls_err = [f for f in c.findings if f['type'] == 'fetch_error' and re.search(r'cert|ssl|tls', f['detail'], re.I)]
    if tls_err:
        issues.append('a certificate/TLS error occurred: ' + tls_err[0]['detail'][:100])
    if issues:
        return r('not_met', 'HTTPS problems: ' + '; '.join(issues) + '.', ev)
    ev.insert(0, E('Transport', f'First page over HTTPS; http:// {"redirects to https" if c.e.get("http_probe") == "redirects_to_https" else c.e.get("http_probe", "unchecked")}; '
                                 f'{len(c.pages)} page(s) with no mixed content; certificate accepted by the browser.'))
    return r('met', 'All pages scanned use HTTPS with a valid certificate, with no mixed content or HTTP form posts.', ev)


@rule('F2')
def f2(c):
    return _s42(c, 'encryption', 'encryption at rest', 'R.6(1)(a) requires encryption, masking, obfuscation or tokens.')


@rule('F3')
def f3(c):
    return _s42(c, 'access control', 'access control and MFA', 'R.6(1)(b) requires controlled access to computer resources.')


@rule('F4')
def f4(c):
    return _s42(c, 'logging', 'access logging and monitoring', 'R.6(1)(c) requires logs and monitoring to detect unauthorised access.')


@rule('F5')
def f5(c):
    return _s42(c, 'backups', 'backups', 'R.6(1)(d) requires backups and continuity measures.')


@rule('F6')
def f6(c):
    return _s42(c, 'one-year log', 'one-year log retention', 'R.6(1)(e) requires logs to be kept for one year.')


@rule('F7')
def f7(c):
    v = c.s('S28')
    if v:
        v = str(v).lower()
        if v == 'all':
            return r('declared_met', 'You declared a written contract with every processor. Unverified: attach the list and the security clauses.', ask=['S28'])
        return r('declared_gap', f'You answered "{v}" for processor contracts. Each processor needs a contract with security safeguards (R.6(1)(f)).', ask=['S28'])
    return _s42(c, 'processor contracts', 'processor contracts with security clauses', 'R.6(1)(f) requires security safeguards in processor contracts.')


@rule('F8')
def f8(c):
    if c.answered('S42') and c.has('S42', 'none') and len(c.s('S42') or []) == 1:
        return r('declared_gap', 'You declared none of the listed technical or organisational measures are in place.', ask=['S42'])
    return r('not_testable', 'Internal: appropriate technical and organisational measures that make the safeguards work in practice. Describe and attach policies.', ask=['S42'])


@rule('F9')
def f9(c):
    if c.blind:
        return blind_result()
    h = c.headers
    issues, ev = [], []
    https = c.e.get('final_scheme') == 'https'
    for name, need in (('strict-transport-security', https), ('content-security-policy', True), ('x-content-type-options', True), ('referrer-policy', True)):
        if need and name not in h:
            issues.append(f'missing {name}')
    if issues:
        ev.append(E('Missing security headers', ', '.join(i.replace('missing ', '') for i in issues), c.pages[0]['url'] if c.pages else None))
    for k in c.cookies:
        if k['first_party'] and https and not k['secure']:
            issues.append(f'cookie {k["name"]} lacks Secure')
            ev.append(E('Cookie without Secure flag', f'{k["name"]} ({k["domain"]})'))
        if k['first_party'] and SESSION_COOKIE_RE.search(k['name']) and not k['http_only']:
            issues.append(f'session cookie {k["name"]} lacks HttpOnly')
            ev.append(E('Session-like cookie without HttpOnly', k['name']))
    for hdr in ('server', 'x-powered-by'):
        if re.search(r'\d+\.\d+', h.get(hdr, '')):
            issues.append(f'{hdr} reveals a version')
            ev.append(E('Version disclosure', f'{hdr}: {h[hdr]}'))
    if issues:
        return r('not_met', f'{len(issues)} web-hygiene issue(s): ' + '; '.join(issues[:6]) + '.', ev[:10])
    return r('review', 'No problems found in the indicators tested (headers, cookie flags, version disclosure). Exposed files, admin panels, outdated CMS/plugins and exposed API '
                       'keys are not tested by this passive scan.', [E('Headers present', ', '.join(sorted(h)) or 'none')])


def _s38(c, fid):
    v = c.s('S38')
    if not v:
        return r('input', 'Do you have a documented breach response plan covering notice to individuals and to the Board within 72 hours?', ask=['S38'])
    v = str(v).lower()
    if v == 'yes':
        return r('declared_met', 'You declared a documented breach plan exists. Unverified: attach the plan.', ask=['S38'])
    return r('declared_gap', f'You answered "{v}" on having a breach response plan (R.7). This is a high-weight gap.', ask=['S38'])


@rule('F10')
def f10(c):
    return _s38(c, 'F10')


@rule('F11')
def f11(c):
    return _s38(c, 'F11')


# --------------------------------------------------------------------------------------------- G. Retention

def _s40(c):
    v = c.s('S40')
    ev = []
    q = snip(RETENTION_RX, c.notice_text)
    if q:
        ev.append(E('Notice retention wording', q, c.notice_url))
    if not v:
        return r('input', 'Do you have a retention schedule that covers website data stores?', ev, ['S40'])
    v = str(v).lower()
    if v.startswith('yes, covers'):
        return r('declared_met', 'You declared a retention schedule covering all website data stores. Unverified: attach it.', ev, ['S40'])
    return r('declared_gap', f'You answered "{v}". A retention period per purpose is required (s.8(7)).', ev, ['S40'])


@rule('G1')
def g1(c):
    return _s40(c)


@rule('G2')
def g2(c):
    v = c.s('S5')
    if not v:
        return r('input', 'Are you an e-commerce, online gaming or social media intermediary, and how many users in India?', ask=['S5'])
    v = str(v).lower()
    if '2 crore or more' in v or '50 lakh or more' in v:
        return r('not_testable', 'You are in a class covered by the Third Schedule. Confirm erasure after 3 years of inactivity with 48 hours’ notice.', ask=['S5'])
    return r('na', 'Below the Third Schedule thresholds or not an e-commerce/gaming/social media entity (S5).', ask=['S5'])


@rule('G3')
def g3(c):
    if c.has('S42', 'one-year log'):
        return r('declared_met', 'You declared one-year log retention. Unverified: show the log retention setting and how it is reconciled with erasure requests.', ask=['S42', 'S41'])
    if c.answered('S42'):
        return r('declared_gap', 'You did not select one-year log retention; R.8(3) requires at least one year for the Seventh Schedule purposes.', ask=['S42', 'S41'])
    return r('input', 'Do you keep logs and personal data for at least one year?', ask=['S42'])


@rule('G4')
def g4(c):
    return _s40(c)


# --------------------------------------------------------------------------------------------- H. Processors

@rule('H1')
def h1(c):
    if c.blind:
        return blind_result()
    if not c.hosts:
        return r('met' if c.mode == 'browser' else 'review',
                 'No third-party scripts, pixels, embeds or CDNs were found.' if c.mode == 'browser' else 'No third-party hosts found in the HTML; browser rendering would reveal more.')
    ev = [E(f'{c.cat[h]}', h) for h in sorted(c.hosts, key=lambda x: (c.cat[x] == 'other', c.cat[x], x))[:25]]
    cats = sorted({c.cat[h] for h in c.hosts if c.cat[h] != 'other'})
    return r('review', f'{len(c.hosts)} third-party host(s) found' + (f' ({", ".join(cats)})' if cats else '') +
             '. Confirm each is in your processor/recipient inventory and that none is missing.', ev, ['S25'])


@rule('H2')
def h2(c):
    v = c.s('S28')
    if not v:
        return r('input', 'Is there a written contract with each processor (hosting, CRM, email, analytics, payments, support)?', ask=['S28'])
    v = str(v).lower()
    if v == 'all':
        return r('declared_met', 'You declared a written contract with every processor. Unverified: attach the processor list and contracts.', ask=['S28'])
    return r('declared_gap', f'You answered "{v}". s.8(2) requires a valid contract with every Data Processor.', ask=['S28'])


@rule('H3')
def h3(c):
    return r('not_testable', 'A legal principle (you remain responsible for processors, whatever the contract says). Record that it is understood and reflected in vendor oversight.')


@rule('H4')
def h4(c):
    if c.blind:
        return blind_result()
    if c.mode != 'browser':
        return r('review', 'Third-party tracking at page load can only be observed with browser rendering, which was unavailable.')
    ev = [E('Advertising host at page load', h) for h in c.ad_hosts[:8]]
    if c.ad_hosts:
        return r('not_met', f'{len(c.ad_hosts)} advertising/ad-network host(s) receive visitor data on page load, before any consent choice. Their disclosure needs its own lawful basis or consent.', ev, ['S26'])
    an = [E('Analytics host', h) for h in c.trackers[:6]]
    if an:
        return r('review', 'No ad networks were seen, but analytics providers receive data on load. Confirm they are processors under contract, or covered by consent.', an, ['S26'])
    return r('met', 'No advertising or analytics third parties were contacted on page load.')


@rule('H5')
def h5(c):
    return r('not_testable', 'Internal: data used to decide something about a person, or shared with another fiduciary, must be complete, accurate and consistent.', ask=['S27'])


# --------------------------------------------------------------------------------------------- I. Cross-border

@rule('I1')
def i1(c):
    ev = [E('Server IP of the site', c.e.get('server_ip') or 'not resolved')] + [E(c.cat[h], h) for h in sorted(c.hosts)[:12]]
    if c.answered('S29'):
        return r('declared_met', 'Hosting countries declared: ' + ', '.join(c.s('S29') if isinstance(c.s('S29'), list) else [c.s('S29')]) +
                 '. The scan does not geolocate servers; unverified.', ev, ['S29'])
    return r('input', f'{len(c.hosts)} third-party endpoint(s) and the site server were found, but their countries are not determined automatically. Tell us where the site, database, backups and vendors are hosted.', ev, ['S29'])


@rule('I2')
def i2(c):
    foreign = c.answered('S29') and any('india' != str(x).lower() for x in (c.s('S29') if isinstance(c.s('S29'), list) else [c.s('S29')]))
    if foreign or c.tri('S30') == 'yes':
        return r('not_testable', 'Data goes outside India. Check it against any restriction notified under R.15 and document the assessment.', ask=['S29', 'S30'])
    if c.answered('S29') and c.tri('S30') != 'yes':
        return r('na', 'You declared all hosting is in India and no outside vendor receives the data (S29 / S30).', ask=['S29', 'S30'])
    return r('input', 'Where is data hosted, and does any vendor or group company outside India receive it?', ask=['S29', 'S30'])


@rule('I3')
def i3(c):
    g = notice_gate(c, 'the overseas-transfer statement')
    if g:
        return g
    q = snip(OVERSEAS_RX, c.notice_text)
    if q:
        return r('met', 'The notice mentions transfers outside India.', [E('Notice wording', q, c.notice_url)])
    if c.hosts:
        return r('not_met', 'Third-party services receive visitor data (often hosted abroad) but the notice does not mention overseas transfers.',
                 [E('Third party', h) for h in sorted(c.hosts)[:5]], ['S29'])
    return r('review', 'The notice does not mention overseas transfers; none were observed either. Confirm none occur.', ask=['S29'])


@rule('I4')
def i4(c):
    if not c.answered('S9'):
        return r('input', 'Which sector are you in? Banking, insurance, health and telecom have stricter localisation or transfer rules.', ask=['S9'])
    hit = [x for x in (c.s('S9') or []) if re.search(r'bank|insur|health|telecom|government', str(x), re.I)]
    if hit:
        return r('not_testable', f'You operate in {", ".join(hit)}, where sector rules (for example RBI, IRDAI, TRAI) may require local storage or limit transfers. Document compliance.', ask=['S9'])
    return r('na', 'No sector with stricter localisation or transfer rules was selected (S9).', ask=['S9'])


# --------------------------------------------------------------------------------------------- J. SDF

def _sdf(c, first=False):
    t = c.tri('S6')
    if t == 'no':
        return r('na', 'You said you are not a notified Significant Data Fiduciary (S6).', ask=['S6'])
    if t is None:
        return r('input', 'Have you been notified as a Significant Data Fiduciary, or do you expect to be?', ask=['S6'])
    if t == 'unsure':
        return r('input', 'You are unsure about SDF status. Check it against the Government notification.', ask=['S6'])
    return None


@rule('J1')
def j1(c):
    x = _sdf(c)
    if x:
        return x
    return r('not_testable', 'You are a notified SDF. Record the notification reference and the date you checked it.', ask=['S6'])


@rule('J2', 'J3', 'J4', 'J5', 'J6')
def j_rest(c):
    x = _sdf(c)
    return x or r('not_testable', 'You are a notified SDF. Provide the evidence for this obligation (appointment letter, audit report, DPIA, localisation proof).', ask=['S6'])


# --------------------------------------------------------------------------------------------- K. Governance

@rule('K1')
def k1(c):
    v = c.s('S39')
    if not v:
        return r('input', 'Have you prepared a data inventory (record of processing) and a DPIA?', ask=['S39'])
    v = str(v).lower()
    if v == 'neither':
        return r('declared_gap', 'You have neither a data inventory nor a DPIA. A data map is the basis of the security duty in s.8(4).', ask=['S39'])
    return r('declared_met', f'You declared: {v}. Unverified: attach the inventory.', ask=['S39'])


@rule('K2')
def k2(c):
    v = c.s('S35')
    if not v:
        return r('input', 'Have you appointed a DPO or designated contact, and is it published?', ask=['S35'])
    v = str(v).lower()
    if v.startswith('dpo appointed') or v.startswith('designated contact'):
        return r('declared_met', f'You declared: {v}.', ask=['S35'])
    return r('declared_gap', f'You declared: {v}. A named privacy owner and published contact are expected (s.8(9)).', ask=['S35'])


@rule('K3')
def k3(c):
    return r('not_testable', 'Internal: staff training on handling personal data and rights requests. Attach a training record.')


@rule('K4')
def k4(c):
    return r('not_testable', 'Internal: ability to answer Board directions and Government information requests. Name who handles them.')


@rule('K5')
def k5(c):
    return r('not_testable', 'Internal awareness: voluntary undertaking (s.32) and mediation (s.31).')


# --------------------------------------------------------------------------------------------- cross-cutting

KEEP_WHEN_NO_PERSONAL_DATA = {'B11', 'B13', 'F1', 'F9', 'H1', 'H4', 'D4'}
CLIENT_SECTIONS = {'A', 'B', 'E'}


def suggestions(c):
    """Pre-filled answers detected from the scan, offered to the owner as one-click suggestions."""
    out = {}
    kinds = {f['kind'] for f in c.forms if f['personal']}
    points = []
    for k, label in (('contact', 'contact form'), ('lead', 'lead or demo form'), ('newsletter', 'newsletter'), ('careers', 'careers or job application'),
                     ('checkout', 'checkout or payment'), ('login', 'account or login')):
        if k in kinds or (k == 'login' and any(f['kind'] == 'login' for f in c.forms)):
            points.append(label)
    embeds = {cat: [h for h in c.hosts if c.cat[h] == cat] for cat in ('chat', 'video', 'maps', 'social widgets', 'hosted fonts', 'payments')}
    if embeds['chat']:
        points.append('chat or chatbot')
    if points:
        out['S13'] = {'value': sorted(set(points)), 'reason': 'Forms and widgets found on the pages scanned'}
    if any(f['kind'] == 'login' for f in c.forms) or c.links('login'):
        out['S14'] = {'value': 'Yes', 'reason': 'A login form or sign-in link was found'}
    if c.links('careers') or 'careers' in kinds:
        out['S15'] = {'value': 'Yes', 'reason': 'A careers page or application form was found'}
    cats = set()
    for f in c.forms:
        sig = ' '.join(x['name'] + ' ' + x.get('hint', '') for x in f['fields'])
        for cat, rx in FORM_CAT_MAP.items():
            if re.search(rx, sig, re.I):
                cats.add(cat)
        cats |= {'email'} if any(x['type'] == 'email' for x in f['fields']) else set()
        cats |= {'phone'} if any(x['type'] == 'tel' for x in f['fields']) else set()
    if cats:
        out['S17'] = {'value': sorted(cats), 'reason': 'Field names in the forms found'}
    if embeds['payments']:
        out['S18'] = {'value': 'third-party gateway', 'reason': 'Payment provider detected: ' + ', '.join(embeds['payments'][:3])}
    langs = sorted({l for p in c.pages for l in (p.get('lang_switch') or [[]])[0]} | {'English'} if any(p.get('lang_switch') for p in c.pages) else set())
    if langs:
        out['S22'] = {'value': [l for l in langs if len(l) < 30][:10], 'reason': 'Language switcher found on the site'}
    if 'newsletter' in kinds:
        out['S24'] = {'value': 'Yes', 'reason': 'A newsletter sign-up form was found'}
    em = [k for k in ('video', 'maps', 'chat', 'social widgets', 'hosted fonts') if embeds.get(k)]
    if em:
        out['S25'] = {'value': em, 'reason': 'Embeds detected: ' + ', '.join(f'{k} ({embeds[k][0]})' for k in em)}
    if embeds['chat']:
        out['S27'] = {'value': None, 'reason': 'A chat widget was found (' + embeds['chat'][0] + '). Say whether it uses AI or automated decisions.'}
    kid_pages = [p for p in c.pages if re.search(CHILDREN_RX, p.get('text_sample', '') + ' ' + p.get('title', ''), re.I)]
    if kid_pages:
        out['S4'] = {'value': None, 'reason': 'Page wording mentions children, students or schools; check whether under-18s can use the site'}
    return out


def evaluate(scan, scope=None, declarations=None, docs=None):
    """Return the full assessment. Pure function: scan evidence + owner answers in, report out."""
    scope, declarations, docs = scope or {}, declarations or {}, docs or {}
    c = Ctx(scan, scope)
    results, flags = [], []
    no_data = c.tri('S1') == 'no'
    processor = str(scope.get('S3') or '').lower().startswith('data processor')

    for chk in DATA['checks']:
        cid = chk['id']
        try:
            res = RULES[cid](c)
        except Exception as ex:  # a rule bug must never take the report down
            res = r('review', f'This check could not be evaluated automatically ({type(ex).__name__}). Review it manually.')
        if no_data and cid not in KEEP_WHEN_NO_PERSONAL_DATA:
            res = r('na', 'You said the site processes no personal data (S1). Only tracker and HTTPS checks still apply.', res['evidence'], ['S1'])
        elif processor and cid[0] in CLIENT_SECTIONS:
            res = r('na', 'Client responsibility: you act as a Data Processor for a client (S3), so notice, consent and rights duties sit with the client.', res['evidence'], ['S3'])
        status = res['status']
        d = declarations.get(cid)
        if d and status in ('review', 'input', 'not_testable'):
            status = {'met': 'declared_met', 'gap': 'declared_gap', 'na': 'na'}.get(d['status'], status)
        results.append({
            'id': cid, 'section': chk['section'], 'requirement': chk['requirement'], 'source': chk['source'], 'basis': chk['basis'],
            'risk': chk['risk'], 'penalty': penalty_for(cid), 'status': status, 'scan_status': res['status'],
            'note': res['note'], 'evidence': res['evidence'], 'ask': res['ask'], 'fix': FIX.get(cid, ''),
            'declaration': d, 'docs': docs.get(cid, 0)})

    counts = {s: 0 for s in STATUSES}
    for x in results:
        counts[x['status']] += 1
    gaps = [x for x in results if x['status'] in ('not_met', 'declared_gap')]
    gaps.sort(key=lambda x: (RISK_ORDER[x['risk']], -x['penalty']['crore'], x['id']))
    top = max((x for x in gaps if x['penalty']['crore']), key=lambda x: x['penalty']['crore'], default=None)
    summary = {'total': len(results), 'counts': counts, 'applicable': len(results) - counts['na'],
               'observed': counts['met'] + counts['not_met'],
               'open': counts['input'] + counts['not_testable'] + counts['review'],
               'priority': [x['id'] for x in gaps[:8]],
               'high_risk_gaps': sum(1 for x in gaps if x['risk'] == 'H'),
               'top_exposure': {'crore': top['penalty']['crore'], 'label': top['penalty']['label'], 'max': top['penalty']['max'], 'check': top['id']} if top else None}

    # questions: which open checks does each one close?
    open_by_q = {}
    for x in results:
        if x['status'] == 'input':
            for q in x['ask']:
                open_by_q.setdefault(q, []).append(x['id'])
    sugg = suggestions(c)
    questions = []
    for q in DATA['questions']:
        qid = q['id']
        if q['type'] == 'info':
            continue
        questions.append({**{k: q[k] for k in ('id', 'group', 'question', 'type', 'options', 'when', 'effect')},
                          'answer': scope.get(qid), 'closes': open_by_q.get(qid, []), 'suggestion': sugg.get(qid)})

    # flags for legal review
    if c.s('S2') and str(c.s('S2')).lower().startswith('from abroad, does not'):
        flags.append('You operate from abroad and do not offer goods or services to people in India (S2): the Act may not apply. Get legal advice before relying on this report.')
    if c.tri('S7') == 'yes':
        flags.append('You said some processing is excluded (personal/domestic use or data made public by the person, S7). Record which processing, with a note.')
    if c.answered('S8') and not (c.has('S8', 'none') and len(c.s('S8')) == 1):
        flags.append('You rely on an exemption (S8). It applies only if notified; no check has been relaxed. Have counsel confirm the exemption.')
    if c.tri('S10') == 'yes':
        flags.append('The site is run by the State or provides a State benefit or service (S10): the Second Schedule standards apply instead of the usual consent checks. Get legal review.')
    if c.tri('S23') == 'yes':
        flags.append('You use a GDPR-style banner and notice for India (S23). The Act has no "legitimate interest" basis; s.7 uses are narrower. Review any reliance on it.')
    if c.tri('S43') == 'yes':
        flags.append('You have received a complaint, notice or regulator query about personal data (S43). Treat overall risk as higher and flag for legal review.')
    if c.tri('S11') == 'yes':
        flags.append('The site is part of a group with several entities or domains (S11). This scan covers one domain; scan the others and confirm which entity is the Data Fiduciary for each.')
    if c.mode != 'browser':
        flags.append('Browser rendering was not available, so cookies, trackers and JavaScript-built content could not be observed. Several checks are marked for review.')
    if c.blind:
        flags.append('This site builds its pages with JavaScript and the scan could not render it, so most website checks are inconclusive.')
    if scan.get('evidence', {}).get('timed_out'):
        flags.append('The scan stopped at its time limit; some pages were not visited.')
    if not c.notice_text and not c.blind:
        flags.append('No privacy notice text could be read, so notice-content checks (A2 to A7, E2 to E4, I3) could not run.')

    return {'results': results, 'summary': summary, 'questions': questions, 'flags': flags,
            'sections': DATA['sections'], 'mode': c.mode, 'pages_scanned': len(c.pages), 'target': scan.get('target'),
            'notice_url': c.notice_url, 'caveats': scan.get('caveats', [])}
