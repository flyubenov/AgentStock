import { Link, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { pathname } = useLocation()

  const navItems = [
    { href: '/', label: 'Analyse' },
    { href: '/database', label: 'Database' },
  ]

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-200 font-mono">
      <header className="border-b border-[#1e1e2a] bg-[#111118]">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-blue-400 font-bold text-lg tracking-wider">STOCK EVALUATOR</span>
            <span className="text-slate-600 text-xs">AI-Powered Analysis</span>
          </div>
          <nav className="flex gap-6">
            {navItems.map(item => (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  'text-sm transition-colors',
                  pathname === item.href
                    ? 'text-blue-400 border-b border-blue-400 pb-0.5'
                    : 'text-slate-400 hover:text-slate-200'
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
      <footer className="border-t border-[#1e1e2a] mt-12 py-4 text-center text-xs text-slate-600">
        For informational and educational purposes only. Not investment advice.
      </footer>
    </div>
  )
}
