import { TuningLab } from './components/TuningLab';
import './App.css';

function App() {
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
            <div className="nav-item active">
              <span>🎛️</span> Tuning Lab
            </div>
            <div className="nav-item">
              <span>📋</span> Presets
            </div>
            <div className="nav-item">
              <span>🤖</span> Agents
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
        <TuningLab />
      </main>
    </div>
  );
}

export default App;
