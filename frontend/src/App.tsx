import { useState, useEffect } from 'react';
import { Navigation } from './components/Navigation';
import type { TabType } from './components/Navigation';

// Page Views
import { LandingPage } from './pages/LandingPage';
import { AuthPage } from './pages/AuthPage';
import { Dashboard } from './pages/Dashboard';
import { InteractiveHallMap } from './components/HallMap/InteractiveHallMap';
import { LiveMonitoringView } from './components/LiveMonitoring/LiveMonitoringView';
import { AlertList } from './components/AlertPanel/AlertList';
import { EvidenceViewer } from './components/EvidenceViewer/EvidenceViewer';
import { BehaviourTimeline } from './pages/BehaviourTimeline';
import { GroupGraphViewer } from './components/GroupGraph/GroupGraphViewer';
import { CameraCoverageViewer } from './components/CameraStatus/CameraCoverageViewer';
import { PrivacyDiagram } from './components/PrivacyStatus/PrivacyDiagram';
import { SystemStatusViewer } from './components/SystemStatus/SystemStatusViewer';
import { ReportsPage } from './pages/ReportsPage';

import type { Seat, Alert, NormalizedEvent } from './types';
import { fetchAlerts, fetchEvents, connectWebSocket, controlSimulation, triggerSimStage } from './services/api';

