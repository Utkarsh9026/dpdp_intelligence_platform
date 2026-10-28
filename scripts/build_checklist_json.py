"""Regenerate backend/checklist.json from 'DPDP Website Compliance Checklist.xlsx'.

Usage (from repo root):  python scripts/build_checklist_json.py

Uses only the standard library (an .xlsx is a zip of XML), so no openpyxl needed.
The xlsx stays the source of truth; the app reads the generated JSON at runtime.
"""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / 'backend' / 'DPDP Website Compliance Checklist.xlsx'
OUT = ROOT / 'backend' / 'checklist.json'
M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

# The sheet's free-text "Answer type" column is not always machine-parseable. These
# questions get explicit options so the UI can render a proper control.
OVERRIDES = {
    'S5': {'type': 'single', 'options': [
        'Not e-commerce, online gaming or social media',
        'E-commerce or social media: under 2 crore users in India',
        'E-commerce or social media: 2 crore or more users in India',
        'Online gaming: under 50 lakh users in India',
        'Online gaming: 50 lakh or more users in India']},
    'S12': {'type': 'multi', 'options': ['Under 10,000 individuals', '10,000 to 1 lakh', 'Over 1 lakh', 'Financial data',
                                           'Health data', 'Location data', 'Biometric data', 'Government ID data']},
    'S36': {'type': 'single', 'options': ['Yes, response time is 90 days or less', 'Yes, but response time is over 90 days',
                                            'Yes, but no response time is published', 'No grievance mechanism']},
    'S35': {'type': 'single', 'options': ['DPO appointed and published', 'Designated contact person, published',
                                            'DPO or contact exists but is not published', 'None']},
    'S19': {'type': 'multi', 'options': ['consent', 'voluntary provision (s.7(a))', 'employment (s.7(i))',
                                         'legal obligation or order', 'other']},
    'S22': {'type': 'multi', 'options': ['English', 'Hindi', 'Bengali', 'Marathi', 'Telugu', 'Tamil', 'Gujarati', 'Urdu',
                                         'Kannada', 'Odia', 'Malayalam', 'Punjabi', 'Assamese', 'Other Eighth Schedule language']},
    'S25': {'type': 'multi', 'options': ['video', 'maps', 'chat', 'social widgets', 'hosted fonts', 'none']},
    'S29': {'type': 'multi', 'options': ['India', 'United States', 'European Union', 'United Kingdom', 'Singapore', 'Other country']},
    'S38': {'type': 'single', 'options': ['Yes', 'No', 'Partly']},
    'S41': {'type': 'single', 'options': ['Yes', 'No']},
    'S44': {'type': 'yesno'},
    'S45': {'type': 'info'},
}


def sheet_rows(z, name, strings):
    for row in ET.fromstring(z.read(f'xl/worksheets/{name}.xml')).iter(M + 'row'):
        cells = {}
        for c in row.findall(M + 'c'):
            v = c.find(M + 'v')
            if v is None:
                continue
            col = re.match(r'[A-Z]+', c.get('r')).group(0)
            cells[col] = strings[int(v.text)] if c.get('t') == 's' else v.text
        if cells:
            yield int(row.get('r')), cells


def parse_answer_type(raw):
    """Turn 'Multi-select: a / b / c' style text into {'type', 'options'}."""
    raw = (raw or '').strip()
    low = raw.lower()
    if low.startswith('upload'):
        return {'type': 'info', 'options': []}
    m = re.match(r'(multi-select|single choice)[^:]*:\s*(.+)', raw, re.I | re.S)
    if m:
        opts = [o.strip(' .') for o in re.split(r'\s+/\s+', m.group(2)) if o.strip()]
        if 2 <= len(opts) <= 25 and not any(len(o) > 90 for o in opts):
            return {'type': 'multi' if m.group(1).lower().startswith('multi') else 'single', 'options': opts}
    if re.fullmatch(r'yes\s*/\s*no(\s*/\s*(not sure|don.t know))?', low):
        return {'type': 'single', 'options': [o.strip().capitalize() if o.strip().lower() != "don't know" else "Don't know"
                                                for o in raw.split('/')]}
    return {'type': 'text', 'options': []}


def main():
    z = zipfile.ZipFile(XLSX)
    strings = [''.join(t.text or '' for t in si.iter(M + 't')) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(M + 'si')]

    checks, sections = [], {}
    for r, c in sheet_rows(z, 'sheet1', strings):
        cid = c.get('A', '')
        if not re.fullmatch(r'[A-K]\d+', cid):
            continue
        sec = c['B']
        m = re.match(r'([A-K])\.\s*(.+?)\s*(?:\((.*)\))?$', sec)
        letter, title, law = (m.group(1), m.group(2), m.group(3) or '') if m else (cid[0], sec, '')
        sections[letter] = {'letter': letter, 'title': title, 'law': law}
        checks.append({'id': cid, 'section': letter, 'requirement': c['C'], 'source': c.get('D', ''),
                       'basis': c.get('E', ''), 'risk': c.get('F', 'M')})

    penalties = [{'breach': c['A'], 'max': c.get('B', '')} for r, c in sheet_rows(z, 'sheet2', strings) if r > 2]

    questions = []
    for r, c in sheet_rows(z, 'sheet3', strings):
        qid = c.get('A', '')
        if not re.fullmatch(r'S\d+', qid):
            continue
        q = {'id': qid, 'group': c.get('B', ''), 'question': c.get('C', ''), 'answer_type': c.get('D', ''),
             'when': c.get('E', ''), 'effect': c.get('F', '')}
        q.update(OVERRIDES.get(qid) or parse_answer_type(c.get('D', '')))
        if q['type'] == 'yesno':
            q.update({'type': 'single', 'options': ['Yes', 'No']})
        questions.append(q)

    data = {'sections': [sections[k] for k in sorted(sections)], 'checks': checks, 'penalties': penalties, 'questions': questions}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(checks)} checks, {len(sections)} sections, {len(questions)} questions -> {OUT}')
    kinds = {}
    for q in questions:
        kinds.setdefault(q['type'], []).append(q['id'])
    for k, v in kinds.items():
        print(' ', k, v)


if __name__ == '__main__':
    sys.exit(main())
