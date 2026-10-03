import BrandMark from './BrandMark'

const SECTIONS = [
  { href: '#analyze', label: 'Analyze' },
  { href: '#how', label: 'Methodology' },
  { href: '#why', label: 'Why Intrinsica' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#pricing', label: 'Pricing' },
]

/** The logo block, shared with the checkout's and privacy page's mini-navs. It
 *  links home from every page (user decision 2026-10-03): a /t/ link page otherwise
 *  has no way back to the plain homepage. A plain link, not a router Link, so the
 *  homepage starts fresh with its own example. */
export function Logo() {
  return <a className="logo" href="/"><BrandMark size={42} />Intrinsica</a>
}

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-in">
        <Logo />
        <div className="links">
          {SECTIONS.map(s => (
            <a key={s.href} href={s.href}>{s.label}</a>
          ))}
          <a className="cta" href="#pricing">Sign up</a>
        </div>
      </div>
    </nav>
  )
}
