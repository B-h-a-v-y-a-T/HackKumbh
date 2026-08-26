import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, XCircle, HelpCircle, FileSearch } from 'lucide-react';
import type { Alert, DecisionType } from '../../types';
import { submitReview } from '../../services/api';

interface AlertListProps {
  alerts: Alert[];
  onReviewSubmitted: () => void;
  onViewEvidence: (alertId: string) => void;
}

export const AlertList: React.FC<AlertListProps> = ({
  alerts,
  onReviewSubmitted,
  onViewEvidence
}) => {
  const [filterPriority, setFilterPriority] = useState<string>('ALL');
  const [filterStatus, setFilterStatus] = useState<string>('ACTIVE');
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const getDecision = (alert: Alert) => {
    if (alert.latest_review?.decision) return alert.latest_review.decision;
    if (alert.status === 'CONFIRMED_FOR_REVIEW' || alert.status === 'CONFIRMED') return 'CONFIRM_FOR_REVIEW';
    if (alert.status === 'UNSURE' || alert.status === 'NEEDS_FURTHER_REVIEW') return 'UNSURE';
    if (alert.status === 'DISMISS' || alert.status === 'DISMISSED') return 'DISMISS';
    return null;
  };

  const isActive = (alert: Alert) => {
    const d = getDecision(alert);
    return !d || alert.status === 'UNVERIFIED' || alert.status === 'IN_REVIEW';
  };

  const filteredAlerts = alerts.filter((alert) => {
    if (filterPriority !== 'ALL' && alert.priority !== filterPriority) return false;
    const d = getDecision(alert);
    if (filterStatus === 'ACTIVE') return isActive(alert);
    if (filterStatus === 'CONFIRMED') return d === 'CONFIRM_FOR_REVIEW';
    if (filterStatus === 'UNSURE') return d === 'UNSURE';
    if (filterStatus === 'DISMISSED') return d === 'DISMISS';
    return true;
  });

  const handleDecision = async (alertId: string, decision: DecisionType) => {
    try {
      setSubmittingId(alertId);
      await submitReview(alertId, decision, `Invigilator selected ${decision}`);
      onReviewSubmitted();
    } catch (err) {
      console.error('Failed to submit review', err);
    } finally {
      setSubmittingId(null);
    }
  };

  return (
    <div className="glass-panel-white p-6 space-y-6">
      {/* Header & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#D9DDD8] pb-4">
        <div>
          <h2 className="text-base font-extrabold text-[#171C18] flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[#FF7A2A]" />
            RISK REVIEW QUEUE (HUMAN-IN-THE-LOOP)
          </h2>
          <p className="text-xs text-[#3D4741]">
            Invigilators review flagged behavioral posture alerts to confirm, query, or dismiss events.
          </p>
        </div>

        {/* Priority Filter */}
        <div className="flex items-center space-x-1 text-xs">
          <span className="text-[#3D4741] font-bold mr-1.5">Priority:</span>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((p) => (
            <button
              key={p}
              onClick={() => setFilterPriority(p)}
              className={`px-3 py-1 rounded-lg font-bold transition-all ${
                filterPriority === p
                  ? 'bg-[#171C18] text-white shadow-2xs'
                  : 'glass-control text-[#3D4741] hover:text-[#171C18]'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Review Status Tabs (Segmented Glass Control) */}
      <div className="glass-control p-1.5 text-xs flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => setFilterStatus('ACTIVE')}
            className={`px-3.5 py-1.5 rounded-lg font-bold transition-all ${
              filterStatus === 'ACTIVE'
                ? 'bg-white text-[#171C18] shadow-2xs border border-[#D9DDD8]'
                : 'text-[#3D4741] hover:text-[#171C18]'
            }`}
          >
            Pending Review Queue ({alerts.filter(isActive).length})
          </button>
          <button
            onClick={() => setFilterStatus('CONFIRMED')}
            className={`px-3.5 py-1.5 rounded-lg font-bold transition-all ${
              filterStatus === 'CONFIRMED'
                ? 'glass-card-orange text-[#171C18]'
                : 'text-[#3D4741] hover:text-[#171C18]'
            }`}
          >
            Confirmed for Review ({alerts.filter((a) => getDecision(a) === 'CONFIRM_FOR_REVIEW').length})
          </button>
          <button
            onClick={() => setFilterStatus('UNSURE')}
            className={`px-3.5 py-1.5 rounded-lg font-bold transition-all ${
              filterStatus === 'UNSURE'
                ? 'glass-card text-[#171C18]'
                : 'text-[#3D4741] hover:text-[#171C18]'
            }`}
          >
            Flagged Unsure ({alerts.filter((a) => getDecision(a) === 'UNSURE').length})
          </button>
          <button
            onClick={() => setFilterStatus('DISMISSED')}
            className={`px-3.5 py-1.5 rounded-lg font-bold transition-all ${
              filterStatus === 'DISMISSED'
                ? 'glass-card-sage text-[#171C18]'
                : 'text-[#3D4741] hover:text-[#171C18]'
            }`}
          >
            Dismissed ({alerts.filter((a) => getDecision(a) === 'DISMISS').length})
          </button>
        </div>
      </div>

      {/* Alert List Items */}
      {filteredAlerts.length === 0 ? (
        <div className="text-center py-10 text-[#5E6962] text-xs">
          No risk alerts match the selected status or priority filter.
        </div>
      ) : (
        <div className="space-y-4">
          {filteredAlerts.map((alert) => {
            const isCritical = alert.priority === 'CRITICAL' || alert.priority === 'HIGH';
            const isSubmitting = submittingId === alert.id;
            const eventType = alert.observed_behaviours?.[0] || alert.object_detected || 'BEHAVIOUR_RISK';
            const explainabilityText = alert.explainability?.summary || 'Gaze angle deviation and hand posture anomaly detected by spatial analytics.';

            return (
              <div
                key={alert.id}
                className={`p-5 space-y-4 transition-all shadow-2xs ${
                  isCritical
                    ? 'glass-card-orange border-l-4 border-l-[#FF7A2A]'
                    : 'glass-card hover:border-[#718277]'
                }`}
              >
                {/* Item Top Row */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#D9DDD8]/80 pb-3">
                  <div className="flex items-center space-x-3">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-extrabold ${
                      isCritical
                        ? 'bg-[#FF7A2A] text-white'
                        : 'glass-pill text-[#171C18]'
                    }`}>
                      {alert.priority} (Risk: {alert.risk_score})
                    </span>
                    <span className="font-extrabold text-[#171C18] text-sm">
                      {eventType}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2 text-xs">
                    <span className="glass-pill px-2.5 py-0.5 font-bold text-[#171C18]">
                      Seat {alert.seat_id || 'B4'}
                    </span>
                    <span className="text-[#5E6962] text-[11px]">Track {alert.track_id}</span>
                  </div>
                </div>

                {/* Event Explanation & Details */}
                <p className="text-xs text-[#3D4741] leading-relaxed font-medium">
                  {explainabilityText}
                </p>

                {/* Evidence Clip & Decision Controls Row */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[#D9DDD8]/80">
                  <button
                    onClick={() => onViewEvidence(alert.id)}
                    className="text-xs font-bold text-[#171C18] glass-control px-3.5 py-1.5 transition-all flex items-center gap-1.5 shadow-2xs hover:bg-[#B9C4BC]/50"
                  >
                    <FileSearch className="w-3.5 h-3.5 text-[#718277]" />
                    <span>View Evidence Clip</span>
                  </button>

                  {/* Decision Action Buttons */}
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <button
                      onClick={() => handleDecision(alert.id, 'CONFIRM_FOR_REVIEW')}
                      disabled={isSubmitting}
                      className="bg-[#FF7A2A] hover:bg-[#E86518] text-white font-extrabold px-3.5 py-1.5 rounded-xl flex items-center gap-1.5 transition-all shadow-xs disabled:opacity-50"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Confirm for Review</span>
                    </button>

                    <button
                      onClick={() => handleDecision(alert.id, 'UNSURE')}
                      disabled={isSubmitting}
                      className="glass-card hover:bg-[#F6B28A]/40 text-[#171C18] font-bold px-3 py-1.5 rounded-xl flex items-center gap-1.5 transition-all disabled:opacity-50"
                    >
                      <HelpCircle className="w-3.5 h-3.5 text-[#718277]" />
                      <span>Flag Unsure</span>
                    </button>

                    <button
                      onClick={() => handleDecision(alert.id, 'DISMISS')}
                      disabled={isSubmitting}
                      className="glass-card-sage hover:bg-[#A3B5A8]/50 text-[#171C18] font-bold px-3 py-1.5 rounded-xl flex items-center gap-1.5 transition-all disabled:opacity-50"
                    >
                      <XCircle className="w-3.5 h-3.5 text-[#718277]" />
                      <span>Dismiss</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
