import React from 'react';
import {
  LayoutDashboard,
  Grid,
  AlertTriangle,
  FileSearch,
  FileText,
  Clock,
  Users,
  Eye,
  ShieldCheck,
  Cpu,
  Activity,
  ChevronRight,
  ChevronLeft
} from 'lucide-react';

export type TabType = 
  | 'dashboard'
  | 'live'
  | 'alerts'
  | 'evidence'
  | 'timeline'
  | 'group'
  | 'reports'
  | 'coverage'
  | 'privacy'
  | 'system';

interface NavigationProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  alertBadgeCount: number;
  isCollapsed?: boolean;
  setIsCollapsed?: (collapsed: boolean) => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  setActiveTab,
  alertBadgeCount,
  isCollapsed = false,
  setIsCollapsed
}) => {
  const tabs: { id: TabType; label: string; icon: React.FC<{ className?: string }>; badge?: number }[] = [
    { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
    { id: 'live', label: 'Live Monitoring', icon: Grid },
    { id: 'evidence', label: 'Evidence Review', icon: FileSearch },
    { id: 'alerts', label: 'Risk Events', icon: AlertTriangle, badge: alertBadgeCount },
    { id: 'timeline', label: 'Timeline / Replay', icon: Clock },
    { id: 'group', label: 'Student Groups', icon: Users },
    { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'coverage', label: 'Camera Health', icon: Eye },
    { id: 'privacy', label: 'Privacy Status', icon: ShieldCheck },
    { id: 'system', label: 'System Status', icon: Cpu },
  ];

  return (
    <aside
      className={`glass-sidebar print:hidden flex flex-col justify-between shrink-0 min-h-screen select-none transition-all duration-300 ease-in-out sticky top-0 z-40 ${
        isCollapsed ? 'w-16' : 'w-16 lg:w-60'
      }`}
    >
      {/* Top Logo & App Title Section */}
      <div>
        <div className="h-16 flex items-center px-4 border-b border-[#D5D8D3]/80 justify-between bg-[#E1E4DF]/40">
          <div className="flex items-center gap-3 overflow-hidden">
            <img src="/logo.png" alt="CopyCop Logo" className="w-9 h-9 object-contain shrink-0 rounded-lg bg-white/80 p-0.5 shadow-xs" />
            {!isCollapsed && (
              <div className="hidden lg:block overflow-hidden">
                <h1 className="font-black text-base leading-tight tracking-tight truncate">
                  <span className="text-[#FF7A2A]">Copy</span>
                  <span className="text-[#171C18]">Cop</span>
                </h1>
                <p className="text-[10px] text-[#5E6962] truncate font-bold uppercase tracking-wider">
                  AI Examination Monitor
                </p>
              </div>
            )}
          </div>

          {setIsCollapsed && (
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="hidden lg:flex p-1 text-[#5E6962] hover:text-[#171C18] hover:bg-white/60 rounded-lg transition-colors cursor-pointer"
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="p-2.5 space-y-1.5 mt-3">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                title={tab.label}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all group relative cursor-pointer ${
                  isActive
                    ? 'glass-card-orange-light text-[#171C18] font-extrabold border-l-4 border-[#FF7A2A] shadow-xs'
                    : 'text-[#3D4741] hover:text-[#171C18] hover:bg-[#D9DDD8]/60'
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 transition-colors ${isActive ? 'text-[#FF7A2A]' : 'text-[#5E6962] group-hover:text-[#171C18]'}`} />
                {!isCollapsed && <span className="hidden lg:inline truncate">{tab.label}</span>}

                {/* Badge Counter */}
                {tab.badge !== undefined && tab.badge > 0 && (
                  <span className={`ml-auto px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                    isActive
                      ? 'bg-[#FF7A2A] text-white'
                      : 'bg-[#F6B28A] text-[#171C18]'
                  }`}>
                    {tab.badge}
                  </span>
                )}

                {/* Tooltip for narrow view */}
                {isCollapsed && (
                  <div className="absolute left-full ml-2 px-2.5 py-1 bg-[#171C18] text-white text-[11px] rounded-md shadow-lg pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-50 whitespace-nowrap">
                    {tab.label}
                  </div>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Privacy Footer Indicator */}
      <div className="p-3 border-t border-[#D5D8D3]/80">
        {!isCollapsed ? (
          <div className="hidden lg:flex items-center gap-2 px-3 py-2 bg-white/70 border border-[#D5D8D3] rounded-xl text-[11px] text-[#3D4741] shadow-2xs">
            <ShieldCheck className="w-4 h-4 text-[#FF7A2A] shrink-0" />
            <div className="leading-tight">
              <span className="font-bold block text-[#171C18]">Privacy Protected</span>
              <span className="text-[10px] text-[#5E6962]">Anonymous Track IDs</span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center py-2" title="Anonymous Tracking Active">
            <ShieldCheck className="w-5 h-5 text-[#FF7A2A]" />
          </div>
        )}
      </div>
    </aside>
  );
};
