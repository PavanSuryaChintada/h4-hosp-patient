import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Shell } from './components/Shell';
import { Queue } from './screens/Queue';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Queue />} />
          <Route path="*" element={<Queue />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  </StrictMode>,
);
