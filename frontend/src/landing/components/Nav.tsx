import BrandMark from './BrandMark'

const SECTIONS = [
  { href: '#analyze', label: 'Analyze' },
  { href: '#how', label: 'Methodology' },
  { href: '#why', label: 'Why Intrinsica' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#pricing', label: 'Pricing' },
]

/** The logo block, shared with the checkout's mini-nav. */
export function Logo() {
  return <div className="logo"><BrandMark size={42} />Intrinsica</div>
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
