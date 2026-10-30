import { StrictMode, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { AuthProvider, RequireAuth } from './auth';
import { DataProvider } from './data/load';
import { Shell } from './components/Shell';
import { Home } from './screens/Home';
import { ArchitecturePage } from './screens/Architecture';
import { Results } from './screens/Results';
import { Login } from './screens/Login';
import { Queue } from './screens/Queue';
import { PatientDetail } from './screens/PatientDetail';
import { Why } from './screens/Why';
import { Intake } from './screens/Intake';
import { Resolution } from './screens/Resolution';
import { Patterns, WardAdmit, WardList, WardRecordScreen } from './screens/Ward';
import './styles.css';

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

// Keyed by id so dismissed EHR alerts and the handoff form reset between patients.
function PatientRoute() {
  const { id } = useParams();
  return <PatientDetail key={id} />;
}

function AppLayout() {
  return (
    <RequireAuth>
      <DataProvider>
        <Shell><Outlet /></Shell>
      </DataProvider>
    </RequireAuth>
  );
}

/** Short links (/why, /intake) keep their query string, so /why?demo=1 works. */
function Short({ to }: { to: string }) {
  const { search } = useLocation();
  return <Navigate to={to + search} replace />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter basename={import.meta.env.BASE_URL} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ScrollTop />
        <Routes>
          <Route path="/" element={<DataProvider><Home /></DataProvider>} />
          <Route path="/results" element={<DataProvider><Results /></DataProvider>} />
          <Route path="/architecture" element={<DataProvider><ArchitecturePage /></DataProvider>} />
          <Route path="/models" element={<Navigate to="/architecture" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Queue />} />
            <Route path="patient/:id" element={<PatientRoute />} />
            <Route path="why" element={<Why />} />
            <Route path="intake" element={<Intake />} />
            <Route path="resolution" element={<Resolution />} />
            <Route path="evaluation" element={<Navigate to="/results" replace />} />
            <Route path="ward" element={<WardList />} />
            <Route path="ward/new" element={<WardAdmit />} />
            <Route path="ward/patterns" element={<Patterns />} />
            <Route path="ward/:id" element={<WardRecordScreen />} />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Route>
          <Route path="/why" element={<Short to="/app/why" />} />
          <Route path="/intake" element={<Short to="/app/intake" />} />
          <Route path="*" element={<Short to="/app" />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
