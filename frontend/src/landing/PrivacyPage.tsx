import { useEffect } from 'react'
import './theme.css'
import { Logo } from './components/Nav'
import SiteFooter from './components/SiteFooter'
import { isOwner } from '../lib/analytics'

/** The privacy notice (launch checklist B4, 2026-10-02). The checkout collects an
 *  optional email and every visitor gets a browser ID, and the site is run from
 *  the EU, so both pages link here.
 *
 *  Every claim below must stay true of the code. When a new kind of data is
 *  collected (a new event prop, a new third-party request), this page changes in
 *  the same commit — PrivacyPage.test.tsx lists what it must disclose. */

export const CONTACT_EMAIL = 'contact@intrinsica.io'
export const UPDATED = '3 October 2026'

function Mail() {
  return <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
}

export default function PrivacyPage() {
  useEffect(() => {
    document.title = 'Privacy notice · Intrinsica'
    const previous = document.body.style.backgroundColor
    document.body.style.backgroundColor = '#ffffff'
    return () => { document.body.style.backgroundColor = previous }
  }, [])

  return (
    <div className="intrinsica">
      <nav className="nav">
        <div className="nav-in">
          <Logo />
          <div className="links"><a className="back" href="/">← Back to Intrinsica</a></div>
        </div>
      </nav>

      <section className="section stage">
        <div className="container privacy">
          <div className="kicker">Last updated {UPDATED}</div>
          <h1 className="stitle">Privacy notice</h1>

          <p>
            Intrinsica is a pre-launch product. This page explains what the site collects
            while we measure interest in it, why, and what you can ask us to do with it.
            Questions or requests: <Mail />.
          </p>

          <h2>Who we are</h2>
          <p>
            Intrinsica (intrinsica.io), operated from the European Union, is responsible for
            the data described here. Contact: <Mail />.
          </p>

          <h2>What we collect</h2>
          <ul>
            <li>
              <b>A random visitor ID</b> kept in your browser's local storage, plus a count
              of the free analyses you've used and the channel you first arrived from. The
              ID isn't linked to your name, and we use no advertising trackers. If you give us
              your email, it is stored with your visitor ID and the events above.
            </li>
            <li>
              <b>What you do on the site</b>: for example page views, the tickers you analyse,
              which scores and plans you look at, and clicks on Share, plans, checkout and
              payment buttons, each with a time stamp.
            </li>
            <li>
              <b>Where you came from</b>: the campaign tags in the link you followed, and the
              domain of the site that sent you (for example google.com, never the full
              address).
            </li>
            <li>
              <b>Your optional email</b>, only if you type it on the checkout page to hear
              about early access.
            </li>
            <li>
              <b>Your IP address</b>, which every web request carries. We keep it only in
              server memory, to limit abusive traffic, and never write it to storage. Our
              hosting provider keeps it in request
              logs for up to 30 days. We don't store it with the events above.
            </li>
          </ul>

          <h2>Why</h2>
          <p>
            To find out whether people want a paid version of Intrinsica and which channels
            bring them (our legitimate interest in testing the product before building it),
            and, if you gave us your email, to tell you when early access opens (your
            consent, which you can withdraw at any time).
          </p>

          <h2>Who processes it</h2>
          <ul>
            <li><b>Google Cloud</b> hosts the site in Belgium (europe-west1).</li>
            <li><b>Google Sheets</b> stores the events and emails.</li>
          </ul>
          <p>
            Google may process data outside the EU under its standard contractual clauses.
            We don't sell or share your data with anyone else.
          </p>

          <h2>How long we keep it</h2>
          <p>
            Events and emails are deleted within 12 months after the pre-launch test ends,
            or sooner if you ask. The data in your browser stays until you clear your site
            data.
          </p>

          <h2>Your rights</h2>
          <p>
            You can ask for a copy of your data, or ask us to correct or delete it, or to
            stop using it, by writing to <Mail />. Include the visitor ID shown below if you
            want us to find your events. You can also lodge a complaint with your national
            data protection authority.
          </p>
          <p className="mute">Your visitor ID: <VisitorIdLine /></p>
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}

/** Shown so a visitor can quote it in a request: without it, events tied to a
 *  random ID can't be found, and a deletion request can't be honoured. Read
 *  directly rather than through analytics.visitorId(), which would mint an ID
 *  for a visitor who has none. */
function VisitorIdLine() {
  let id: string | null = null
  try { id = localStorage.getItem('intrinsica_vid') } catch { /* blocked storage */ }
  if (id && isOwner()) id = `me-${id}`
  return <code>{id ?? 'none stored in this browser'}</code>
}
