import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes, useParams } from 'react-router-dom';
import { Shell } from './components/Shell';
import { Queue } from './screens/Queue';
import { PatientDetail } from './screens/PatientDetail';
import { Resolution } from './screens/Resolution';
import './styles.css';

// Keyed by id so the collapse toggle resets when moving between patients.
function PatientRoute() {
  const { id } = useParams();
  return <PatientDetail key={id} />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Queue />} />
          <Route path="/patient/:id" element={<PatientRoute />} />
          <Route path="/resolution" element={<Resolution />} />
          <Route path="*" element={<Queue />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  </StrictMode>,
);
