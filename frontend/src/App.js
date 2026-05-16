import React, { useContext } from 'react';
import Chat from "./Chat";
import VideoCall from "./VideoCall";
import Dashboard from "./Dashboard";
import Login from "./Login";
import Register from "./Register";
import Scrabble from "./Scrabble";
import Recommendations from "./Recommendations";
import Performance from "./Performance";
import Guide from "./Guide";
import TonePractice from "./TonePractice";
import Journal from "./Journal";
import { AuthProvider, AuthContext } from "./AuthContext";
import "./App.css";

function AppContent() {
  const { token } = useContext(AuthContext);

  if (!token) {
    // Simple routing based on URL
    const path = window.location.pathname;
    if (path === '/register') {
      return <Register />;
    }
    return <Login />;
  }

  const path = window.location.pathname;
  if (path === '/chat') {
    return <Chat />;
  }
  if (path === '/videocall') {
    return <VideoCall />;
  }
  if (path === '/scrabble') {
    return <Scrabble />;
  }
  if (path === '/recommendations') {
    return <Recommendations />;
  }
  if (path === '/performance') {
    return <Performance />;
  }
  if (path === '/guide') {
    return <Guide />;
  }
  if (path === '/tone-practice') {
    return <TonePractice />;
  }
  if (path === '/journal') {
    return <Journal />;
  }
  return <Dashboard />;
}

export default function App(){
  return(
    <AuthProvider>
      <div className="app-shell">
        <header className="app-header">
          <div className="brand">
            <div className="brand-title">Zhongwen</div>
            <div className="brand-subtitle">AI Chinese Tutor</div>
          </div>
        </header>
        <div className="app-content">
          <AppContent />
        </div>
      </div>
    </AuthProvider>
  )
}
