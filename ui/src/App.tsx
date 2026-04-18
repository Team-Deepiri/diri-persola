import { NavLink, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { TuningLab } from './components/TuningLab';
import { AgentManager } from './components/AgentManager';
import { ConversationView } from './components/Conversation';
import { AnalysisView } from './components/Analysis';
import { BlendTool } from './components/BlendTool';
import { PersonaLibrary } from './components/PersonaLibrary';
import './App.css';

function AgentChatPage() {
  const { id } = useParams<{ id: string }>();
  return <ConversationView initialAgentId={id} />;
}

const navCls = ({ isActive }: { isActive: boolean }) =>
  `nav-item${isActive ? ' active' : ''}`;

function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <NavLink to="/" className="logo" style={{ textDecoration: 'none' }}>
          <div className="logo-icon">P</div>
          Persola
        </NavLink>

        <nav className="nav">
          <div className="nav-section">
            <div className="nav-title">Persona</div>
            <NavLink to="/" end className={navCls}>
              <span>🎛️</span> Tuning Lab
            </NavLink>
            <NavLink to="/personas" className={navCls}>
              <span>👤</span> Personas
            </NavLink>
          </div>

          <div className="nav-section">
            <div className="nav-title">Runtime</div>
            <NavLink to="/agents" className={navCls}>
              <span>🤖</span> Agents
            </NavLink>
          </div>

          <div className="nav-section">
            <div className="nav-title">Tools</div>
            <NavLink to="/analyze" className={navCls}>
              <span>🔍</span> Analyze Style
            </NavLink>
            <NavLink to="/blend" className={navCls}>
              <span>🎭</span> Blend
            </NavLink>
          </div>
        </nav>
      </aside>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<TuningLab />} />
          <Route path="/personas" element={<PersonaLibrary />} />
          <Route path="/agents" element={<div className="page-container"><AgentManager /></div>} />
          <Route path="/agents/:id/chat" element={<AgentChatPage />} />
          <Route path="/analyze" element={<AnalysisView />} />
          <Route path="/blend" element={<BlendTool />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
