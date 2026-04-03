import { useState } from 'react';
import { TuningLab } from './components/TuningLab';
import { AgentManager } from './components/AgentManager';
import './App.css';

type Page = 'tuning' | 'agents';

function App() {
  const [page, setPage] = useState<Page>('tuning');

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-icon">P</div>
          Persola
        </div>
        
        <nav className="nav">
          <div className="nav-section">
            <div className="nav-title">Persona</div>
            <div
              className={`nav-item ${page === 'tuning' ? 'active' : ''}`}
              onClick={() => setPage('tuning')}
            >
              <span>🎛️</span> Tuning Lab
            </div>
            <div
              className={`nav-item ${page === 'agents' ? 'active' : ''}`}
              onClick={() => setPage('agents')}
            >
              <span>🤖</span> Agents
            </div>
          </div>
        </nav>
      </aside>
      
      <main className="main-content">
        {page === 'tuning' && <TuningLab />}
        {page === 'agents' && (
          <div className="page-container">
            <AgentManager />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
