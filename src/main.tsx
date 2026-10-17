import { StrictMode, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { AuthProvider, RequireAuth } from './auth';
import { Shell } from './components/Shell';
import { TourProvider } from './components/Tour';
import { Landing } from './screens/Landing';
import { Login } from './screens/Login';
import { Queue } from './screens/Queue';
import { PatientDetail } from './screens/PatientDetail';
import { Resolution } from './screens/Resolution';
import { Method } from './screens/Method';
import { Evaluation } from './screens/Evaluation';
import './styles.css';

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

// Keyed by id so the collapse toggle resets when moving between patients.
function PatientRoute() {
  const { id } = useParams();
  return <PatientDetail key={id} />;
}

function AppLayout() {
  return (
    <RequireAuth>
      <TourProvider>
        <Shell><Outlet /></Shell>
      </TourProvider>
    </RequireAuth>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter basename={import.meta.env.BASE_URL} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ScrollTop />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Queue />} />
            <Route path="patient/:id" element={<PatientRoute />} />
            <Route path="resolution" element={<Resolution />} />
            <Route path="method" element={<Method />} />
            <Route path="evaluation" element={<Evaluation />} />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