export function App() {
  const [viewMode, setViewMode] = useState<'landing' | 'auth' | 'app'>('landing');
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [isNavCollapsed, setIsNavCollapsed] = useState<boolean>(false);
  const [currentStage, setCurrentStage] = useState<number>(0);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [events, setEvents] = useState<NormalizedEvent[]>([]);
  const [resetCounter, setResetCounter] = useState<number>(0);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [livePoses, setLivePoses] = useState<Record<string, any>>({});

  const loadInitialData = async () => {
    try {
      const alertData = await fetchAlerts();
      setAlerts(alertData);
      if (alertData.length > 0) {
        setSelectedAlertId((prev) => prev || alertData[0].id);
      }

      const eventData = await fetchEvents(30);
      setEvents(eventData);

      // Generate 120 seat grid (Rows A to F, 20 seats per row)
      const generatedSeats: Seat[] = [];
      const rows = ['A', 'B', 'C', 'D', 'E', 'F'];
      rows.forEach((r) => {
        for (let c = 1; c <= 20; c++) {
          const seatLabel = `${r}${c}`;
          let visStatus: 'GOOD' | 'PARTIAL' | 'POOR' | 'BLIND_SPOT' = 'GOOD';
          let visScore = 0.92;

          if (seatLabel === 'B4') {
            visStatus = 'POOR';
            visScore = 0.42;
          } else if (['B3', 'C7', 'E12'].includes(seatLabel)) {
            visStatus = 'PARTIAL';
            visScore = 0.68;
          } else if (seatLabel === 'D8') {
            visStatus = 'BLIND_SPOT';
            visScore = 0.18;
          }

          generatedSeats.push({
            id: `SEAT_${seatLabel}`,
            exam_id: 'EXAM_001',
            seat_label: seatLabel,
            row: r,
            column: c,
            visibility_status: visStatus,
            visibility_score: visScore,
          });
        }
      });
      setSeats(generatedSeats);
    } catch (err) {
      console.error('Failed to load initial data', err);
    }
  };

  useEffect(() => {
    loadInitialData();

    const disconnectWS = connectWebSocket((wsMsg) => {
      if (wsMsg.type === 'STAGE_UPDATE') {
        setCurrentStage(wsMsg.stage);
        if (wsMsg.alerts) {
          setAlerts(wsMsg.alerts);
          if (wsMsg.alerts.length > 0 && !selectedAlertId) {
            setSelectedAlertId(wsMsg.alerts[0].id);
          }
        }
        if (wsMsg.events) {
          setEvents(wsMsg.events);
        }
      } else if (wsMsg.type === 'ALERT_UPDATE') {
        if (wsMsg.alert) {
          setAlerts((prev) => {
            const idx = prev.findIndex((a) => a.id === wsMsg.alert.id);
            if (idx >= 0) {
              const copy = [...prev];
              copy[idx] = wsMsg.alert;
              return copy;
            }
            return [wsMsg.alert, ...prev];
          });
        }
      } else if (wsMsg.type === 'EVENT_NORMALIZED') {
        if (wsMsg.event) {
          setEvents((prev) => [wsMsg.event, ...prev].slice(0, 50));
        }
      } else if (wsMsg.type === 'POSE_UPDATE') {
        if (wsMsg.poses) {
          setLivePoses(wsMsg.poses);
        }
      }
    });

    return () => disconnectWS();
  }, []);

  const activeAlertsCount = alerts.filter((a) => a.status === 'ACTIVE').length;

  // 1. Landing Page
  if (viewMode === 'landing') {
    return (
      <LandingPage
        onLaunchConsole={() => {
          setViewMode('auth');
        }}
      />
    );
  }

  // 2. Auth Page
  if (viewMode === 'auth' || !isAuthenticated) {
    return (
      <AuthPage
        onLogin={() => {
          setIsAuthenticated(true);
          setActiveTab('dashboard');
          setViewMode('app');
        }}
      />
    );
  }

  // 3. Authenticated Industrial Monitoring Dashboard (LIGHT MODE BY DEFAULT)
  return (
    <div className="min-h-screen bg-[#EEF0ED] text-[#171C18] flex font-sans antialiased print:bg-white print:block print:min-h-0 print:p-0">
      {/* 1. Left Vertical Navigation */}
      <Navigation
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        alertBadgeCount={activeAlertsCount}
        isCollapsed={isNavCollapsed}
        setIsCollapsed={setIsNavCollapsed}
      />

      {/* 2. Main Workspace Layout (Full Height Without Top Bar) */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen transition-all duration-300 ease-in-out print:block print:w-full print:min-h-0 print:m-0 print:p-0">
        {/* Main Workspace Container */}
        <main key={resetCounter} className="flex-1 p-6 max-w-[1800px] w-full mx-auto space-y-6 transition-all duration-300 print:p-0 print:m-0 print:max-w-none print:w-full">
          {activeTab === 'dashboard' && (
            <Dashboard
              seats={seats}
              alerts={alerts}
              events={events}
              livePoses={livePoses}
              onReviewSubmitted={loadInitialData}
              onNavigateToTab={setActiveTab}
              onViewEvidence={(id) => {
                setSelectedAlertId(id);
                setActiveTab('evidence');
              }}
            />
          )}

          {activeTab === 'live' && (
            <LiveMonitoringView />
          )}

          {activeTab === 'evidence' && (
            <EvidenceViewer />
          )}

          {activeTab === 'alerts' && (
            <AlertList
              alerts={alerts}
              onReviewSubmitted={loadInitialData}
              onViewEvidence={(id) => {
                setSelectedAlertId(id);
                setActiveTab('evidence');
              }}
            />
          )}

          {activeTab === 'timeline' && (
            <BehaviourTimeline />
          )}

          {activeTab === 'group' && (
            <GroupGraphViewer />
          )}

          {activeTab === 'reports' && (
            <ReportsPage
              onNavigateToTimeline={() => setActiveTab('timeline')}
              onNavigateToEvidence={() => setActiveTab('evidence')}
            />
          )}

          {activeTab === 'coverage' && (
            <CameraCoverageViewer />
          )}

          {activeTab === 'privacy' && (
            <PrivacyDiagram />
          )}

          {activeTab === 'system' && (
            <SystemStatusViewer />
          )}
        </main>

        {/* Footer with Return to Landing button */}
        <footer className="border-t border-[#D5D8D3]/80 bg-[#E5E7E2]/85 backdrop-blur-md px-6 py-3 text-center text-xs text-[#3D4741] font-medium flex flex-wrap items-center justify-between gap-2 shadow-2xs print:hidden">
          <span>AI Examination Behaviour Monitoring Platform — Industrial Dashboard</span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setViewMode('landing')}
              className="text-[11px] font-bold text-[#FF7A2A] hover:underline cursor-pointer"
            >
              ← Back to Landing Page
            </button>
            <span className="glass-pill px-3 py-1 text-[11px] font-bold text-[#171C18] flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#718277]"></span>
              Identity Protection Engine Enforced (No Biometrics / Face ID)
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
