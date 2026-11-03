import React, { useEffect, useState } from 'react';
import { Maker, MAKER_URL } from './brand.jsx';
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  ChevronDown,
  CircleHelp,
  FileCheck2,
  Gauge,
  Globe2,
  Lock,
  ScanSearch,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

/* Public landing page. The scanner behind the form is the logged-out flow in PublicCheck.jsx.
   Copy describes only what the product does: a free score and headline counts before login,
   findings with evidence, declarations, the evidence vault and reports after login. */

const CHECKS = 76; // size of the DPDP website checklist (backend/checklist.json)

const STEPS = [
  [
    Globe2,
    'Scan any website',
    'Enter a public URL. No signup needed to see the result.',
  ],
  [
    Gauge,
    'See the readiness index',
    `Get a score and the count of gaps across ${CHECKS} DPDP checks.`,
  ],
  [
    Building2,
    'Create a workspace',
    'Login unlocks your saved scan and the compliance file behind it.',
  ],
  [
    FileCheck2,
    'Fix and prove',
    'Answer the open questions, declare what is done, keep evidence in one vault and download the report.',
  ],
];

const FAQ = [
  [
    'What do I see without signing in?',
    'Your readiness score and the number of gaps, checks to review, open checks and checks met. The scan reads public pages only, and the result is not saved to any account.',
  ],
  [
    'Why is login required for the full workspace?',
    'Each finding comes with evidence from your pages, and the next steps (scoping questions, declarations, uploaded documents) are about your company. An account keeps all of that private to you.',
  ],
  [
    'Is the result AI-written?',
    'No. The score comes from a fixed, rule-based checklist run on what a visitor can see. An optional AI assistant inside the workspace can help you review, and its output always needs human verification.',
  ],
];

const PREVIEW_ROWS = [
  ['Consent mechanism', 'Section 6', 'On track', 'ok'],
  ['Privacy notice', 'Section 5', 'Review', 'warn'],
  ['Breach readiness', 'Section 8(6)', 'Review', 'warn'],
];

const go = (id) => (e) => {
  e.preventDefault();
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
};

function PreviewRing({ value }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const [on, setOn] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setOn(true), 250);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="lp-ring" role="img" aria-label={`Sample score ${value}`}>
      <svg viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={r} className="trk" />
        <circle
          cx="64"
          cy="64"
          r={r}
          className="val"
          strokeDasharray={`${on ? (c * value) / 100 : 0} ${c}`}
          transform="rotate(-90 64 64)"
        />
      </svg>
      <div>
        <b>{value}</b>
        <span>of 100</span>
      </div>
    </div>
  );
}

