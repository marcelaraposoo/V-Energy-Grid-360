import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { UnidadesPage } from './features/unidades/UnidadesPage'
import { OrdensPage } from './features/inspecoes/OrdensPage'
import { AssistentePage } from './features/assistente/AssistentePage'
import { NotFoundPage } from './pages/NotFoundPage'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="uc" element={<UnidadesPage />} />
          <Route path="uc/:id" element={<UnidadesPage />} />
          <Route path="inspecoes/ordens" element={<OrdensPage />} />
          <Route path="assistente" element={<AssistentePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
