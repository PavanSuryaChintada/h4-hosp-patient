import { StrictMode, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { Shell } from './components/Shell';
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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ScrollTop />
      <Shell>
        <Routes>
          <Route path="/" element={<Queue />} />
          <Route path="/patient/:id" element={<PatientRoute />} />
          <Route path="/resolution" element={<Resolution />} />
          <Route path="/method" element={<Method />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="*" element={<Queue />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  </StrictMode>,
);
