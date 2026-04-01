import { useState } from 'react';
import { TuningLab } from './components/TuningLab';
import { AgentPlayground } from './components/AgentPlayground';
import './App.css';

type View = 'tuning-lab' | 'agent-playground';

function App() {
  const [currentView, setCurrentView] = useState<View>('tuning-lab');

  const renderMainContent = () => {
    switch (currentView) {
      case 'tuning-lab':
        return <TuningLab />;
      case 'agent-playground':
        return <AgentPlayground />;
      default:
        return <TuningLab />;
    }
  };

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
              className={`nav-item ${currentView === 'tuning-lab' ? 'active' : ''}`}
              onClick={() => setCurrentView('tuning-lab')}
            >
              <span>🎛️</span> Tuning Lab
            </div>
            <div className="nav-item">
              <span>📋</span> Presets
            </div>
            <div
              className={`nav-item ${currentView === 'agent-playground' ? 'active' : ''}`}
              onClick={() => setCurrentView('agent-playground')}
            >
              <span>🤖</span> Agent Playground
            </div>
          </div>

          <div className="nav-section">
            <div className="nav-title">Actions</div>
            <div className="nav-item">
              <span>💾</span> Save Persona
            </div>
            <div className="nav-item">
              <span>📂</span> Load Persona
            </div>
          </div>
        </nav>
      </aside>

      <main className="main-content">
        {renderMainContent()}
      </main>
    </div>
  );
}

export default App;
