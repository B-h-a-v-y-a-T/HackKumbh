import React, { useState, useEffect, useCallback } from 'react';
import { FileText, AlertCircle, RefreshCw, Loader2 } from 'lucide-react';
import {
  fetchReportSessions,
  fetchReportSummary,
  getReportCSVDownloadUrl,
} from '../services/api';
import type { ReportSession, ReportSummary, ReportFilters as ReportFiltersType } from '../types/report';

import { ReportHeader } from '../components/Reports/ReportHeader';
import { ReportFilters } from '../components/Reports/ReportFilters';
import { ReportKPICards } from '../components/Reports/ReportKPICards';
import { RiskDistributionCard } from '../components/Reports/RiskDistributionCard';
import { RiskTimelineCard } from '../components/Reports/RiskTimelineCard';
import { BehaviourAnalysisCard } from '../components/Reports/BehaviourAnalysisCard';
import { ObjectAnalysisCard } from '../components/Reports/ObjectAnalysisCard';
import { GroupIntelligenceCard } from '../components/Reports/GroupIntelligenceCard';
import { TopFlaggedTracksTable } from '../components/Reports/TopFlaggedTracksTable';
import { EventEvidenceTable } from '../components/Reports/EventEvidenceTable';
import { CameraHealthSummary } from '../components/Reports/CameraHealthSummary';
import { HumanReviewSummary } from '../components/Reports/HumanReviewSummary';
import { RetrospectiveVerificationCard } from '../components/Reports/RetrospectiveVerificationCard';
import { SystemPerformanceCard } from '../components/Reports/SystemPerformanceCard';
import { PrivacyTrustCard } from '../components/Reports/PrivacyTrustCard';
import { DeterministicInsightsCard } from '../components/Reports/DeterministicInsightsCard';
import { ReportPrintView } from '../components/Reports/ReportPrintView';

interface ReportsPageProps {
  onNavigateToTimeline?: (trackId?: string) => void;
  onNavigateToEvidence?: (trackId?: string) => void;
}

const defaultFilters: ReportFiltersType = {
  risk_level: 'ALL',
  event_type: 'ALL',
  camera_id: 'ALL',
  seat_id: 'ALL',
  track_id: 'ALL',
  review_status: 'ALL',
};

