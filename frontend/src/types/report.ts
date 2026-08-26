export interface ReportSession {
  session_id: string;
  name: string;
  source_type: 'LIVE_STREAM' | 'UPLOADED_VIDEO';
  source_label: string;
  filename?: string;
  created_at: string;
  duration_sec?: number;
  duration_formatted?: string;
  total_cameras?: number;
  has_cached_analysis?: boolean;
  is_live: boolean;
}

export interface ReportKPIs {
  tracks_monitored: number;
  tracks_flagged: number;
  total_behaviour_events: number;
  total_object_events: number;
  total_group_events: number;
  total_reviews: number;
  confirmed_reviews: number;
  dismissed_reviews: number;
  pending_reviews: number;
  confirmation_rate_pct: number;
  dismissal_rate_pct: number;
  executive_status: 'NORMAL' | 'ATTENTION_REQUIRED' | 'HIGH_ATTENTION';
  executive_status_label: string;
  executive_status_description: string;
}

export interface RiskDistributionItem {
  level: 'LOW' | 'WATCH' | 'HIGH' | 'CRITICAL';
  label: string;
  count: number;
  percentage: number;
  color: string;
}

export interface RiskTimelineSlice {
  bin_index: number;
  start_sec: number;
  end_sec: number;
  label: string;
  avg_risk: number;
  peak_risk: number;
  behaviour_count: number;
  object_count: number;
  group_count: number;
  total_events: number;
}

export interface BehaviourCountItem {
  event_type: string;
  count: number;
  percentage: number;
}

export interface BehaviourCombinationItem {
  combination: string;
  count: number;
  significance: string;
}

export interface ObjectCountItem {
  object_class: string;
  count: number;
  percentage: number;
}

export interface ObjectConfidenceItem {
  object_class: string;
  avg_confidence_pct: number;
  samples_count: number;
}

export interface GroupNode {
  id: string;
  label: string;
  is_leader?: boolean;
}

export interface GroupEdge {
  source: string;
  target: string;
  weight: number;
}

export interface GroupSummaryItem {
  group_id: string;
  tracks: string[];
  tracks_formatted: string;
  events_count: number;
  peak_risk: number;
  main_pattern: string;
  review_status: string;
  nodes: GroupNode[];
  edges: GroupEdge[];
}

export interface TopFlaggedTrack {
  rank: number;
  track_id: string;
  seat_id: string;
  final_risk: number;
  peak_risk: number;
  priority: string;
  status: string;
  review_status: string;
  behaviour_events_count: number;
  object_events_count: number;
  group_events_count: number;
  observed_behaviours: string[];
  object_detected?: string | null;
}

export interface EventEvidenceRow {
  event_id: string;
  timestamp: string | number;
  time_sec?: number;
  time_str?: string;
  camera_id?: string;
  track_id: string;
  track_ids?: string[];
  seat_id: string;
  seat_ids?: string[];
  event_type: string;
  severity: string;
  confidence: number;
  duration_sec?: number;
  source: string;
  risk_score: number;
  object_evidence?: any[];
  reasons?: string[];
  review_status: string;
}

export interface TopRiskPeriod {
  time_range: string;
  activity_level: string;
  events_count: number;
  average_risk: number;
  reasons: string[];
}

export interface CameraHealthItem {
  camera_id: string;
  coverage_pct: number;
  visibility_score: number;
  status: 'GOOD' | 'WARNING' | 'CRITICAL';
  affected_seats_count: number;
  partial_seats: string[];
  blind_spots: string[];
  fps: number;
  dropped_frames: number;
  framing_recommendation: string;
}

export interface HumanReviewSummaryData {
  total_alerts: number;
  reviewed: number;
  pending: number;
  confirmed: number;
  dismissed: number;
  confirmation_rate_pct: number;
  dismissal_rate_pct: number;
  most_dismissed_types: Array<{
    event_type: string;
    dismissed_count: number;
    reason: string;
  }>;
}

export interface RetrospectiveSummaryData {
  live_alerts_count: number;
  strengthened_count: number;
  weakened_count: number;
  new_retrospective_events_count: number;
  verification_models: string[];
}

export interface SystemMetricsData {
  average_fps: number;
  peak_fps: number;
  average_latency_ms: number;
  cameras_active: number;
  frames_processed: number;
  frames_dropped: number;
  gpu_device: string;
  cpu_utilization_pct: number;
  memory_usage_mb: number;
}

export interface PrivacyStatusData {
  privacy_mode: string;
  identity_masking: string;
  face_recognition: string;
  biometric_storage: string;
  anonymous_tracking: string;
  human_review_policy: string;
  compliance_declaration: string;
}

export interface ReportInsight {
  category: string;
  type: 'NORMAL' | 'INFO' | 'WARNING' | 'CRITICAL';
  text: string;
}

export interface ReportFilters {
  risk_level: string;
  event_type: string;
  camera_id: string;
  seat_id: string;
  track_id: string;
  review_status: string;
  start_time?: number;
  end_time?: number;
}

export interface ReportSummary {
  session_info: {
    session_id: string;
    name: string;
    exam_name: string;
    date: string;
    start_time: string;
    end_time: string;
    duration_sec: number;
    duration_formatted: string;
    total_cameras: number;
    analysis_source: string;
    source_type: string;
    generated_at: string;
  };
  filters_applied: ReportFilters;
  kpis: ReportKPIs;
  risk_distribution: RiskDistributionItem[];
  risk_timeline: RiskTimelineSlice[];
  behaviour_analysis: {
    event_counts: BehaviourCountItem[];
    combinations: BehaviourCombinationItem[];
    total_count: number;
  };
  object_analysis: {
    event_counts: ObjectCountItem[];
    confidences: ObjectConfidenceItem[];
    total_count: number;
  };
  group_intelligence: {
    groups: GroupSummaryItem[];
    total_groups: number;
  };
  top_flagged_tracks: TopFlaggedTrack[];
  events_table: EventEvidenceRow[];
  total_events_count: number;
  top_risk_periods: TopRiskPeriod[];
  camera_health: CameraHealthItem[];
  human_review_summary: HumanReviewSummaryData;
  retrospective_summary: RetrospectiveSummaryData;
  system_metrics: SystemMetricsData;
  privacy_status: PrivacyStatusData;
  insights: ReportInsight[];
}
