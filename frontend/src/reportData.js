/* Pure helpers and numbers shared by the on-screen report (WebsiteReport.jsx) and the print document (ReportDoc.jsx). */

export const GAP = ['not_met', 'declared_gap'];
export const PASS = ['met', 'declared_met'];
export const OPEN = ['input', 'not_testable'];
export const answered = (q) =>
  q.answer != null && (!Array.isArray(q.answer) || q.answer.length > 0);
export const shortUrl = (u) =>
  (u || '')
    .replace(/^https?:\/\//, '')
    .replace(/\/$/, '')
    .slice(0, 80);
export const host = (u) => {
  try {
    return new URL(/^https?:/.test(u) ? u : 'https://' + u).hostname.replace(
      /^www\./,
      ''
    );
  } catch {
    return u || '';
  }
};
export const when = (iso) =>
  new Date(iso).toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
export const list = (ids) =>
  ids.length <= 1
    ? ids.join('')
    : ids.slice(0, -1).join(', ') + ' and ' + ids[ids.length - 1];


/* ------------------------------------------------------------------ numbers */

export function derive(a) {
  const counts = a.summary.counts;
  const rank = { H: 0, M: 1, L: 2 };
  const by = (sts) => a.results.filter((x) => sts.includes(x.status));
  const gapList = by(GAP).sort(
    (x, y) =>
      rank[x.risk] - rank[y.risk] ||
      y.penalty.crore - x.penalty.crore ||
      x.id.localeCompare(y.id)
  );
  const critical = gapList.filter((x) => x.risk === 'H');
  const otherGaps = gapList.filter((x) => x.risk !== 'H');
  const review = by(['review']).sort((x, y) => rank[x.risk] - rank[y.risk]);
  const open = by(OPEN).sort((x, y) => rank[x.risk] - rank[y.risk]);
  const pass = by(PASS);
  const na = by(['na']);
  const observed = counts.met + counts.not_met;
  const metPct = observed ? Math.round((100 * counts.met) / observed) : null;
  const byRisk = Object.fromEntries(
    ['H', 'M', 'L'].map((k) => {
      const it = a.results.filter((x) => x.risk === k && x.status !== 'na');
      const n = (sts) => it.filter((x) => sts.includes(x.status)).length;
      return [
        k,
        {
          total: it.length,
          gaps: n(GAP),
          review: n(['review']),
          open: n(OPEN),
          pass: n(PASS),
        },
      ];
    })
  );
  const settleable = a.results.filter(
    (x) => x.status === 'input' && x.ask.length
  ).length;
  const tierMap = new Map();
  a.results
    .filter((x) => x.penalty.crore > 0 && x.status !== 'na')
    .forEach((x) => {
      const t = tierMap.get(x.penalty.label) || {
        label: x.penalty.label,
        max: x.penalty.max,
        crore: x.penalty.crore,
        gaps: 0,
        open: 0,
      };
      if (GAP.includes(x.status)) t.gaps += 1;
      else if (!PASS.includes(x.status)) t.open += 1; // review, input, not testable
      tierMap.set(x.penalty.label, t);
    });
  const tiers = [...tierMap.values()].sort((p, q) => q.crore - p.crore);
  const exposure = a.summary.top_exposure;
  const gaps = gapList.length;

  const bits = [];
  bits.push(
    `We read ${a.pages_scanned} page${a.pages_scanned === 1 ? '' : 's'} of ${host(a.scan.target)} on ${when(a.scan.created)} and tested it against ${a.summary.total} DPDP website checks.`
  );
  if (observed)
    bits.push(
      `${observed} could be settled from the public site: ${counts.met} met and ${counts.not_met} not met.`
    );
  else bits.push('None could be fully settled from the public site alone.');
  if (counts.review) bits.push(`${counts.review} need a person to confirm.`);
  if (counts.input + counts.not_testable)
    bits.push(
      `${counts.input + counts.not_testable} cannot be seen from outside and depend on your answers or documents.`
    );
  if (critical.length)
    bits.push(
      `The most urgent gaps are ${list(critical.slice(0, 4).map((x) => x.id))}${critical.length > 4 ? ` and ${critical.length - 4} more` : ''}.`
    );
  else if (gaps)
    bits.push(
      `${gaps} gap${gaps === 1 ? ' was' : 's were'} found; none is rated high risk.`
    );
  else bits.push('No gaps were found in what the scan could see.');
  return {
    counts,
    gaps,
    gapList,
    critical,
    otherGaps,
    review,
    open,
    pass,
    na,
    observed,
    metPct,
    byRisk,
    settleable,
    exposure,
    tiers,
    // scanner caveats include notes meant for whoever runs the server; show only what matters to the reader
    caveats: (a.caveats || []).filter((c) => !/DNS|egress|robots/i.test(c)),
    answeredQ: a.questions.filter(answered).length,
    summaryText: bits.join(' '),
  };
}
