import React, { useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  Globe2,
  Layers,
  Loader2,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react';
import { Ring } from './ReportDoc.jsx';
import Landing from './Landing.jsx';
import { Maker } from './brand.jsx';
import { host, when } from './reportData.js';
import './public.css';

/* Logged-out journey: landing -> company details -> website address -> headline score.
   Everything beyond the score (findings, evidence, fixes, declarations, report) needs an account.
   The company details and address are kept in sessionStorage so Setup and the website check are prefilled after signup. */

const API = import.meta.env.VITE_API_URL || '/api';
export const LEAD_KEY = 'dpdp-lead';

export function Brand() {
  return (
    <div className="lp-brand pc-brand">
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
  );
}

export default function PublicCheck({ onSignIn, onDetails }) {
  const [step, setStep] = useState('landing'); // landing | company | url | scanning | result
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('Technology');
  const [type, setType] = useState('Data Fiduciary');
  const [url, setUrl] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const saveLead = () =>
    sessionStorage.setItem(
      LEAD_KEY,
      JSON.stringify({ name: name.trim(), industry, type, domain: url.trim() })
    );

  const runScan = async () => {
    setError('');
    setStep('scanning');
    try {
      const r = await fetch(API + '/public/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok)
        throw Error(
          typeof j.detail === 'string'
            ? j.detail
            : 'The check could not be completed.'
        );
      setResult(j);
      setStep('result');
    } catch (e) {
      setError(e.message);
      setStep('url');
    }
  };

  if (step === 'landing')
    return (
      <Landing
        initialUrl={url}
        onSignIn={onSignIn}
        onStart={(u) => {
          setUrl(u);
          setStep('company');
        }}
      />
    );

  if (step === 'company')
    return (
      <div className="auth-shell">
        <Brand />
        <div className="auth-card">
          <h1>About your company</h1>
          <p>
            {url.trim()
              ? `We will check ${host(url)} next. These details also prepare your workspace.`
              : 'These details are used to set up your workspace later.'}
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (url.trim()) runScan();
              else setStep('url');
            }}
          >
            <label>
              Company legal name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="Acme India Private Limited"
              />
            </label>
            <label>
              Industry
              <input
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
              />
            </label>
            <label>
              Company data role
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option>Data Fiduciary</option>
                <option>Data Processor</option>
                <option>Significant Data Fiduciary</option>
                <option>Registered Consent Manager</option>
              </select>
            </label>
            <button className="btn primary wide">
              {url.trim() ? 'Run the free scan' : 'Next'}{' '}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="auth-switch">
            <button onClick={() => setStep('landing')}>Back</button>
          </div>
        </div>
        <small className="pc-brandline auth-foot">
          Verity is a product of{' '}
          <strong>
            <Maker />
          </strong>
        </small>
      </div>
    );

  if (step === 'url' || step === 'scanning')
    return (
      <div className="auth-shell">
        <Brand />
        <div className="auth-card">
          {step === 'scanning' ? (
            <div className="pc-scanning" aria-live="polite">
              <Loader2 size={30} className="spin" />
              <h1>Reading {host(url)}</h1>
              <p>
                This usually takes 20 to 60 seconds. Please keep this page
                open.
              </p>
            </div>
          ) : (
            <>
              <h1>Your website</h1>
              <p>Enter the address of your public website.</p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (url.trim()) runScan();
                }}
              >
                <label>
                  Website address
                  <div className="pc-input">
                    <Globe2 size={17} />
                    <input
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      required
                      placeholder="https://yourcompany.com"
                      autoFocus
                    />
                  </div>
                </label>
                {error && (
                  <div className="form-error pc-error">
                    <AlertCircle size={14} /> {error}
                  </div>
                )}
                <button className="btn primary wide">
                  Check website <ArrowRight size={17} />
                </button>
              </form>
              <div className="auth-switch">
                <button onClick={() => setStep('company')}>Back</button>
              </div>
            </>
          )}
        </div>
        <small className="pc-brandline auth-foot">
          Verity is a product of{' '}
          <strong>
            <Maker />
          </strong>
        </small>
      </div>
    );

  // result
  const r = result;
  return (
    <div className="pc-shell">
      <div className="pc-top">
        <Brand />
        <button className="btn secondary small" onClick={onSignIn}>
          Sign in
        </button>
      </div>
      <div className="pc-result">
        <div className="pc-score">
          <div className="pc-score-main">
            <div className="eyebrow">YOUR READINESS INDEX</div>
            <h2>{r.host}</h2>
            <div className="pc-chips">
              <span>
                <Calendar size={13} /> {when(r.scanned)}
              </span>
              <span>
                <Layers size={13} /> {r.pages} page{r.pages === 1 ? '' : 's'}{' '}
                read
              </span>
            </div>
          </div>
          <div className="pc-score-ring">
            <Ring pct={r.percent} />
            <div>
              <b>
                {r.observed ? `${r.met} of ${r.observed}` : 'Nothing settled'}
              </b>
              <span>
                {r.observed
                  ? 'checks the scan could settle are met'
                  : 'from the public site'}
              </span>
              <small>{r.unsettled} more need your answers or review</small>
            </div>
          </div>
        </div>

        <div className="pc-stats">
          <div className="red">
            <b>{r.gaps}</b>
            <span>Gaps</span>
          </div>
          <div className="amber">
            <b>{r.review}</b>
            <span>To review</span>
          </div>
          <div className="blue">
            <b>{r.open}</b>
            <span>Open</span>
          </div>
          <div className="green">
            <b>{r.passed}</b>
            <span>Met</span>
          </div>
        </div>

        <div className="pc-locked">
          <LockKeyhole size={22} />
          <div>
            <b>Want to know which checks failed and why?</b>
            <p>
              Log in to see each finding with its evidence and how to fix it,
              answer the questions that settle the open checks, and download
              the full report.
            </p>
          </div>
          <button
            className="btn primary"
            onClick={() => {
              saveLead();
              onDetails();
            }}
          >
            Log in to see details <ArrowRight size={16} />
          </button>
        </div>
        <div className="pc-foot">
          <button className="text-link" onClick={() => setStep('url')}>
            Check another website
          </button>
          <small>
            Based on public pages only. This is a findings summary, not a
            certification of compliance.
          </small>
          <small className="pc-brandline">
            Verity is a product of{' '}
          <strong>
            <Maker />
          </strong>
          </small>
        </div>
      </div>
    </div>
  );
}


