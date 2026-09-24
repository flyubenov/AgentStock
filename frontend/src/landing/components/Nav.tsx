const SECTIONS = [
  { href: '#analyze', label: 'Analyze' },
  { href: '#how', label: 'Methodology' },
  { href: '#why', label: 'Why Intrinsica' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#pricing', label: 'Pricing' },
]

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-in">
        <div className="logo">Intrinsica</div>
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
