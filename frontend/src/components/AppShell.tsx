import { FilePlus2, FolderKanban, MapPinned } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">GV</div>
          <div>
            <div className="brand-name">GeoVision</div>
            <div className="brand-org">Site screening</div>
          </div>
        </div>

        <div className="nav-section">Workspace</div>
        <NavLink to="/" end className="nav-item">
          <FolderKanban size={16} />
          Projects
        </NavLink>
        <NavLink to="/new" className="nav-item">
          <FilePlus2 size={16} />
          New screening
        </NavLink>

        <div className="sidebar-foot">
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <MapPinned size={13} />
            India · Site Screening module
          </div>
          <div style={{ marginTop: 2 }}>v0.1</div>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  )
}