export const ReportsPage: React.FC<ReportsPageProps> = ({
  onNavigateToTimeline,
  onNavigateToEvidence,
}) => {
  const [sessions, setSessions] = useState<ReportSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>('LIVE');
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [filters, setFilters] = useState<ReportFiltersType>(defaultFilters);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState<boolean>(false);

  // 1. Fetch available sessions on mount
  useEffect(() => {
    let isMounted = true;
    async function loadSessions() {
      try {
        const res = await fetchReportSessions();
        if (isMounted && res.sessions && res.sessions.length > 0) {
          setSessions(res.sessions);
          // Default to first session or keep current
          if (!selectedSessionId || selectedSessionId === 'LIVE') {
            setSelectedSessionId(res.sessions[0].session_id);
          }
        }
      } catch (err: any) {
        console.error('Failed to load report sessions:', err);
      }
    }
    loadSessions();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch session report summary whenever selected session or filters change
  const loadReport = useCallback(async () => {
    if (!selectedSessionId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchReportSummary(selectedSessionId, filters);
      setSummary(data);
    } catch (err: any) {
      console.error('Failed to load report summary:', err);
      setError(err.message || 'Failed to load report summary data.');
    } finally {
      setIsLoading(false);
    }
  }, [selectedSessionId, filters]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  // Handlers
  const handleFilterChange = (key: keyof ReportFiltersType, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleResetFilters = () => {
    setFilters(defaultFilters);
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadCSV = () => {
    const url = getReportCSVDownloadUrl(selectedSessionId, filters);
    window.open(url, '_blank');
  };

  const handleOpenTimeline = (trackId: string) => {
    if (onNavigateToTimeline) {
      onNavigateToTimeline(trackId);
    }
  };

  // Derive unique tracks and seats for dropdown filters
  const availableTracks = summary
    ? Array.from(new Set(summary.events_table.map((e) => e.track_id).filter(Boolean))).sort()
    : [];
  const availableSeats = summary
    ? Array.from(new Set(summary.events_table.map((e) => e.seat_id).filter(Boolean))).sort()
    : [];

  const hasActiveFilters =
    filters.risk_level !== 'ALL' ||
    filters.event_type !== 'ALL' ||
    filters.review_status !== 'ALL' ||
    filters.track_id !== 'ALL' ||
    filters.seat_id !== 'ALL';

  return (
    <div className="space-y-6 pb-12">
      {/* Printable Report View (Visible ONLY during window.print()) */}
      {summary && <ReportPrintView summary={summary} />}

      {/* Screen Interactive View (Hidden during print) */}
      <div className="print:hidden space-y-6">
        {/* Header Section */}
        <ReportHeader
          sessions={sessions}
          selectedSessionId={selectedSessionId}
          onSelectSession={(id) => {
            setSelectedSessionId(id);
            setFilters(defaultFilters);
          }}
          summary={summary}
          isLoading={isLoading}
          onRefresh={loadReport}
          onPrint={handlePrint}
          onDownloadCSV={handleDownloadCSV}
          showFilters={showFilters}
          onToggleFilters={() => setShowFilters((prev) => !prev)}
          hasActiveFilters={hasActiveFilters}
        />

        {/* Filter Drawer / Bar */}
        {showFilters && (
          <ReportFilters
            filters={filters}
            onChangeFilter={handleFilterChange}
            onResetFilters={handleResetFilters}
            availableTracks={availableTracks}
            availableSeats={availableSeats}
          />
        )}

        {/* Error State */}
        {error && (
          <div className="bg-[#FEF2F2] border border-[#FCA5A5] rounded-2xl p-4 flex items-center justify-between text-xs text-[#DC2626]">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span className="font-bold">{error}</span>
            </div>
            <button
              onClick={loadReport}
              className="px-3 py-1 bg-white border border-[#FCA5A5] rounded-lg text-xs font-bold hover:bg-[#FEE2E2] cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading Spinner */}
        {isLoading && !summary && (
          <div className="py-24 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-[#FF7A2A] animate-spin" />
            <span className="text-xs font-bold text-[#5E6962]">
              Computing deterministic session analytics & evidence aggregations…
            </span>
          </div>
        )}

        {/* Main Content Dashboard */}
        {summary && (
          <>
            {/* 1. KPIs & Executive Status */}
            <ReportKPICards
              kpis={summary.kpis}
              onFilterByFlagged={() => handleFilterChange('risk_level', 'HIGH')}
              onFilterByObjects={() => handleFilterChange('event_type', 'PHONE')}
              onFilterByGroups={() => handleFilterChange('event_type', 'GROUP')}
            />

            {/* 2. Charts Row: Risk Distribution & Risk Timeline */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <RiskDistributionCard
                distribution={summary.risk_distribution}
                selectedLevel={filters.risk_level}
                onSelectLevel={(lvl) => handleFilterChange('risk_level', lvl)}
              />
              <RiskTimelineCard
                timeline={summary.risk_timeline}
                onSelectTimeWindow={(start, end) => {
                  handleFilterChange('start_time', start);
                  handleFilterChange('end_time', end);
                }}
              />
            </div>

            {/* 3. Deep Analysis Row: Behavioural Dynamics & Contraband Objects */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <BehaviourAnalysisCard
                eventCounts={summary.behaviour_analysis.event_counts}
                combinations={summary.behaviour_analysis.combinations}
                totalCount={summary.behaviour_analysis.total_count}
                onSelectEventType={(type) => handleFilterChange('event_type', type)}
              />
              <ObjectAnalysisCard
                eventCounts={summary.object_analysis.event_counts}
                confidences={summary.object_analysis.confidences}
                totalCount={summary.object_analysis.total_count}
              />
            </div>

            {/* 4. Student Groups & Spatial Intelligence */}
            <GroupIntelligenceCard
              groups={summary.group_intelligence.groups}
              onSelectGroup={() => handleFilterChange('event_type', 'GROUP')}
            />

            {/* 5. Top Flagged Anonymous Tracks */}
            <TopFlaggedTracksTable
              tracks={summary.top_flagged_tracks}
              onOpenTimeline={handleOpenTimeline}
            />

            {/* 6. Canonical Event Evidence Log Table */}
            <EventEvidenceTable
              events={summary.events_table}
              onOpenTimeline={handleOpenTimeline}
            />

            {/* 7. Camera Health & Human Review Summary */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <CameraHealthSummary cameras={summary.camera_health} />
              <HumanReviewSummary reviewData={summary.human_review_summary} />
            </div>

            {/* 8. Retrospective 15-Minute Verification */}
            <RetrospectiveVerificationCard retroData={summary.retrospective_summary} />

            {/* 9. System Metrics & Privacy Guarantee */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SystemPerformanceCard metrics={summary.system_metrics} />
              <PrivacyTrustCard privacy={summary.privacy_status} />
            </div>

            {/* 10. Key Insights & Rule-Based Recommendations */}
            <DeterministicInsightsCard insights={summary.insights} />
          </>
        )}
      </div>
    </div>
  );
};
