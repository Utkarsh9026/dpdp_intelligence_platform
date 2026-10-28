import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, ArrowRight, Check, CheckCircle2, ChevronDown, ChevronRight, Download, ExternalLink, EyeOff, Globe2,
  HelpCircle, Loader2, MinusCircle, RefreshCw, Search, ShieldAlert, Sparkles, UploadCloud, X, XCircle,
} from 'lucide-react';
import './website.css';

/* Website compliance check: paste a URL -> live scan -> checklist findings grouped by section -> questions + documents close the gaps.
   All statuses come from the API (backend/assess.py). This file only presents them; it never decides compliance. */

export const STATUS = {
  not_met: { label: 'Not met', tone: 'red', Icon: XCircle },
  declared_gap: { label: 'Self-declared: gap', tone: 'rose', Icon: XCircle },
  review: { label: 'Needs review', tone: 'amber', Icon: AlertTriangle },
  input: { label: 'Needs your input', tone: 'blue', Icon: HelpCircle },
  not_testable: { label: 'Not testable externally', tone: 'slate', Icon: EyeOff },
  declared_met: { label: 'Self-declared: met', tone: 'teal', Icon: CheckCircle2 },
  met: { label: 'Met', tone: 'green', Icon: CheckCircle2 },
  na: { label: 'Not applicable', tone: 'mute', Icon: MinusCircle },
};
const ORDER = ['not_met', 'declared_gap', 'review', 'input', 'not_testable', 'declared_met', 'met', 'na'];
const FILTERS = [
  ['all', 'All', null],
  ['gaps', 'Gaps', ['not_met', 'declared_gap']],
  ['review', 'Needs review', ['review']],
  ['input', 'Needs your input', ['input']],
  ['not_testable', 'Not testable', ['not_testable']],
  ['done', 'Met', ['met', 'declared_met']],
  ['na', 'N/A', ['na']],
];
export const RISK = { H: 'High', M: 'Medium', L: 'Low' };
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const answered = (q) => q.answer != null && (!Array.isArray(q.answer) || q.answer.length > 0);
const fmtVal = (v) => (Array.isArray(v) ? v.map(cap).join(', ') : cap(String(v)));
const shortUrl = (u) => (u || '').replace(/^https?:\/\//, '').slice(0, 70);

export function StatusPill({ status, small }) {
  const s = STATUS[status] || STATUS.review;
  return <span className={`wa-pill ${s.tone}${small ? ' small' : ''}`}><s.Icon size={small ? 11 : 13} />{s.label}</span>;
}

/* ------------------------------------------------------------------ main */

export default function WebsiteAudit({ org, active, req, onError, flash }) {
  const canEdit = ['owner', 'admin', 'assessor'].includes(active?.role);
  const [url, setUrl] = useState(active?.domain || '');
  const [phase, setPhase] = useState('loading'); // loading | idle | running | failed | done
  const [scan, setScan] = useState(null);
  const [data, setData] = useState(null);
  const [legacy, setLegacy] = useState(false);
  const [starting, setStarting] = useState(false);
  const run = useRef(0);
  const timer = useRef(null);

  useEffect(() => { setUrl(active?.domain || ''); }, [active?.domain]);

  const stop = () => { run.current += 1; clearTimeout(timer.current); };
  useEffect(() => stop, []);

  const loadAssessment = useCallback(async (id, mine) => {
    const a = await req(`/orgs/${org}/scans/${id}/assessment`);
    if (mine !== undefined && mine !== run.current) return;
    setData(a);
    setPhase('done');
  }, [org, req]);

  const follow = useCallback((id) => {
    const mine = ++run.current;
    clearTimeout(timer.current);
    setPhase('running');
    const poll = async () => {
      try {
        const v = await req(`/orgs/${org}/scans/${id}`);
        if (mine !== run.current) return;
        setScan(v);
        if (v.status === 'running') timer.current = setTimeout(poll, 1400);
        else if (v.status === 'done') await loadAssessment(id, mine);
        else setPhase('failed');
      } catch (e) {
        if (mine === run.current) { onError(e.message); setPhase('failed'); }
      }
    };
    poll();
  }, [org, req, loadAssessment, onError]);

  // On organisation change: resume a running scan or show the latest finished one.
  useEffect(() => {
    if (!org) return undefined;
    stop();
    setData(null); setScan(null); setPhase('loading'); setLegacy(false);
    const mine = run.current;
    (async () => {
      try {
        const list = await req(`/orgs/${org}/scans`);
        if (mine !== run.current) return;
        const latest = list.find((s) => s.status === 'running' || (s.status === 'done' && s.checklist));
        if (!latest) { setLegacy(list.length > 0); setPhase('idle'); return; }
        setScan(latest);
        if (latest.status === 'running') follow(latest.id); else await loadAssessment(latest.id, mine);
      } catch (e) { if (mine === run.current) { onError(e.message); setPhase('idle'); } }
    })();
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [org]);

  const start = async () => {
    setStarting(true);
    try {
      const r = await req(`/orgs/${org}/scans`, { method: 'POST', body: { url: url.trim() } });
      setData(null); setScan({ id: r.id, status: 'running', progress: { label: 'Queued', percent: 1, pages: [] }, target: url });
      follow(r.id);
    } catch (e) { onError(e.message); } finally { setStarting(false); }
  };

  const refresh = useCallback(async () => { if (scan?.id) await loadAssessment(scan.id); }, [scan, loadAssessment]);
  const act = async (fn, okMsg) => {
    try { await fn(); await refresh(); if (okMsg) flash(okMsg); } catch (e) { onError(e.message); }
  };
  const answer = (qid, value) => act(() => req(`/orgs/${org}/scope/${qid}`, { method: 'PUT', body: { value } }));
  const declare = (cid, status, note) => act(() => req(`/orgs/${org}/web-checks/${cid}`, { method: 'PUT', body: { status, note } }), status === 'clear' ? 'Declaration cleared' : 'Declaration saved');
  const upload = (cid, file) => act(() => { const fd = new FormData(); fd.append('file', file); return req(`/orgs/${org}/web-checks/${cid}/evidence`, { method: 'POST', file: fd }); }, 'Document attached');

  return (
    <div className="wa">
      <div className="page-title">
        <div className="eyebrow">DPDP WEBSITE CHECK</div>
        <div className="page-heading"><div>
          <h1>Website compliance check</h1>
          <p>Paste your website address. We read what a visitor can see, test it against the 76-point DPDP website checklist, and show what is met, what is not, and what we need from you.</p>
        </div></div>
      </div>

      <UrlBar url={url} setUrl={setUrl} onRun={start} busy={starting || phase === 'running'} canEdit={canEdit} compact={phase === 'done'}
        domain={active?.domain} />

      {phase === 'loading' && <div className="wa-card wa-center"><Loader2 className="spin" size={22} /> Loading…</div>}
      {phase === 'idle' && <Intro legacy={legacy} />}
      {phase === 'running' && <Progress scan={scan} />}
      {phase === 'failed' && (
        <div className="wa-card wa-fail"><XCircle size={20} /><div><b>The scan did not complete</b><p>{scan?.error || 'Something went wrong.'}</p>
          <small>Check the address is a public website that loads in a browser, then try again.</small></div></div>
      )}
      {phase === 'done' && data && (
        <Results a={data} canEdit={canEdit} answer={answer} declare={declare} upload={upload}
          onRescan={start} rescanning={starting} />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ pieces */

function UrlBar({ url, setUrl, onRun, busy, canEdit, compact, domain }) {
  return (
    <div className={'wa-card wa-urlbar' + (compact ? ' compact' : '')}>
      <div className="wa-input">
        <Globe2 size={18} />
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://yourcompany.com" aria-label="Website address"
          onKeyDown={(e) => { if (e.key === 'Enter' && url.trim() && !busy && canEdit) onRun(); }} />
        <button className="btn primary" disabled={busy || !url.trim() || !canEdit} onClick={onRun}>
          {busy ? <><Loader2 size={15} className="spin" /> Scanning…</> : <>{compact ? 'Scan again' : 'Check website'} <ArrowRight size={16} /></>}
        </button>
      </div>
      {!compact && <small>{canEdit ? `Limited to your registered site${domain ? ` (${shortUrl(domain)})` : ''}. Public pages only: nothing is submitted, no login is attempted.` : 'Your role is read-only: ask an owner, admin or assessor to run a scan.'}</small>}
    </div>
  );
}

function Intro({ legacy }) {
  return (
    <div className="wa-card wa-intro">
      {legacy && <div className="wa-note"><AlertTriangle size={15} /> Earlier scans in this workspace predate the checklist. Run a new scan to see checklist results.</div>}
      <h3>What happens when you press “Check website”</h3>
      <div className="wa-steps3">
        <div><span>1</span><b>We read your site</b><p>Pages, forms, banners, cookies and third-party scripts, exactly as a visitor’s browser sees them, plus your privacy notice text.</p></div>
        <div><span>2</span><b>We test 76 checks</b><p>Each is marked Met, Not met or Needs review, with the page and wording we based it on. About half cannot be seen from outside.</p></div>
        <div><span>3</span><b>You close the gaps</b><p>Answer a few questions and attach documents. Items you declare are labelled self-declared, never “verified”.</p></div>
      </div>
    </div>
  );
}

function Progress({ scan }) {
  const p = scan?.progress || { label: 'Starting', percent: 2, pages: [] };
  const steps = [['Connect to the site', 5], ['Read robots.txt and sitemap', 10], ['Start the browser', 14], ['Read pages', 20], ['Read the privacy notice and evaluate the checklist', 90]];
  const idx = steps.reduce((n, [, t], i) => (p.percent >= t ? i : n), 0);
  return (
    <div className="wa-card wa-progress" aria-live="polite">
      <div className="wa-prog-head"><Loader2 size={20} className="spin" /><div><b>{p.label}</b><small>This usually takes 20 to 60 seconds. You can leave this page; the scan keeps running.</small></div><span>{Math.min(99, p.percent)}%</span></div>
      <div className="wa-bar"><div style={{ width: `${Math.min(100, p.percent)}%` }} /></div>
      <ol className="wa-stepper">{steps.map(([s], i) => <li key={s} className={i < idx ? 'done' : i === idx ? 'now' : ''}>{i < idx ? <Check size={13} /> : i === idx ? <Loader2 size={13} className="spin" /> : <span className="dot" />}{s}</li>)}</ol>
      {!!p.pages?.length && <div className="wa-pages"><small>Pages read so far</small>{p.pages.slice(-6).map((u) => <code key={u}>{shortUrl(u)}</code>)}</div>}
    </div>
  );
}

function Results({ a, canEdit, answer, declare, upload, onRescan, rescanning }) {
  const [filter, setFilter] = useState('all');
  const [risk, setRisk] = useState('all');
  const [q, setQ] = useState('');
  const [openSec, setOpenSec] = useState(null);
  const [openRows, setOpenRows] = useState({});
  const [allQ, setAllQ] = useState(false);
  const counts = a.summary.counts;

  useEffect(() => { // first view: open the sections that contain gaps
    setOpenSec(new Set(a.results.filter((x) => x.status === 'not_met' || x.status === 'declared_gap').map((x) => x.section)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a.scan.id]);

  const preset = FILTERS.find((f) => f[0] === filter)[2];
  const visible = useMemo(() => a.results.filter((x) =>
    (!preset || preset.includes(x.status)) && (risk === 'all' || x.risk === risk) &&
    (!q || `${x.id} ${x.requirement} ${x.note}`.toLowerCase().includes(q.toLowerCase()))), [a.results, preset, risk, q]);
  const filtering = filter !== 'all' || risk !== 'all' || !!q;

  const focusCheck = (id) => {
    setFilter('all'); setRisk('all'); setQ('');
    setOpenSec((s) => new Set([...(s || []), id[0]]));
    setOpenRows((r) => ({ ...r, [id]: true }));
    setTimeout(() => document.getElementById('chk-' + id)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 80);
  };
  const openQuestions = a.questions.filter((x) => x.closes.length && !answered(x)).sort((x, y) => y.closes.length - x.closes.length);

  return (
    <>
      <div className="wa-meta">
        <div><b>{shortUrl(a.scan.target)}</b><span>Scanned {new Date(a.scan.created).toLocaleString()} · {a.pages_scanned} page{a.pages_scanned === 1 ? '' : 's'} · {a.mode === 'browser' ? 'browser-rendered' : 'static HTML'}</span></div>
        <div className="wa-meta-actions">
          <button className="btn secondary small" onClick={() => exportCsv(a)}><Download size={14} /> Export CSV</button>
          <button className="btn secondary small" disabled={rescanning || !canEdit} onClick={onRescan}><RefreshCw size={14} /> Rescan</button>
        </div>
      </div>

      {a.flags.map((f) => <div className="wa-flag" key={f}><ShieldAlert size={16} />{f}</div>)}

      <Summary a={a} counts={counts} filter={filter} setFilter={setFilter} focusCheck={focusCheck} />

      <Questions a={a} list={openQuestions} answer={answer} canEdit={canEdit} onAll={() => setAllQ(true)} />

      <div className="wa-toolbar">
        <div className="wa-tabs" role="tablist">{FILTERS.map(([key, label, sts]) => {
          const n = sts ? sts.reduce((s, k) => s + counts[k], 0) : a.summary.total;
          return <button key={key} role="tab" aria-selected={filter === key} className={filter === key ? 'on' : ''} onClick={() => setFilter(key)}>{label}<i>{n}</i></button>;
        })}</div>
        <div className="wa-tools">
          <select value={risk} onChange={(e) => setRisk(e.target.value)} aria-label="Risk filter"><option value="all">Any risk</option><option value="H">High risk</option><option value="M">Medium risk</option><option value="L">Low risk</option></select>
          <div className="wa-search"><Search size={15} /><input placeholder="Search checks" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        </div>
      </div>

      {a.sections.map((sec) => {
        const items = visible.filter((x) => x.section === sec.letter);
        const all = a.results.filter((x) => x.section === sec.letter);
        if (!items.length) return null;
        const isOpen = filtering || openSec?.has(sec.letter);
        return (
          <section className="wa-sec" key={sec.letter}>
            <button className="wa-sec-head" onClick={() => setOpenSec((s) => { const n = new Set(s); n.has(sec.letter) ? n.delete(sec.letter) : n.add(sec.letter); return n; })} aria-expanded={isOpen}>
              {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
              <span className="wa-letter">{sec.letter}</span>
              <span className="wa-sec-title"><b>{sec.title}</b>{sec.law && <small>{sec.law}</small>}</span>
              <SecCounts items={all} />
            </button>
            {isOpen && <div className="wa-rows">{items.map((x) => (
              <CheckRow key={x.id} x={x} a={a} open={!!openRows[x.id]} toggle={() => setOpenRows((r) => ({ ...r, [x.id]: !r[x.id] }))}
                canEdit={canEdit} declare={declare} upload={upload} answer={answer} />
            ))}</div>}
          </section>
        );
      })}
      {!visible.length && <div className="wa-card wa-center">No checks match these filters.</div>}

      <p className="wa-foot">This report records what an automated, passive scan of public pages observed, plus your own answers. It is not a legal opinion or certification of compliance. “Self-declared” items are unverified. Have counsel review before relying on it.</p>
      {allQ && <AllQuestions a={a} answer={answer} canEdit={canEdit} onClose={() => setAllQ(false)} />}
    </>
  );
}

function SecCounts({ items }) {
  const n = (sts) => items.filter((x) => sts.includes(x.status)).length;
  const parts = [['red', n(['not_met', 'declared_gap']), 'gaps'], ['amber', n(['review']), 'to review'], ['blue', n(['input', 'not_testable']), 'open'], ['green', n(['met', 'declared_met']), 'met']];
  return <span className="wa-seccounts">{parts.filter((p) => p[1]).map(([t, v, l]) => <span key={t} className={'c ' + t} title={`${v} ${l}`}>{v}</span>)}</span>;
}

function Summary({ a, counts, filter, setFilter, focusCheck }) {
  const total = a.summary.total;
  const gaps = counts.not_met + counts.declared_gap;
  const ok = counts.met + counts.declared_met;
  const top = a.summary.top_exposure;
  const byId = Object.fromEntries(a.results.map((x) => [x.id, x]));
  const jump = (sts) => setFilter(FILTERS.find((f) => f[2] && f[2].join() === sts.join())?.[0] || 'all');
  return (
    <div className="wa-card wa-summary">
      <div className="wa-stats">
        <button onClick={() => jump(['not_met', 'declared_gap'])} className="wa-stat red"><b>{gaps}</b><span>Gaps found</span></button>
        <button onClick={() => jump(['review'])} className="wa-stat amber"><b>{counts.review}</b><span>Need review</span></button>
        <button onClick={() => jump(['input'])} className="wa-stat blue"><b>{counts.input}</b><span>Need your input</span></button>
        <button onClick={() => jump(['met', 'declared_met'])} className="wa-stat green"><b>{ok}</b><span>Met</span></button>
      </div>
      <div className="wa-stack" role="img" aria-label="Status breakdown">
        {ORDER.map((s) => counts[s] > 0 && <div key={s} className={'seg ' + STATUS[s].tone} style={{ width: `${(100 * counts[s]) / total}%` }} title={`${STATUS[s].label}: ${counts[s]}`} />)}
      </div>
      <div className="wa-legend">{ORDER.filter((s) => counts[s]).map((s) => <span key={s}><i className={STATUS[s].tone} />{STATUS[s].label} {counts[s]}</span>)}</div>
      <p className="wa-honest">
        <b>{a.summary.observed}</b> of {total} checks could be settled from the website. <b>{counts.input + counts.not_testable}</b> need your answers or documents, because a URL scan cannot see them. This is a findings list, not a compliance score.
      </p>
      {!!a.summary.priority.length && (
        <div className="wa-priority">
          <h4>Fix first{top && <small>Highest penalty tier among the gaps: <b>{top.max}</b> ({top.label}, check {top.check}). This is the statutory maximum, not a prediction.</small>}</h4>
          {a.summary.priority.map((id) => (
            <button key={id} onClick={() => focusCheck(id)}><span className="id">{id}</span><span className="t">{byId[id].requirement}</span><span className={'rk ' + byId[id].risk}>{RISK[byId[id].risk]}</span><ChevronRight size={15} /></button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ questions */

function QuestionControl({ q, answer, disabled }) {
  const [draft, setDraft] = useState(Array.isArray(q.answer) ? q.answer : []);
  useEffect(() => { setDraft(Array.isArray(q.answer) ? q.answer : []); }, [JSON.stringify(q.answer)]); // eslint-disable-line
  const valid = (v) => (Array.isArray(v) ? v.filter((x) => q.options.some((o) => o.toLowerCase() === String(x).toLowerCase())) : v);
  const sugg = !answered(q) && q.suggestion && q.suggestion.value != null ? valid(q.suggestion.value) : null;
  const useful = Array.isArray(sugg) ? sugg.length > 0 : !!sugg;
  return (
    <div className="wa-qc">
      {q.suggestion && !answered(q) && (
        <div className="wa-sugg"><Sparkles size={13} /><span>{q.suggestion.reason}{useful && <> · Detected: <b>{fmtVal(sugg)}</b></>}</span>
          {useful && !disabled && <button onClick={() => answer(q.id, sugg)}>Use this</button>}</div>
      )}
      {q.type === 'single' && (
        <div className="wa-opts">{q.options.map((o) => {
          const on = answered(q) && String(q.answer).toLowerCase() === o.toLowerCase();
          return <button key={o} disabled={disabled} className={on ? 'on' : ''} onClick={() => answer(q.id, on ? null : o)}>{cap(o)}</button>;
        })}</div>
      )}
      {q.type === 'multi' && (
        <>
          <div className="wa-opts">{q.options.map((o) => {
            const on = draft.some((d) => d.toLowerCase() === o.toLowerCase());
            return <button key={o} disabled={disabled} className={on ? 'on' : ''} onClick={() => setDraft(on ? draft.filter((d) => d.toLowerCase() !== o.toLowerCase()) : [...draft, o])}>{on && <Check size={12} />}{cap(o)}</button>;
          })}</div>
          {!disabled && <div className="wa-qsave"><button className="btn primary small" disabled={JSON.stringify(draft) === JSON.stringify(q.answer || [])} onClick={() => answer(q.id, draft.length ? draft : null)}>Save answer</button>
            {answered(q) && <button className="btn secondary small" onClick={() => answer(q.id, null)}>Clear</button>}</div>}
        </>
      )}
    </div>
  );
}

function Questions({ a, list, answer, canEdit, onAll }) {
  const total = a.questions.length;
  const done = a.questions.filter(answered).length;
  const top = list.slice(0, 4);
  return (
    <div className="wa-card wa-questions">
      <div className="wa-q-head">
        <div><h3><Sparkles size={17} /> Improve accuracy</h3>
          <p>{top.length ? 'These answers settle checks the scan cannot see. Answers are saved to your workspace and reused on every rescan.' : 'You have answered every question that affects an open check.'}</p></div>
        <button className="btn secondary small" onClick={onAll}>All {total} questions ({done} answered)</button>
      </div>
      {top.map((q) => (
        <div className="wa-q" key={q.id}>
          <div className="wa-q-text"><span className="id">{q.id}</span><b>{q.question}</b><small>Settles {q.closes.length} check{q.closes.length === 1 ? '' : 's'}: {q.closes.slice(0, 8).join(', ')}{q.closes.length > 8 ? '…' : ''}</small></div>
          <QuestionControl q={q} answer={answer} disabled={!canEdit} />
        </div>
      ))}
    </div>
  );
}

function AllQuestions({ a, answer, canEdit, onClose }) {
  const groups = [...new Set(a.questions.map((q) => q.group))];
  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <div className="drawer wa-drawer" onMouseDown={(e) => e.stopPropagation()}>
        <div className="drawer-head"><div><span className="eyebrow">SCOPING QUESTIONS</span><h2>Tell us about your organisation</h2></div><button className="btn secondary" onClick={onClose}><X size={15} /> Close</button></div>
        <div className="drawer-scroll">
          {groups.map((g) => (
            <div key={g} className="wa-qgroup"><h4>{g}</h4>
              {a.questions.filter((q) => q.group === g).map((q) => (
                <div className="wa-q" key={q.id}>
                  <div className="wa-q-text"><span className="id">{q.id}</span><b>{q.question}</b>
                    {q.closes.length > 0 && <small>Settles {q.closes.length} open check{q.closes.length === 1 ? '' : 's'}</small>}
                    <small className="eff">{q.effect}</small></div>
                  <QuestionControl q={q} answer={answer} disabled={!canEdit} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ one check */

function CheckRow({ x, a, open, toggle, canEdit, declare, upload, answer }) {
  const [note, setNote] = useState(x.declaration?.note || '');
  const [pick, setPick] = useState(null);
  const [allEv, setAllEv] = useState(false);
  useEffect(() => { setNote(x.declaration?.note || ''); setPick(null); }, [x.declaration?.note, x.declaration?.status]);
  const editable = ['review', 'input', 'not_testable'].includes(x.scan_status);
  const files = a.documents[x.id] || [];
  const related = a.questions.filter((qq) => x.ask.includes(qq.id));
  return (
    <div className={'wa-row ' + STATUS[x.status].tone + (open ? ' open' : '')} id={'chk-' + x.id}>
      <button className="wa-row-head" onClick={toggle} aria-expanded={open}>
        <span className="wa-id">{x.id}</span>
        <span className="wa-req">{x.requirement}</span>
        <span className={'wa-risk ' + x.risk} title="Risk weight from the checklist">{RISK[x.risk]}</span>
        <StatusPill status={x.status} />
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      {open && (
        <div className="wa-detail">
          <div className="wa-finding"><h5>What we found</h5><p>{x.note}</p>
            {x.declaration && x.scan_status !== x.status && <p className="wa-sub">Scan result before your declaration: <b>{STATUS[x.scan_status].label}</b>.</p>}
          </div>
          {x.evidence.length > 0 && (
            <div className="wa-evidence"><h5>Evidence</h5>
              {(allEv ? x.evidence : x.evidence.slice(0, 6)).map((e, i) => (
                <div className="wa-ev" key={i}><b>{e.label}</b>{e.detail && <span>{e.detail}</span>}
                  {e.url && <a href={e.url} target="_blank" rel="noreferrer noopener"><ExternalLink size={12} />{shortUrl(e.url)}</a>}</div>
              ))}
              {x.evidence.length > 6 && (
                <button className="wa-link" onClick={() => setAllEv(!allEv)}>
                  {allEv ? 'Show fewer' : `Show all ${x.evidence.length} items`}
                </button>
              )}
            </div>
          )}
          {x.fix && !['met', 'declared_met', 'na'].includes(x.status) && <div className="wa-fix"><h5>How to fix</h5><p>{x.fix}</p></div>}
          <div className="wa-legal"><h5>Requirement and legal basis</h5><p>{x.requirement}</p>
            <small>Source: {x.source || '—'} · Basis: {x.basis || '—'}{x.penalty.crore ? ` · Max penalty tier: ${x.penalty.max}` : ' · No direct statutory penalty (good practice)'}</small></div>

          {x.status === 'input' && related.length > 0 && canEdit && (
            <div className="wa-related"><h5>Answer to settle this check</h5>
              {related.slice(0, 2).map((qq) => <div className="wa-q" key={qq.id}><div className="wa-q-text"><span className="id">{qq.id}</span><b>{qq.question}</b></div><QuestionControl q={qq} answer={answer} disabled={false} /></div>)}
            </div>
          )}

          <div className="wa-decl">
            <h5>Your declaration and documents</h5>
            {editable && canEdit ? (
              <>
                <p className="wa-sub">Self-declarations are saved as unverified and shown as such. Attach a document to support them.</p>
                <div className="wa-opts">
                  {[['met', 'We meet this'], ['gap', 'We have a gap'], ['na', 'Not applicable']].map(([k, l]) => {
                    const on = (pick || x.declaration?.status) === k;
                    return <button key={k} className={on ? 'on' : ''} onClick={() => setPick(k)}>{l}</button>;
                  })}
                  {x.declaration && <button onClick={() => declare(x.id, 'clear', '')}>Clear</button>}
                </div>
                {(pick || x.declaration) && (
                  <>
                    <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Explain briefly: what you do, where it is documented" maxLength={5000} />
                    <button className="btn primary small" disabled={!(pick || x.declaration?.status)} onClick={() => declare(x.id, pick || x.declaration.status, note)}>Save declaration</button>
                  </>
                )}
              </>
            ) : (
              <p className="wa-sub">{x.status === 'met' || x.status === 'not_met' ? 'This result comes from what the scan observed, so no declaration is needed. Fix the issue and rescan.' : 'Settled by your answers to the scoping questions above.'}</p>
            )}
            {canEdit && x.status !== 'na' && (
              <label className="wa-file"><UploadCloud size={15} /> Attach document <small>PDF, DOCX, PNG, JPG or TXT · max 5 MB</small>
                <input type="file" accept=".pdf,.docx,.png,.jpg,.jpeg,.txt" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(x.id, f); e.target.value = ''; }} /></label>
            )}
            {files.map((f) => <div className="wa-docfile" key={f.id}><CheckCircle2 size={13} />{f.filename}<code>{f.sha256.slice(0, 12)}…</code></div>)}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ export */

export function exportCsv(a) {
  const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const sec = Object.fromEntries(a.sections.map((s) => [s.letter, s.title]));
  const head = ['ID', 'Section', 'Requirement', 'Risk', 'Status', 'Finding', 'Evidence', 'How to fix', 'Source', 'Basis', 'Self-declaration', 'Documents'];
  const rows = a.results.map((x) => [x.id, sec[x.section], x.requirement, RISK[x.risk], STATUS[x.status].label, x.note,
    x.evidence.map((e) => `${e.label}: ${e.detail}${e.url ? ' (' + e.url + ')' : ''}`).join(' | '), x.fix || '', x.source, x.basis,
    x.declaration ? `${x.declaration.status}: ${x.declaration.note}` : '', (a.documents[x.id] || []).map((d) => d.filename).join('; ')]);
  const blob = new Blob(['\ufeff' + [head, ...rows].map((r) => r.map(q).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const el = document.createElement('a');
  el.href = URL.createObjectURL(blob);
  el.download = `dpdp-website-check-${a.scan.target.replace(/[^a-z0-9]+/gi, '-').slice(0, 40)}.csv`;
  el.click();
  URL.revokeObjectURL(el.href);
}
