import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { NewReport } from './pages/NewReport'
import { ReportDetail } from './pages/ReportDetail'
import { Reports } from './pages/Reports'

export default function App() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="logo">
            <img src="/favicon.svg" width={30} height={30} alt="" />
            <span>
              GeoVision
              <small>Environmental site screening</small>
            </span>
          </Link>
          <nav className="nav">
            <NavLink to="/" end>
              Reports
            </NavLink>
            <NavLink to="/new">New report</NavLink>
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Reports />} />
          <Route path="/new" element={<NewReport />} />
          <Route path="/reports/:id" element={<ReportDetail />} />
          <Route
            path="*"
            element={
              <div className="page">
                <h1>Page not found</h1>
                <Link to="/">Back to reports</Link>
              </div>
            }
          />
        </Routes>
      </main>
    </>
  )
}
