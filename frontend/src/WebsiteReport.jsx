import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, ArrowRight, Calendar, CheckCircle2, ChevronDown, ChevronRight, Download, ExternalLink, FileSearch,
  FileText, Globe2, Layers, Lightbulb, Loader2, Printer, RefreshCw, ScrollText, ShieldAlert, Wrench, X,
} from 'lucide-react';
import { STATUS, RISK, StatusPill, exportCsv } from './WebsiteAudit.jsx';
import './report.css';

/* Detailed website scan report: the "Reports & exports" view of the latest checklist scan.
   Everything shown comes from the assessment API (backend/assess.py); this file only lays it out. */

const GAP = ['not_met', 'declared_gap'];
const PASS = ['met', 'declared_met'];
const OPEN = ['input', 'not_testable'];
const answered = (q) => q.answer != null && (!Array.isArray(q.answer) || q.answer.length > 0);
const shortUrl = (u) => (u || '').replace(/^https?:\/\//, '').replace(/\/$/, '').slice(0, 80);
const host = (u) => { try { return new URL(/^https?:/.test(u) ? u : 'https://' + u).hostname.replace(/^www\./, ''); } catch { return u || ''; } };
const when = (iso) => new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
const list = (ids) => (ids.length <= 1 ? ids.join('') : ids.slice(0, -1).join(', ') + ' and ' + ids[ids.length - 1]);

export default function WebsiteReport({ org, req, onError, goTo }) {
  const [scans, setScans] = useState(null);
  const [sid, setSid] = useState('');
  const [a, setA] = useState(null);
  const [loading, setLoading] = useState(true);
  const [secFilter, setSecFilter] = useState(null);
  const [openGroups, setOpenGroups] = useState({ critical: true, gaps: true, review: true });
  const [openCards, setOpenCards] = useState({});
  const [printing, setPrinting] = useState(false);
  const [tiersOpen, setTiersOpen] = useState(false);

  useEffect(() => {
    let live = true;
    setScans(null); setA(null); setLoading(true); setSid('');
    req(`/orgs/${org}/scans`).then((all) => {
      if (!live) return;
      const done = all.filter((s) => s.status === 'done' && s.checklist);
      setScans(done);
      if (done.length) setSid(done[0].id); else setLoading(false);
    }).catch((e) => { if (live) { onError(e.message); setScans([]); setLoading(false); } });
    return () => { live = false; };
  }, [org, req, onError]);

  useEffect(() => {
    if (!sid) return undefined;
    let live = true;
    setLoading(true);
    req(`/orgs/${org}/scans/${sid}/assessment`)
      .then((x) => { if (live) { setA(x); setSecFilter(null); setOpenCards({}); } })
      .catch((e) => { if (live) onError(e.message); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [org, sid, req, onError]);

  useEffect(() => {
    const done = () => setPrinting(false);
    window.addEventListener('afterprint', done);
    return () => window.removeEventListener('afterprint', done);
  }, []);

  const print = useCallback(() => {
    setPrinting(true);
    setTimeout(() => window.print(), 350); // let every card expand first
  }, []);

  const m = useMemo(() => (a ? derive(a) : null), [a]);

  if (!scans || (loading && !a)) return <div className="rp-card rp-center"><Loader2 className="spin" size={22} /> Preparing report…</div>;
  if (!scans.length) {
    return (
      <div className="rp-card rp-empty">
        <FileSearch size={34} />
        <h3>No website scan to report on yet</h3>
        <p>Run a website check first. The report is built from the scan, so it always shows exactly what was observed, with the evidence and a suggested fix for each item.</p>
        <button className="btn primary" onClick={() => goTo('website')}>Run a website check <ArrowRight size={16} /></button>
      </div>
    );
  }
  if (!a || !m) return null;

  const expandAll = printing;
  const groupOpen = (k) => expandAll || openGroups[k];
  const cardOpen = (id) => expandAll || openCards[id];
  const toggleGroup = (k) => setOpenGroups((g) => ({ ...g, [k]: !g[k] }));
  const toggleCard = (id) => setOpenCards((c) => ({ ...c, [id]: !c[id] }));
  const inSec = (x) => !secFilter || x.section === secFilter;
  const open = (id) => { setSecFilter(null); setOpenCards((c) => ({ ...c, [id]: true })); setOpenGroups((g) => ({ ...g, critical: true, gaps: true, review: true, open: true })); setTimeout(() => document.getElementById('rp-' + id)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 80); };

  const groups = [
    ['critical', 'Critical gaps', 'High-risk checks the scan found not met, or you declared as a gap. Fix these first.', 'red', m.critical],
    ['gaps', 'Other gaps', 'Medium and low-risk checks that are not met.', 'rose', m.otherGaps],
    ['review', 'Needs review', 'The scan found something but cannot be sure. A person should confirm.', 'amber', m.review],
    ['open', 'Needs your input or not testable', 'These cannot be seen from the public site. Answer the questions or attach documents to settle them.', 'blue', m.open],
    ['met', 'Met', 'Checks the scan or your declaration shows as met.', 'green', m.pass],
    ['na', 'Not applicable', 'Checks that do not apply to you, with the reason.', 'mute', m.na],
  ];

  return (
    <div className="wa rp">
      {/* ---------- cover ---------- */}
      <div className="rp-cover">
        <div className="rp-cover-main">
          <div className="rp-eyebrow"><ScrollText size={14} /> DPDP WEBSITE COMPLIANCE REPORT</div>
          <h2>{host(a.scan.target)}</h2>
          <p>Detailed findings from a passive scan of your public website, tested against the {a.summary.total}-point DPDP website checklist.</p>
          <div className="rp-chips">
            <span><Calendar size={13} /> {when(a.scan.created)}</span>
            <span><Layers size={13} /> {a.pages_scanned} page{a.pages_scanned === 1 ? '' : 's'} read</span>
            <span><Globe2 size={13} /> {a.mode === 'browser' ? 'Browser-rendered' : 'Static HTML'}</span>
            <span><CheckCircle2 size={13} /> {m.answeredQ}/{a.questions.length} scoping questions answered</span>
          </div>
        </div>
        <div className="rp-cover-score">
          <Ring pct={m.metPct} />
          <div className="rp-cover-score-t">
            <b>{m.observed ? `${m.counts.met} of ${m.observed}` : 'Nothing settled'}</b>
            <span>{m.observed ? 'checks the scan could settle are met' : 'from the public site'}</span>
            <small>{a.summary.total - m.observed - m.counts.na} more need your answers or review</small>
          </div>
        </div>
      </div>

      <div className="rp-actions rp-noprint">
        <label className="rp-pick">Report for scan
          <select value={sid} onChange={(e) => setSid(e.target.value)}>
            {scans.map((s) => <option key={s.id} value={s.id}>{when(s.created)} · {shortUrl(s.target)}</option>)}
          </select>
        </label>
        <div className="rp-btns">
          <button className="btn secondary small" onClick={() => exportCsv(a)}><Download size={14} /> Export CSV</button>
          <button className="btn secondary small" onClick={() => goTo('website')}><RefreshCw size={14} /> Rescan or answer questions</button>
          <button className="btn primary small" onClick={print}><Printer size={14} /> Print or save as PDF</button>
        </div>
      </div>

      {a.flags.map((f) => <div className="rp-flag" key={f}><ShieldAlert size={16} />{f}</div>)}

      {/* ---------- overview ---------- */}
      <div className="rp-grid3">
        <div className="rp-card rp-exposure">
          <div className="rp-card-t"><AlertTriangle size={15} /> Penalty exposure</div>
          {m.exposure ? (
            <>
              <strong>{m.exposure.max}</strong>
              <p>Highest statutory penalty tier among the gaps found (check <button className="rp-link" onClick={() => open(m.exposure.check)}>{m.exposure.check}</button>: {m.exposure.label}).</p>
            </>
          ) : (
            <>
              <strong className="ok">No tier triggered</strong>
              <p>No gap with a statutory penalty tier was found in what the scan could see.</p>
            </>
          )}
          <div className="rp-tiers">
            <button className="rp-tiers-h" onClick={() => setTiersOpen(!tiersOpen)} aria-expanded={tiersOpen || printing}>
              {tiersOpen || printing ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              <span>Where each check sits in the penalty schedule</span>
              <i>{m.tiers.length}</i>
            </button>
            {(tiersOpen || printing) && (
              <>
                {m.tiers.map((t) => (
                  <div className={'rp-tier' + (t.gaps ? ' hit' : '')} key={t.label}>
                    <div><b>{t.label}</b><span>{t.max}</span></div>
                    <small>
                      {t.gaps > 0 && <em className="red">{t.gaps} gap{t.gaps === 1 ? '' : 's'}</em>}
                      {t.open > 0 && <em className="amber">{t.open} still to settle</em>}
                      {t.gaps === 0 && t.open === 0 && <em className="green">no gaps</em>}
                    </small>
                  </div>
                ))}
                <p>The Act has only a few penalty tiers, and notice, consent, rights and processor gaps all fall in the lowest one, so the headline often stays the same. Checks still to settle could move it up.</p>
              </>
            )}
          </div>
          <small>These are statutory maximums, not predictions of any penalty.</small>
        </div>

        <div className="rp-card">
          <div className="rp-card-t"><Layers size={15} /> Findings by status</div>
          <div className="rp-stats">
            <div className="red"><b>{m.gaps}</b><span>Gaps</span></div>
            <div className="amber"><b>{m.counts.review}</b><span>To review</span></div>
            <div className="blue"><b>{m.counts.input + m.counts.not_testable}</b><span>Open</span></div>
            <div className="green"><b>{m.pass.length}</b><span>Met</span></div>
          </div>
          <div className="rp-stack">{['not_met', 'declared_gap', 'review', 'input', 'not_testable', 'declared_met', 'met', 'na'].map((s) => m.counts[s] > 0 && (
            <i key={s} className={STATUS[s].tone} style={{ width: `${(100 * m.counts[s]) / a.summary.total}%` }} title={`${STATUS[s].label}: ${m.counts[s]}`} />))}</div>
          <div className="rp-legend">{['not_met', 'declared_gap', 'review', 'input', 'not_testable', 'declared_met', 'met', 'na'].filter((s) => m.counts[s]).map((s) => (
            <span key={s}><i className={STATUS[s].tone} />{STATUS[s].label} {m.counts[s]}</span>))}</div>
        </div>

        <div className="rp-card">
          <div className="rp-card-t"><ShieldAlert size={15} /> Findings by risk weight</div>
          {['H', 'M', 'L'].map((k) => {
            const r = m.byRisk[k];
            return (
              <div className="rp-risk" key={k}>
                <div className="rp-risk-h"><span className={'rk ' + k}>{RISK[k]}</span><small>{r.gaps} gap{r.gaps === 1 ? '' : 's'} · {r.review} review · {r.open} open · {r.pass} met</small></div>
                <div className="rp-stack thin">
                  {r.total > 0 && [['red', r.gaps], ['amber', r.review], ['blue', r.open], ['green', r.pass]].map(([t, v]) => v > 0 && <i key={t} className={t} style={{ width: `${(100 * v) / r.total}%` }} />)}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---------- summary ---------- */}
      <div className="rp-card rp-summary">
        <div className="rp-card-t"><FileText size={15} /> Summary</div>
        <p>{m.summaryText}</p>
        <p className="rp-honest">This is a findings report, not a compliance score or certification. A scan of public pages can only settle part of the checklist. The rest depends on how you run the business, so those items are marked <b>Needs your input</b> or <b>Not testable externally</b> instead of being guessed.</p>
      </div>

      {/* ---------- scorecard ---------- */}
      <div className="rp-head"><h3>Results by checklist section</h3>
        {secFilter && <button className="rp-clear rp-noprint" onClick={() => setSecFilter(null)}><X size={13} /> Showing section {secFilter} · show all</button>}
      </div>
      <div className="rp-sections">
        {a.sections.map((sec) => {
          const items = a.results.filter((x) => x.section === sec.letter);
          const c = (sts) => items.filter((x) => sts.includes(x.status)).length;
          const parts = [['red', c(GAP)], ['amber', c(['review'])], ['blue', c(OPEN)], ['green', c(PASS)], ['mute', c(['na'])]];
          return (
            <button key={sec.letter} className={'rp-sec' + (secFilter === sec.letter ? ' on' : '')} onClick={() => setSecFilter(secFilter === sec.letter ? null : sec.letter)}>
              <span className="rp-sec-top"><i className="rp-letter">{sec.letter}</i><b>{sec.title}</b></span>
              {sec.law && <small>{sec.law}</small>}
              <div className="rp-stack thin">{parts.map(([t, v]) => v > 0 && <i key={t} className={t} style={{ width: `${(100 * v) / items.length}%` }} />)}</div>
              <span className="rp-sec-n">
                {parts[0][1] > 0 && <em className="red">{parts[0][1]} gap{parts[0][1] === 1 ? '' : 's'}</em>}
                {parts[1][1] > 0 && <em className="amber">{parts[1][1]} review</em>}
                {parts[2][1] > 0 && <em className="blue">{parts[2][1]} open</em>}
                {parts[3][1] > 0 && <em className="green">{parts[3][1]} met</em>}
                {parts[4][1] > 0 && <em className="mute">{parts[4][1]} n/a</em>}
              </span>
            </button>
          );
        })}
      </div>

      {/* ---------- findings ---------- */}
      <div className="rp-head"><h3>Detailed findings</h3>
        <div className="rp-noprint rp-mini">
          <button onClick={() => { setOpenGroups({ critical: true, gaps: true, review: true, open: true, met: true, na: true }); }}>Open all groups</button>
          <button onClick={() => { setOpenGroups({}); setOpenCards({}); }}>Collapse all</button>
        </div>
      </div>

      {groups.map(([key, title, hint, tone, items]) => {
        const shown = items.filter(inSec);
        if (!shown.length) return null;
        const isOpen = groupOpen(key);
        return (
          <section className={'rp-group ' + tone} key={key}>
            <button className="rp-group-h" onClick={() => toggleGroup(key)} aria-expanded={isOpen}>
              {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
              <span className="rp-group-t"><b>{title}</b><small>{hint}</small></span>
              <span className={'rp-count ' + tone}>{shown.length}</span>
            </button>
            {isOpen && (
              <div className="rp-finds">
                {shown.map((x) => <Finding key={x.id} x={x} sec={a.sections.find((s) => s.letter === x.section)} open={!!cardOpen(x.id)} toggle={() => toggleCard(x.id)} goTo={goTo} />)}
              </div>
            )}
          </section>
        );
      })}

      {/* ---------- next steps ---------- */}
      <div className="rp-card rp-next">
        <div className="rp-card-t"><Lightbulb size={15} /> Recommended next steps</div>
        <ol>
          {m.critical.length > 0 && <li><b>Fix the {m.critical.length} critical gap{m.critical.length === 1 ? '' : 's'}.</b> Start with {list(m.critical.slice(0, 4).map((x) => x.id))}. Each one has a suggested fix above.</li>}
          {m.otherGaps.length > 0 && <li><b>Close the {m.otherGaps.length} other gap{m.otherGaps.length === 1 ? '' : 's'}</b> once the critical items are done.</li>}
          {m.review.length > 0 && <li><b>Have someone confirm the {m.review.length} item{m.review.length === 1 ? '' : 's'} marked Needs review</b>, then declare them met or a gap on the Website audit page.</li>}
          {m.settleable > 0 && <li><b>Answer the scoping questions.</b> {m.settleable} open check{m.settleable === 1 ? '' : 's'} can be settled by your answers, and some questions settle several at once.</li>}
          <li><b>Attach evidence</b> (policies, contracts, logs, training records) to the checks you declare as met, so a reviewer can verify them.</li>
          <li><b>Rescan after you make changes</b> to confirm the fixes show up, and keep this report as your record.</li>
        </ol>
        <div className="rp-btns rp-noprint">
          <button className="btn primary small" onClick={() => goTo('website')}>Go to Website audit <ArrowRight size={14} /></button>
        </div>
      </div>

      {/* ---------- scope + disclaimer ---------- */}
      <div className="rp-card rp-scope">
        <div className="rp-card-t"><Wrench size={15} /> About this report</div>
        <dl>
          <div><dt>Website</dt><dd>{a.scan.target}</dd></div>
          <div><dt>Scanned</dt><dd>{when(a.scan.created)}</dd></div>
          <div><dt>Pages read</dt><dd>{a.pages_scanned}</dd></div>
          <div><dt>Privacy notice read</dt><dd>{a.notice_url ? <a href={a.notice_url} target="_blank" rel="noreferrer noopener">{shortUrl(a.notice_url)}</a> : 'Not found'}</dd></div>
          <div><dt>Method</dt><dd>{a.mode === 'browser' ? 'Headless browser, as a visitor sees the site' : 'Static HTML only'}</dd></div>
          <div><dt>Report generated</dt><dd>{when(new Date().toISOString())}</dd></div>
        </dl>
        {m.caveats.length > 0 && <ul className="rp-caveats">{m.caveats.map((c) => <li key={c}>{c}</li>)}</ul>}
        <p>The scan is passive: it loads public pages, submits nothing and never logs in. It records what a visitor's browser observes and applies keyword rules to the privacy notice, so wording that is present but unclear can be marked <b>Needs review</b>. Items you declare yourself are labelled self-declared and are not verified. This report is not legal advice or a certificate of compliance. Have counsel review it before relying on it.</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ pieces */

function Ring({ pct }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone = pct == null ? 'mute' : pct >= 80 ? 'green' : pct >= 50 ? 'amber' : 'red';
  return (
    <div className="rp-ring" role="img" aria-label={pct == null ? 'Nothing settled' : `${pct} percent met`}>
      <svg viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={r} className="trk" />
        {pct != null && <circle cx="64" cy="64" r={r} className={'val ' + tone} strokeDasharray={`${(c * pct) / 100} ${c}`} transform="rotate(-90 64 64)" />}
      </svg>
      <div><b>{pct == null ? '—' : pct}{pct != null && <small>%</small>}</b><span>met</span></div>
    </div>
  );
}

function Finding({ x, sec, open, toggle, goTo }) {
  const [allEv, setAllEv] = useState(false);
  const needsFix = !PASS.includes(x.status) && x.status !== 'na' && x.fix;
  const ev = allEv ? x.evidence : x.evidence.slice(0, 4);
  return (
    <div className={'rp-find ' + STATUS[x.status].tone + (open ? ' open' : '')} id={'rp-' + x.id}>
      <button className="rp-find-h" onClick={toggle} aria-expanded={open}>
        <span className="rp-id">{x.id}</span>
        <span className="rp-req">{x.requirement}</span>
        <span className={'rk ' + x.risk}>{RISK[x.risk]}</span>
        <StatusPill status={x.status} />
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      {open && (
        <div className="rp-find-b">
          <div className="rp-cols">
            <div>
              <h5>What we found</h5>
              <p>{x.note}</p>
              {x.declaration && x.scan_status !== x.status && <p className="rp-sub">Scan result before your declaration: <b>{STATUS[x.scan_status].label}</b>.</p>}
              {x.declaration?.note && <p className="rp-sub">Your note: {x.declaration.note}</p>}
              {x.docs > 0 && <p className="rp-sub">{x.docs} supporting document{x.docs === 1 ? '' : 's'} attached.</p>}
            </div>
            {x.evidence.length > 0 && (
              <div>
                <h5>Evidence</h5>
                <div className="rp-ev">
                  {ev.map((e, i) => (
                    <div key={i}><b>{e.label}</b>{e.detail && <span>{e.detail}</span>}
                      {e.url && <a href={e.url} target="_blank" rel="noreferrer noopener"><ExternalLink size={11} />{shortUrl(e.url)}</a>}</div>
                  ))}
                </div>
                {x.evidence.length > 4 && <button className="rp-link rp-noprint" onClick={() => setAllEv(!allEv)}>{allEv ? 'Show fewer' : `Show all ${x.evidence.length} items`}</button>}
              </div>
            )}
          </div>
          {needsFix && (
            <div className="rp-fix"><h5><Wrench size={13} /> How to fix</h5><p>{x.fix}</p>
              {x.status === 'input' && <button className="rp-link rp-noprint" onClick={() => goTo('website')}>Answer on the Website audit page <ArrowRight size={12} /></button>}
            </div>
          )}
          <small className="rp-legal">{sec ? `Section ${sec.letter}: ${sec.title}` : ''}{x.source ? ` · ${x.source}` : ''}{x.basis ? ` · Basis: ${x.basis}` : ''}{x.penalty?.crore ? ` · Max penalty tier: ${x.penalty.max}` : ' · No direct statutory penalty tier (good practice)'}</small>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ numbers */

function derive(a) {
  const counts = a.summary.counts;
  const rank = { H: 0, M: 1, L: 2 };
  const by = (sts) => a.results.filter((x) => sts.includes(x.status));
  const gapList = by(GAP).sort((x, y) => rank[x.risk] - rank[y.risk] || y.penalty.crore - x.penalty.crore || x.id.localeCompare(y.id));
  const critical = gapList.filter((x) => x.risk === 'H');
  const otherGaps = gapList.filter((x) => x.risk !== 'H');
  const review = by(['review']).sort((x, y) => rank[x.risk] - rank[y.risk]);
  const open = by(OPEN).sort((x, y) => rank[x.risk] - rank[y.risk]);
  const pass = by(PASS);
  const na = by(['na']);
  const observed = counts.met + counts.not_met;
  const metPct = observed ? Math.round((100 * counts.met) / observed) : null;
  const byRisk = Object.fromEntries(['H', 'M', 'L'].map((k) => {
    const it = a.results.filter((x) => x.risk === k && x.status !== 'na');
    const n = (sts) => it.filter((x) => sts.includes(x.status)).length;
    return [k, { total: it.length, gaps: n(GAP), review: n(['review']), open: n(OPEN), pass: n(PASS) }];
  }));
  const settleable = a.results.filter((x) => x.status === 'input' && x.ask.length).length;
  const tierMap = new Map();
  a.results.filter((x) => x.penalty.crore > 0 && x.status !== 'na').forEach((x) => {
    const t = tierMap.get(x.penalty.label) || { label: x.penalty.label, max: x.penalty.max, crore: x.penalty.crore, gaps: 0, open: 0 };
    if (GAP.includes(x.status)) t.gaps += 1;
    else if (!PASS.includes(x.status)) t.open += 1; // review, input, not testable
    tierMap.set(x.penalty.label, t);
  });
  const tiers = [...tierMap.values()].sort((p, q) => q.crore - p.crore);
  const exposure = a.summary.top_exposure;
  const gaps = gapList.length;

  const bits = [];
  bits.push(`We read ${a.pages_scanned} page${a.pages_scanned === 1 ? '' : 's'} of ${host(a.scan.target)} on ${when(a.scan.created)} and tested it against ${a.summary.total} DPDP website checks.`);
  if (observed) bits.push(`${observed} could be settled from the public site: ${counts.met} met and ${counts.not_met} not met.`);
  else bits.push('None could be fully settled from the public site alone.');
  if (counts.review) bits.push(`${counts.review} need a person to confirm.`);
  if (counts.input + counts.not_testable) bits.push(`${counts.input + counts.not_testable} cannot be seen from outside and depend on your answers or documents.`);
  if (critical.length) bits.push(`The most urgent gaps are ${list(critical.slice(0, 4).map((x) => x.id))}${critical.length > 4 ? ` and ${critical.length - 4} more` : ''}.`);
  else if (gaps) bits.push(`${gaps} gap${gaps === 1 ? ' was' : 's were'} found; none is rated high risk.`);
  else bits.push('No gaps were found in what the scan could see.');
  return {
    counts, gaps, critical, otherGaps, review, open, pass, na, observed, metPct, byRisk, settleable, exposure, tiers,
    // scanner caveats include notes meant for whoever runs the server; show only what matters to the reader
    caveats: (a.caveats || []).filter((c) => !/DNS|egress|robots/i.test(c)),
    answeredQ: a.questions.filter(answered).length, summaryText: bits.join(' '),
  };
}
