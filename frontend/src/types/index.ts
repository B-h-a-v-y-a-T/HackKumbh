export interface Exam {
  id: string;
  name: string;
  start_time: string;
  end_time?: string;
  status: string;
  total_seats: number;
  total_cameras: number;
  description?: string;
}

export interface Seat {
  id: string;
  exam_id: string;
  seat_label: string;
  row: string;
  column: number;
  visibility_status: 'GOOD' | 'PARTIAL' | 'POOR' | 'BLIND_SPOT';
  visibility_score: number;
  camera_id?: string;
  current_track_id?: string;
  risk_score?: number;
}

export interface AlertExplainability {
  summary: string;
  observed_points: string[];
  confidence_score: number;
  reduced_confidence_reasons: string[];
  recommendation: string;
}

export type DecisionType = 'CONFIRM_FOR_REVIEW' | 'DISMISS' | 'UNSURE' | string;

export interface HumanReviewData {
  id: string;
  decision: DecisionType;
  notes: string;
  reviewer_id: string;
  reviewed_at: string;
}

export interface Alert {
  id: string;
  exam_id: string;
  track_id: string;
  seat_id: string;
  risk_score: number;
  peak_risk: number;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'UNVERIFIED' | 'IN_REVIEW' | 'CONFIRMED' | 'CONFIRMED_FOR_REVIEW' | 'DISMISSED' | 'NEEDS_FURTHER_REVIEW' | 'UNSURE' | string;
  confidence: number;
  observed_behaviours: string[];
  duration_sec: number;
  low_visibility_flag: boolean;
  verification_status: 'LIVE_DETECTION' | 'SECOND_PASS_CONFIRMED' | 'SECOND_PASS_DISPROVED' | string;
  group_id?: string;
  object_detected?: string;
  explainability?: AlertExplainability;
  latest_review?: HumanReviewData;
  created_at: string;
  updated_at: string;
}

export interface NormalizedEvent {
  event_id: string;
  source: 'PART_1' | 'PART_2' | 'PART_3' | 'MOCK' | 'SYSTEM';
  timestamp: string;
  exam_id: string;
  camera_id?: string;
  track_ids: string[];
  seat_ids: string[];
  event_type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence: number;
  visibility_context: number;
  metadata: Record<string, any>;
}

export interface ProblematicSeat {
  seat_id: string;
  status: string;
  score: number;
  recommendation: string;
}

export interface CoverageReport {
  exam_id: string;
  total_seats: number;
  reliable_coverage_pct: number;
  partial_coverage_pct: number;
  blind_spots_pct: number;
  good_seats_count: number;
  partial_seats_count: number;
  poor_seats_count: number;
  blind_spots_count: number;
  problematic_seats: ProblematicSeat[];
}

export interface GroupInteraction {
  id: string;
  group_id: string;
  exam_id: string;
  member_tracks: string[];
  group_risk: number;
  pattern_description: string;
  window_start: string;
  window_end: string;
}

export interface SystemStatus {
  system_health: string;
  active_exam_id: string;
  timestamp: string;
  ai_modules: {
    part1_perception: { status: string; mode: string; events_ingested: number; last_active: string };
    part2_behaviour: { status: string; mode: string; events_ingested: number; last_active: string };
    part3_verification: { status: string; mode: string; events_ingested: number; last_active: string };
  };
  websocket_channel: string;
  api_latency_ms: number;
}
