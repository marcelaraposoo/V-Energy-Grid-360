import { useEffect, useRef, useState } from 'react'
import { Menu, Search, Sparkles, Zap } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { UnitSearch } from '../ui/UnitSearch'
import { getCurrentPage, navigation } from './navigation'

function Brand({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      className="brand"
      to="/"
      aria-label="V-Energy Grid 360 — início"
      onClick={onNavigate}
    >
      <svg
        className="brand-mark"
        width="34"
        height="36"
        viewBox="0 0 34 36"
        fill="none"
        aria-hidden="true"
      >
        <path d="M1 4h9l8 21-5 10L1 4Z" fill="currentColor" opacity=".65" />
        <path d="M24 1h10L20 35H10L24 1Z" fill="currentColor" />
      </svg>
      <span className="brand-copy">
        <strong>V-Energy</strong>
        <small>Grid 360</small>
      </span>
    </Link>
  )
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="sidebar-nav" aria-label="Navegação principal">
      {navigation.map((section) => (
        <div className="nav-group" key={section.group}>
          <p className="nav-group-label">{section.group}</p>
          {section.items.map(({ to, title, icon: Icon }) => (
            <NavLink
              to={to}
              end={to === '/'}
              key={to}
              onClick={onNavigate}
              title={title}
              aria-label={title}
              className={({ isActive }) =>
                `nav-link${isActive ? ' nav-link--active' : ''}`
              }
            >
              <Icon size={20} strokeWidth={1.6} aria-hidden="true" />
              <span className="nav-label">{title}</span>
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )
}

function SidebarFooter() {
  return (
    <footer className="sidebar-footer">
      <span className="sidebar-footer-symbol">
        <Zap size={18} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <div>
        <p>Uma visão. Mais possibilidades.</p>
        <small>V-Energy Grid 360</small>
      </div>
    </footer>
  )
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const mobileMenu = useRef<HTMLDialogElement>(null)
  const location = useLocation()
  const page = getCurrentPage(location.pathname)

  useEffect(() => {
    document.title = `${page.title} | V-Energy Grid 360`
    document.getElementById('main-content')?.focus()
    window.scrollTo(0, 0)
  }, [location.pathname, page.title])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        const search = [
          document.getElementById('global-uc-search'),
          document.getElementById('page-uc-search'),
        ].find((element) => element?.getClientRects().length)
        if (search) {
          event.preventDefault()
          search.focus()
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 768px)')
    function closeMobileMenu(event: MediaQueryListEvent) {
      if (event.matches) mobileMenu.current?.close()
    }
    desktop.addEventListener('change', closeMobileMenu)
    return () => desktop.removeEventListener('change', closeMobileMenu)
  }, [])

  return (
    <div className={`app-shell${collapsed ? ' app-shell--collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">
        Pular para o conteúdo
      </a>
      <aside className="sidebar">
        <Navigation />
        <SidebarFooter />
      </aside>

      <dialog
        ref={mobileMenu}
        id="mobile-navigation"
        className="mobile-menu"
        aria-label="Menu de navegação"
        onClick={(event) => {
          if (event.target === event.currentTarget) mobileMenu.current?.close()
        }}
      >
        <div className="mobile-menu-content">
          <div className="mobile-menu-header">
            <Brand onNavigate={() => mobileMenu.current?.close()} />
            <button
              className="icon-button"
              type="button"
              aria-label="Fechar menu"
              onClick={() => mobileMenu.current?.close()}
            >
              <Menu size={22} aria-hidden="true" />
            </button>
          </div>
          <Navigation onNavigate={() => mobileMenu.current?.close()} />
          <SidebarFooter />
        </div>
      </dialog>

      <header className="topbar">
        <div className="topbar-brand">
          <button
            className="sidebar-collapse icon-button"
            onClick={() => setCollapsed(!collapsed)}
            type="button"
            aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
            aria-expanded={!collapsed}
          >
            <Menu size={22} aria-hidden="true" />
          </button>
          <button
            className="mobile-menu-trigger icon-button"
            type="button"
            aria-label="Abrir menu"
            aria-haspopup="dialog"
            aria-controls="mobile-navigation"
            onClick={() => mobileMenu.current?.showModal()}
          >
            <Menu size={22} aria-hidden="true" />
          </button>
          <Brand />
        </div>
        <div className="topbar-actions">
          <div className="global-search">
            <UnitSearch compact />
          </div>
          <Link
            to="/uc"
            className="icon-button mobile-search"
            aria-label="Buscar unidade consumidora"
          >
            <Search size={20} />
          </Link>
          <Link
            className="assistant-shortcut"
            to="/assistente"
            aria-label="Perguntar à IA"
          >
            <Sparkles size={16} aria-hidden="true" />
            <span>Perguntar à IA</span>
          </Link>
        </div>
      </header>
      <div className="app-workspace">
        <main className="main-content" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>V-Energy Grid 360</span>
        </footer>
      </div>
    </div>
  )
}