export default function Landing({ onSignIn, onStart, initialUrl = '' }) {
  const [url, setUrl] = useState(initialUrl);
  const [open, setOpen] = useState(0);

  return (
    <div className="lp">
      {/* ---------------------------------------------------------- nav */}
      <header className="lp-nav">
        <div className="lp-nav-in">
          <div className="lp-brand">
            <span className="lp-mark">
              <ShieldCheck size={19} />
            </span>
            <b>
              verity<i>.</i>
            </b>
            <span className="lp-by">
              by{' '}
              <strong>
                <Maker />
              </strong>
            </span>
          </div>
          <nav className="lp-links" aria-label="Page sections">
            <a href="#how" onClick={go('how')}>
              How it works
            </a>
            <a href="#login" onClick={go('login')}>
              Why login?
            </a>
            <a href="#faq" onClick={go('faq')}>
              FAQ
            </a>
          </nav>
          <button className="lp-signin" onClick={onSignIn}>
            Sign in <ArrowRight size={14} />
          </button>
        </div>
      </header>

      {/* ---------------------------------------------------------- hero */}
      <section className="lp-hero">
        <div className="lp-hero-copy">
          <span className="lp-pill">
            <Sparkles size={12} /> THE DPDP ACT, MADE ACTIONABLE
          </span>
          <h1>
            Deliver DPDP
            <br />
            <em>for every client.</em>
          </h1>
          <p>
            Scan a website against {CHECKS} DPDP checks, each mapped to its
            section of the Act. See where a client stands first. Build the
            complete compliance file when the work is ready.
          </p>
          <form
            className="lp-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (url.trim()) onStart(url.trim());
            }}
          >
            <Globe2 size={18} className="lp-form-ic" />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://yourwebsite.com"
              aria-label="Website address"
              required
            />
            <button className="btn primary">
              See the free readiness index <ArrowRight size={16} />
            </button>
          </form>
          <small className="lp-micro">
            <Lock size={12} /> Free scanner · No signup needed · Public pages
            only
          </small>
        </div>

        <div className="lp-preview" aria-hidden="false">
          <div className="lp-preview-card">
            <div className="lp-preview-head">
              <span>READINESS INDEX</span>
              <em>Preview</em>
            </div>
            <div className="lp-preview-score">
              <PreviewRing value={72} />
              <div>
                <b>{CHECKS} checks on every scan</b>
                <p>
                  Each check is tied to the section of the DPDP Act or Rules
                  behind it.
                </p>
              </div>
            </div>
            <ul className="lp-rows">
              {PREVIEW_ROWS.map(([name, sec, state, tone]) => (
                <li key={name}>
                  <span>
                    {name} <small>· {sec}</small>
                  </span>
                  <i className={tone}>{state}</i>
                </li>
              ))}
            </ul>
            <div className="lp-preview-foot">
              <ScanSearch size={13} /> Sample preview. Scan your website to see
              your own result.
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- how it works */}
      <section className="lp-band white" id="how">
        <div className="lp-wrap">
          <div className="lp-split">
            <div>
              <span className="lp-eyebrow">A CLEAR FIRST CONVERSATION</span>
              <h2>
                Give prospects something useful before asking for something
                personal.
              </h2>
            </div>
            <p className="lp-lead">
              The free scanner creates a moment of value. Login becomes the
              natural next step when client context, evidence, and reports
              actually matter.
            </p>
          </div>
          <div className="lp-steps">
            {STEPS.map(([Icon, title, text], i) => (
              <div className="lp-step" key={title}>
                <div className="lp-step-top">
                  <span>0{i + 1}</span>
                  <Icon size={19} />
                </div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- login */}
      <section className="lp-band" id="login">
        <div className="lp-wrap lp-login">
          <div className="lp-login-copy">
            <span className="lp-tile">
              <Sparkles size={19} />
            </span>
            <h2>Login where the value gets personal.</h2>
            <p>
              Don&rsquo;t put a wall in front of curiosity. Put the wall around
              the information that needs trust.
            </p>
          </div>
          <div className="lp-login-cards">
            <div className="lp-dark">
              <span className="lp-eyebrow">BEFORE LOGIN</span>
              <div>
                <Sparkles size={17} />
                <div>
                  <b>A free scanner, not a sales pitch.</b>
                  <p>
                    Share the score and the headline counts from the public
                    scan. Findings with evidence, declarations, the evidence
                    vault, and reports stay inside the client workspace.
                  </p>
                </div>
              </div>
            </div>
            <div className="lp-light">
              <Lock size={18} />
              <h3>After login</h3>
              <p>
                Company details, saved scans, declarations, findings, and a
                private workspace.
              </p>
            </div>
            <div className="lp-light">
              <CircleHelp size={18} />
              <h3>The handoff</h3>
              <p>
                Download the report and share it with your team or counsel, so
                everyone works from the same findings.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- faq */}
      <section className="lp-band white" id="faq">
        <div className="lp-wrap lp-faq">
          <span className="lp-eyebrow">FREQUENTLY ASKED</span>
          <h2>The short version.</h2>
          <div className="lp-acc">
            {FAQ.map(([q, a], i) => (
              <div className={'lp-qa' + (open === i ? ' open' : '')} key={q}>
                <button
                  aria-expanded={open === i}
                  onClick={() => setOpen(open === i ? -1 : i)}
                >
                  {q}
                  <ChevronDown size={16} />
                </button>
                <div className="lp-qa-body">
                  <p>{a}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- maker */}
      <section className="lp-maker">
        <span className="lp-eyebrow">A PRODUCT OF</span>
        <h2>
          <Maker />
        </h2>
        <p>
          Verity is designed, built and maintained by Elevatics AI, an
          enterprise AI automation company.
        </p>
        <a
          className="lp-maker-btn"
          href={MAKER_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          Visit elevatics.ai <ArrowUpRight size={14} />
        </a>
      </section>

      <footer className="lp-foot">
        <span>
          &copy; 2026 <Maker /> &middot; Verity - DPDP compliance, made
          practical.
        </span>
        <span>Built for practitioners, consultancies, and DPOs.</span>
      </footer>
    </div>
  );
}
