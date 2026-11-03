import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Printer, ShieldCheck } from 'lucide-react';
import { STATUS, RISK } from './WebsiteAudit.jsx';
import { Maker } from './brand.jsx';
import {
  GAP,
  PASS,
  OPEN,
  derive,
  host,
  shortUrl,
  when,
} from './reportData.js';
import './reportPrint.css';

/* The printed / PDF form of the website report. It is a separate layout from the on-screen report on purpose:
   no collapsible groups, no buttons, one compact card per gap, and tables for the long tail of open and met checks.

   Two ways it is used:
   - <PrintRoute> at /report/<org>/<scan>/print, which the server renders to PDF with headless Chromium
     (GET /api/orgs/<org>/scans/<scan>/report.pdf). Page numbers and the footer come from Chromium there.
   - <ReportDoc embedded> inside the Reports page, hidden on screen and shown by window.print(), so
     "Print" still produces the same document if the server cannot render PDFs. */

const clip = (t, n) => {
  const s = (t || '').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s;
};
const firstSentence = (t, n = 190) => {
  const s = (t || '').replace(/\s+/g, ' ').trim();
  const m = s.match(/^.*?[.!?](?=\s|$)/);
  return clip(m ? m[0] : s, n);
};
const cssStr = (t) =>
  String(t).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\s+/g, ' ');
