import { NavLink, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { TuningLab } from './components/TuningLab';
import { AgentManager } from './components/AgentManager';
import { ConversationView } from './components/Conversation';
import { AnalysisView } from './components/Analysis';
import { BlendTool } from './components/BlendTool';
import { TeamWorkbench } from './components/TeamWorkbench';
import { CityView } from './components/CityView';
import { PersonaLibrary } from './components/PersonaLibrary';
import { SettingsView } from './components/Settings';
import {
  IconBlend,
  IconBot,
  IconCity,
  IconSearch,
  IconSettings,
  IconSliders,
  IconUser,
  IconUsers,
} from './components/NavIcons';
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
        <NavLink to="/" className="logo">
          <img
            className="logo-icon"
            src="/deepiri-logo.png"
            alt=""
            width={36}
            height={36}
          />
          <span className="logo-text">
            <span className="logo-deepiri">Deepiri</span>
            <span className="logo-product">Persola</span>
          </span>
        </NavLink>

        <nav className="nav">
          <div className="nav-section">
            <div className="nav-title">Persona</div>
            <NavLink to="/" end className={navCls}>
              <IconSliders /> Tuning Lab
            </NavLink>
            <NavLink to="/personas" className={navCls}>
              <IconUser /> Personas
            </NavLink>
          </div>

          <div className="nav-section">
            <div className="nav-title">Runtime</div>
            <NavLink to="/agents" className={navCls}>
              <IconBot /> Agents
            </NavLink>
          </div>

          <div className="nav-section">
            <div className="nav-title">Tools</div>
            <NavLink to="/analyze" className={navCls}>
              <IconSearch /> Analyze
            </NavLink>
            <NavLink to="/blend" className={navCls}>
              <IconBlend /> Blend
            </NavLink>
            <NavLink to="/teams" className={navCls}>
              <IconUsers /> Team
            </NavLink>
            <NavLink to="/city" className={navCls}>
              <IconCity /> City
            </NavLink>
          </div>

          <div className="nav-section">
            <div className="nav-title">System</div>
            <NavLink to="/settings" className={navCls}>
              <IconSettings /> Settings
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
          <Route path="/teams" element={<TeamWorkbench />} />
          <Route path="/city" element={<CityView />} />
          <Route path="/settings" element={<SettingsView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
