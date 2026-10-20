import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { NewScreening } from './pages/NewScreening'
import { ProjectDetail } from './pages/ProjectDetail'
import { Projects } from './pages/Projects'

function LegacyReportRedirect() {
  const { id = '' } = useParams()
  return <Navigate to={`/projects/${id}`} replace />
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Projects />} />
        <Route path="/new" element={<NewScreening />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
        <Route path="/reports/:id" element={<LegacyReportRedirect />} />
        <Route
          path="*"
          element={
            <div className="content">
              <h1>Page not found</h1>
              <p className="muted" style={{ marginTop: 8 }}>
                <Link to="/">Back to projects</Link>
              </p>
            </div>
          }
        />
      </Routes>
    </AppShell>
  )
}