const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + 's'}`;
const tier = (x) => (x.penalty?.crore ? x.penalty.max : '-');

export function Ring({ pct }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone =
    pct == null ? 'mute' : pct >= 80 ? 'green' : pct >= 50 ? 'amber' : 'red';
  return (
    <div
      className="rp-ring"
      role="img"
      aria-label={pct == null ? 'Nothing settled' : `${pct} percent met`}
    >
      <svg viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={r} className="trk" />
        {pct != null && (
          <circle
            cx="64"
            cy="64"
            r={r}
            className={'val ' + tone}
            strokeDasharray={`${(c * pct) / 100} ${c}`}
            transform="rotate(-90 64 64)"
          />
        )}
      </svg>
      <div>
        <b>
          {pct == null ? '-' : pct}
          {pct != null && <small>%</small>}
        </b>
        <span>met</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ document */

export default function ReportDoc({ a, embedded = false }) {
  const m = useMemo(() => derive(a), [a]);
  const rep = a.report || {};
  const site = host(a.scan.target);
  const client = rep.client || site;
  const generated = when(rep.generated || new Date().toISOString());
  const secOf = (id) => a.sections.find((s) => s.letter === id);
  const tops = [...m.gapList, ...m.review].slice(0, 3);
  const unsettled = a.summary.total - m.observed - m.counts.na;
  const tag = [rep.id, rep.hash ? 'SHA-256 ' + rep.hash.slice(0, 12) : '']
    .filter(Boolean)
    .join(' · ');

  // numbered chapters, only for the ones that have content
  const chapters = [
    ['exec', 'Executive summary'],
    ['score', 'Results by checklist section'],
    ['gaps', `Gaps (${m.gaps})`],
    m.review.length && ['review', `Needs review (${m.review.length})`],
    m.open.length && ['open', `Open items (${m.open.length})`],
    ['met', `Met and not applicable (${m.pass.length + m.na.length})`],
    ['appx', 'Appendix: scope, method and disclaimer'],
  ].filter(Boolean);
  const no = (key) => chapters.findIndex((c) => c[0] === key) + 1;

  return (
    <div className={'pr-doc' + (embedded ? ' embedded' : '')}>
      {embedded && (
        // Branded footer with page numbers in the page margin (Chrome 131+, Edge). The server-side PDF route does not
        // use this: it draws its own footer, so it renders with embedded={false}.
        <style>{`@page footed{size:A4;margin:14mm 14mm 16mm;
          @bottom-left{content:"${cssStr(`Verity by Elevatics AI · ${site} · DPDP Report${tag ? ' · ' + tag : ''}`)}";font:8px "Segoe UI",Arial,sans-serif;color:#94a3b8;vertical-align:top;padding-top:4mm}
          @bottom-right{content:"Page " counter(page) " of " counter(pages);font:8px "Segoe UI",Arial,sans-serif;color:#94a3b8;vertical-align:top;padding-top:4mm}}`}</style>
      )}

      {/* ---------- cover ---------- */}
      <section className="pr-cover">
        <div className="pr-logo">
          <span className="pr-mark">
            <ShieldCheck size={22} />
          </span>
          <div>
            <b>
              verity<i>.</i>
            </b>
            <small>
              BY <Maker>ELEVATICS AI</Maker>
            </small>
          </div>
        </div>
        <div className="pr-cover-main">
          <div className="pr-eyebrow">DPDP COMPLIANCE REPORT</div>
          <h1>{site}</h1>
          <p>
            Findings from a passive scan of the public website, tested against
            the {a.summary.total}-check DPDP website checklist.
          </p>
          <dl className="pr-meta">
            <div>
              <dt>Prepared for</dt>
              <dd>{client}</dd>
            </div>
            <div>
              <dt>Website</dt>
              <dd>{shortUrl(a.scan.target)}</dd>
            </div>
            <div>
              <dt>Scan date</dt>
              <dd>{when(a.scan.created)}</dd>
            </div>
            <div>
              <dt>Report ID</dt>
              <dd>{rep.id || '-'}</dd>
            </div>
            <div>
              <dt>Pages read</dt>
              <dd>
                {a.pages_scanned} ·{' '}
                {a.mode === 'browser' ? 'browser-rendered' : 'static HTML'}
              </dd>
            </div>
            <div>
              <dt>Generated</dt>
              <dd>{generated}</dd>
            </div>
          </dl>
        </div>
        <div className="pr-toc">
          <h4>Contents</h4>
          <ol>
            {chapters.map(([k, t]) => (
              <li key={k}>{t}</li>
            ))}
          </ol>
        </div>
        {rep.hash && (
          <small className="pr-hash">
            Report fingerprint (SHA-256): {rep.hash}
          </small>
        )}
      </section>

      {/* ---------- executive summary ---------- */}
      <section className="pr-sec">
        <h2 className="pr-h2">
          <i>{no('exec')}</i> Executive summary
        </h2>
        <div className="pr-top">
          <div className="pr-box pr-score-box">
            <Ring pct={m.metPct} />
            <div>
              <b>
                {m.observed
                  ? `${m.counts.met} of ${m.observed} settled checks are met`
                  : 'Nothing could be settled from outside'}
              </b>
              <span>
                The checklist has {a.summary.total} checks. {m.observed} could
                be settled from the public site; {unsettled} need your answers
                or a reviewer
                {m.counts.na ? `; ${m.counts.na} do not apply` : ''}.
              </span>
            </div>
          </div>
          <div className="pr-box pr-exposure">
            <h4>Penalty exposure</h4>
            {m.exposure ? (
              <>
                <strong>{m.exposure.max}</strong>
                <em>Statutory maximum, not a prediction of any penalty.</em>
                <p>
                  Highest tier among the gaps found (check {m.exposure.check}:{' '}
                  {m.exposure.label}).
                </p>
              </>
            ) : (
              <>
                <strong className="ok">No tier triggered</strong>
                <em>Statutory maximum, not a prediction of any penalty.</em>
                <p>
                  No gap with a statutory penalty tier was found in what the
                  scan could see.
                </p>
              </>
            )}
          </div>
        </div>

        <div className="pr-tiles">
          <div className="red">
            <b>{m.gaps}</b>
            <span>Gaps</span>
          </div>
          <div className="amber">
            <b>{m.counts.review}</b>
            <span>To review</span>
          </div>
          <div className="blue">
            <b>{m.counts.input + m.counts.not_testable}</b>
            <span>Open</span>
          </div>
          <div className="green">
            <b>{m.pass.length}</b>
            <span>Met</span>
          </div>
        </div>

        {a.flags.length > 0 && (
          <div className="pr-flags">
            <h4>For legal review</h4>
            <ul>
              {a.flags.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
        )}

        <h3 className="pr-h3">What to do first</h3>
        {tops.length ? (
          <ol className="pr-actions">
            {tops.map((x) => (
              <li key={x.id}>
                <b>{x.requirement}</b>
                <span>
                  {x.fix
                    ? firstSentence(x.fix)
                    : firstSentence(x.note)}{' '}
                  <em>
                    ({x.id}, {GAP.includes(x.status) ? 'gap' : 'to review'})
                  </em>
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="pr-p">
            No gaps or items needing review were found in what the scan could
            see. Answer the open items to complete the picture.
          </p>
        )}

        <p className="pr-p">{m.summaryText}</p>
        <p className="pr-note">
          This is a findings report, not a compliance score or certification. A
          scan of public pages can settle only part of the checklist; the rest
          depends on how the business runs, so those checks are marked{' '}
          <b>Needs your input</b> or <b>Not testable externally</b> instead of
          being guessed.
        </p>
      </section>

      {/* ---------- scorecard ---------- */}
      <section className="pr-sec">
        <h2 className="pr-h2">
          <i>{no('score')}</i> Results by checklist section
        </h2>
        <div className="pr-grid">
          {a.sections.map((sec) => {
            const items = a.results.filter((x) => x.section === sec.letter);
            const c = (sts) =>
              items.filter((x) => sts.includes(x.status)).length;
            const parts = [
              ['red', 'gap', c(GAP)],
              ['amber', 'review', c(['review'])],
              ['blue', 'open', c(OPEN)],
              ['green', 'met', c(PASS)],
              ['mute', 'n/a', c(['na'])],
            ];
            return (
              <div className="pr-sc" key={sec.letter}>
                <div className="pr-sc-t">
                  <i>{sec.letter}</i>
                  <b>{sec.title}</b>
                </div>
                {sec.law && <small>{sec.law}</small>}
                <div className="pr-bar">
                  {parts.map(
                    ([t, , v]) =>
                      v > 0 && (
                        <i
                          key={t}
                          className={t}
                          style={{ width: `${(100 * v) / items.length}%` }}
                        />
                      )
                  )}
                </div>
                <div className="pr-sc-n">
                  {parts.map(
                    ([t, label, v]) =>
                      v > 0 && (
                        <em key={t} className={t}>
                          {v} {label}
                        </em>
                      )
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <h3 className="pr-h3">By risk weight</h3>
        <div className="pr-risks">
          {['H', 'M', 'L'].map((k) => {
            const r = m.byRisk[k];
            return (
              <div key={k}>
                <div className="pr-risk-h">
                  <span className={'rk ' + k}>{RISK[k]} risk</span>
                  <small>
                    {r.gaps} gap{r.gaps === 1 ? '' : 's'} · {r.review} review ·{' '}
                    {r.open} open · {r.pass} met
                  </small>
                </div>
                <div className="pr-bar">
                  {r.total > 0 &&
                    [
                      ['red', r.gaps],
                      ['amber', r.review],
                      ['blue', r.open],
                      ['green', r.pass],
                    ].map(
                      ([t, v]) =>
                        v > 0 && (
                          <i
                            key={t}
                            className={t}
                            style={{ width: `${(100 * v) / r.total}%` }}
                          />
                        )
                    )}
                </div>
              </div>
            );
          })}
        </div>

        <h3 className="pr-h3">Penalty schedule</h3>
        <table className="pr-table">
          <thead>
            <tr>
              <th>Penalty tier in the Act</th>
              <th className="r">Statutory maximum</th>
              <th className="r">Gaps</th>
              <th className="r">Still to settle</th>
            </tr>
          </thead>
          <tbody>
            {m.tiers.map((t) => (
              <tr key={t.label}>
                <td>{t.label}</td>
                <td className="r">
                  <b>{t.max}</b>
                </td>
                <td className="r">{t.gaps || '-'}</td>
                <td className="r">{t.open || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="pr-note">
          The Act has only a few penalty tiers. Notice, consent, rights and
          processor gaps all fall in the lowest one, so the headline often stays
          the same. Checks still to settle could move it up. These are statutory
          maximums, not predictions.
        </p>
      </section>

      {/* ---------- gaps ---------- */}
      <section className="pr-sec">
        <h2 className="pr-h2">
          <i>{no('gaps')}</i> Gaps
        </h2>
        <p className="pr-lead">
          Checks the scan found not met, or that you declared as a gap. Highest
          risk first.
        </p>
        {m.gaps === 0 && (
          <p className="pr-p">No gaps were found in what the scan could see.</p>
        )}
        {m.critical.length > 0 && (
          <>
            <h3 className="pr-h3 red">
              Critical gaps ({m.critical.length}) <small>high risk: fix first</small>
            </h3>
            {m.critical.map((x) => (
              <Card key={x.id} x={x} sec={secOf(x.section)} />
            ))}
          </>
        )}
        {m.otherGaps.length > 0 && (
          <>
            <h3 className="pr-h3 rose">
              Other gaps ({m.otherGaps.length}){' '}
              <small>medium and low risk</small>
            </h3>
            {m.otherGaps.map((x) => (
              <Card key={x.id} x={x} sec={secOf(x.section)} />
            ))}
          </>
        )}
      </section>

      {/* ---------- needs review ---------- */}
      {m.review.length > 0 && (
        <section className="pr-sec">
          <h2 className="pr-h2">
            <i>{no('review')}</i> Needs review
          </h2>
          <p className="pr-lead">
            The scan found something but cannot be sure. A person should
            confirm each one.
          </p>
          {m.review.map((x) => (
            <Card key={x.id} x={x} sec={secOf(x.section)} />
          ))}
        </section>
      )}

      {/* ---------- open items ---------- */}
      {m.open.length > 0 && (
        <section className="pr-sec">
          <h2 className="pr-h2">
            <i>{no('open')}</i> Open items
          </h2>
          <p className="pr-lead">
            {plural(m.open.length, 'check')} cannot be seen from the public
            site. Answer the scoping questions or attach documents in the
            portal to settle them.
          </p>
          <table className="pr-table pr-open">
            <thead>
              <tr>
                <th className="id">ID</th>
                <th>Check</th>
                <th>What we need from you</th>
                <th className="tier">Max tier</th>
              </tr>
            </thead>
            <tbody>
              {m.open.map((x) => (
                <tr key={x.id}>
                  <td className="id">
                    <b>{x.id}</b>
                  </td>
                  <td>
                    {x.requirement}
                    <small>
                      {RISK[x.risk]} risk
                      {x.status === 'not_testable'
                        ? ' · not testable externally'
                        : ''}
                    </small>
                  </td>
                  <td>{clip(x.note, 260)}</td>
                  <td className="tier">{tier(x)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* ---------- met + n/a ---------- */}
      <section className="pr-sec">
        <h2 className="pr-h2">
          <i>{no('met')}</i> Met and not applicable
        </h2>
        {m.pass.length > 0 ? (
          <>
            <h3 className="pr-h3 green">Met ({m.pass.length})</h3>
            <table className="pr-table pr-open">
              <thead>
                <tr>
                  <th className="id">ID</th>
                  <th>Check</th>
                  <th>What we saw</th>
                  <th className="tier">Basis</th>
                </tr>
              </thead>
              <tbody>
                {m.pass.map((x) => (
                  <tr key={x.id}>
                    <td className="id">
                      <b>{x.id}</b>
                    </td>
                    <td>{x.requirement}</td>
                    <td>{clip(x.note, 200)}</td>
                    <td className="tier">
                      {x.status === 'declared_met'
                        ? 'Self-declared'
                        : 'Scan'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="pr-p">
            No check could be confirmed as met from the public site alone.
          </p>
        )}
        {m.na.length > 0 && (
          <>
            <h3 className="pr-h3 mute">Not applicable ({m.na.length})</h3>
            <table className="pr-table pr-open">
              <thead>
                <tr>
                  <th className="id">ID</th>
                  <th>Check</th>
                  <th>Why it does not apply</th>
                </tr>
              </thead>
              <tbody>
                {m.na.map((x) => (
                  <tr key={x.id}>
                    <td className="id">
                      <b>{x.id}</b>
                    </td>
                    <td>{x.requirement}</td>
                    <td>{clip(x.note, 200)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>

      {/* ---------- appendix ---------- */}
      <section className="pr-sec pr-appx">
        <h2 className="pr-h2">
          <i>{no('appx')}</i> Appendix
        </h2>

        <h3 className="pr-h3">Scope of this scan</h3>
        <dl className="pr-meta two">
          <div>
            <dt>Website</dt>
            <dd>{a.scan.target}</dd>
          </div>
          <div>
            <dt>Scanned</dt>
            <dd>{when(a.scan.created)}</dd>
          </div>
          <div>
            <dt>Privacy notice read</dt>
            <dd>{a.notice_url ? shortUrl(a.notice_url) : 'Not found'}</dd>
          </div>
          <div>
            <dt>Method</dt>
            <dd>
              {a.mode === 'browser'
                ? 'Headless browser, as a visitor sees the site'
                : 'Static HTML only'}
            </dd>
          </div>
          <div>
            <dt>Scoping questions answered</dt>
            <dd>
              {m.answeredQ} of {a.questions.length}
            </dd>
          </div>
          <div>
            <dt>Report</dt>
            <dd>{rep.id || '-'}</dd>
          </div>
        </dl>
        {m.caveats.length > 0 && (
          <ul className="pr-caveats">
            {m.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        )}

        <h3 className="pr-h3">
          Pages scanned ({a.pages?.length ?? a.pages_scanned})
        </h3>
        {a.pages?.length > 0 ? (
          <ul className="pr-pages">
            {a.pages.slice(0, 24).map((p) => (
              <li key={p.url}>
                {shortUrl(p.url)}
                {p.kind && <em>{p.kind}</em>}
              </li>
            ))}
            {a.pages.length > 24 && <li>and {a.pages.length - 24} more</li>}
          </ul>
        ) : (
          <p className="pr-p">{plural(a.pages_scanned, 'page')} were read.</p>
        )}

        <h3 className="pr-h3">
          Third-party hosts contacted ({a.third_parties?.length ?? 0})
        </h3>
        {a.third_parties?.length > 0 ? (
          <div className="pr-hosts">
            {Object.entries(
              a.third_parties.reduce((acc, t) => {
                (acc[t.category] = acc[t.category] || []).push(t.host);
                return acc;
              }, {})
            ).map(([cat, hosts]) => (
              <div key={cat}>
                <b>{cat}</b>
                <span>{hosts.join(', ')}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="pr-p">
            No third-party hosts were observed
            {a.mode === 'browser'
              ? '.'
              : '; a browser-rendered scan would reveal more.'}
          </p>
        )}

        <h3 className="pr-h3">How to read the results</h3>
        <table className="pr-table pr-legend">
          <tbody>
            {[
              ['not_met', 'The scan observed that the requirement is not satisfied.'],
              ['review', 'Something was found, but a person must confirm it.'],
              ['input', 'Cannot be seen from outside; settled by your answers or documents.'],
              ['not_testable', 'Internal process; attach evidence to settle it.'],
              ['met', 'The scan observed that the requirement is satisfied.'],
              ['declared_met', 'You declared it. Self-declared items are not verified.'],
            ].map(([s, t]) => (
              <tr key={s}>
                <td>
                  <span className={'pr-st ' + STATUS[s].tone}>
                    {STATUS[s].label}
                  </span>
                </td>
                <td>{t}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="pr-h3">Method and limits</h3>
        <p className="pr-p">
          The scan is passive: it loads public pages, submits nothing and never
          logs in. It records what a visitor&rsquo;s browser observes and applies
          keyword rules to the privacy notice, so wording that is present but
          unclear can be marked <b>Needs review</b>. Items declared by the
          client are labelled self-declared and have not been verified.
        </p>

        <div className="pr-disclaimer">
          <h4>Disclaimer</h4>
          <p>
            This report is not legal advice and is not a certificate of
            compliance with the Digital Personal Data Protection Act, 2023. It
            reflects the website as it was when scanned
            {a.scan.created ? ` (${when(a.scan.created)})` : ''} and cannot see
            internal processes, systems or documents unless they were provided.
            Penalty amounts are statutory maximums, not predictions. Have
            qualified counsel review it before relying on it.
          </p>
          {rep.id && (
            <small>
              {rep.id} · generated {generated}
              {rep.hash ? ` · SHA-256 ${rep.hash}` : ''}
            </small>
          )}
        </div>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ one finding */

function Card({ x, sec }) {
  const tone = STATUS[x.status].tone;
  const needsFix = !PASS.includes(x.status) && x.status !== 'na' && x.fix;
  const ev = x.evidence.slice(0, 3);
  return (
    <article className={'pr-card ' + tone}>
      <header>
        <b className="pr-id">{x.id}</b>
        <span className="pr-req">{x.requirement}</span>
        <span className={'rk ' + x.risk}>{RISK[x.risk]}</span>
        <span className={'pr-st ' + tone}>{STATUS[x.status].label}</span>
      </header>
      <div className={'pr-cols' + (needsFix ? '' : ' one')}>
        <div>
          <h5>What we found</h5>
          <p>{x.note}</p>
          {x.declaration && x.scan_status !== x.status && (
            <p className="pr-sub">
              Scan result before your declaration:{' '}
              <b>{STATUS[x.scan_status].label}</b>.
            </p>
          )}
          {x.declaration?.note && (
            <p className="pr-sub">Your note: {x.declaration.note}</p>
          )}
        </div>
        {needsFix && (
          <div className="pr-fix">
            <h5>How to fix</h5>
            <p>{x.fix}</p>
          </div>
        )}
      </div>
      {ev.length > 0 && (
        <ul className="pr-ev">
          {ev.map((e, i) => (
            <li key={i}>
              <b>{e.label}</b>
              {e.detail && <span>{clip(e.detail, 200)}</span>}
              {e.url && <em>{shortUrl(e.url)}</em>}
            </li>
          ))}
          {x.evidence.length > ev.length && (
            <li className="more">
              + {x.evidence.length - ev.length} more in the online report
            </li>
          )}
        </ul>
      )}
      <small className="pr-legal">
        {sec ? `Section ${sec.letter}: ${sec.title}` : ''}
        {x.source ? ` · ${x.source}` : ''}
        {x.penalty?.crore
          ? ` · Max penalty tier: ${x.penalty.max}`
          : ' · No direct statutory penalty tier (good practice)'}
      </small>
    </article>
  );
}

/* ------------------------------------------------------------------ route for the PDF renderer */

export function PrintRoute({ org, sid }) {
  const [a, setA] = useState(null);
  const [err, setErr] = useState('');
  const serverPdf = new URLSearchParams(window.location.search).has('pdf');
  useEffect(() => {
    const API = import.meta.env.VITE_API_URL || '/api';
    fetch(`${API}/orgs/${org}/scans/${sid}/assessment`, {
      headers: {
        Authorization: `Bearer ${sessionStorage.getItem('dpdp-token')}`,
      },
    })
      .then(async (r) => {
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          throw Error(
            typeof j.detail === 'string' ? j.detail : 'Could not load the report'
          );
        }
        return r.json();
      })
      .then(setA)
      .catch((e) => setErr(e.message));
  }, [org, sid]);

  if (err)
    return (
      <div className="pr-route pr-state">
        {err}. Sign in to the portal first, then open this page again.
      </div>
    );
  if (!a)
    return (
      <div className="pr-route pr-state">
        <Loader2 size={18} className="spin" /> Preparing report…
      </div>
    );
  return (
    <div className="pr-route" data-report-ready="true">
      <div className="pr-toolbar">
        <span>
          Print preview. Choose “Save as PDF” and turn off “Headers and
          footers”, or use Download PDF in the portal.
        </span>
        <button onClick={() => window.print()}>
          <Printer size={14} /> Print
        </button>
      </div>
      {/* ?pdf=1 means the server is rendering: Chromium adds its own footer and page numbers there */}
      <ReportDoc a={a} embedded={!serverPdf} />
    </div>
  );
}

