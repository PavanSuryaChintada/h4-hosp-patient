import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Shell } from './components/Shell';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="*" element={<div className="content"><h1 className="display">Patients</h1></div>} />
        </Routes>
      </Shell>
    </BrowserRouter>
  </StrictMode>,
);
