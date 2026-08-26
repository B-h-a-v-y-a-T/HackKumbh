from typing import List, Dict, Any

class ExplainabilityService:
    @staticmethod
    def generate_explanation(
        track_id: str,
        seat_id: str,
        risk_score: int,
        observed_behaviours: List[str],
        duration_sec: float,
        visibility_score: float,
        confidence: float,
        group_id: str = None,
        group_members: List[str] = None,
        object_detected: str = None,
        verification_status: str = "LIVE_DETECTION"
    ) -> Dict[str, Any]:
        """
        Generates a human-readable, transparent explanation for why an event was flagged.
        Never declares student cheated. Focuses purely on observed behavioural metrics.
        """
        observed_points = []
        
        # 1. Primary behavioural patterns
        for behaviour in observed_behaviours:
            b_upper = behaviour.upper()
            if "NEIGHBOUR_GAZE" in b_upper:
                observed_points.append(f"Track {track_id} repeatedly oriented head toward neighbouring seats.")
            elif "TORSO_ROTATE" in b_upper:
                observed_points.append("Sustained torso rotation observed away from desk center.")
            elif "UNUSUAL_HAND_MOVEMENT" in b_upper or "HANDS_HIDDEN" in b_upper:
                observed_points.append("Unusual hand movement pattern detected near desk edge or lap.")
            elif "PHONE" in b_upper:
                observed_points.append("Hand-object proximity pattern resembling device interaction.")
            elif "HEAD_TURNING" in b_upper:
                observed_points.append("Frequent rapid head angle turn relative to seat baseline.")

        if duration_sec > 0:
            observed_points.append(f"The behavioural pattern continued continuously for {duration_sec:.1f} seconds.")

        if group_id and group_members:
            members_str = ", ".join([m for m in group_members if m != track_id])
            observed_points.append(f"Correlated temporal movement detected with neighbouring track(s) {members_str} (Group {group_id}).")

        if verification_status == "SECOND_PASS_CONFIRMED":
            if object_detected and object_detected.upper() != "NONE":
                observed_points.append(f"Heavy second-pass verification confirmed physical object interaction: {object_detected.upper()}.")
            else:
                observed_points.append("Heavy second-pass verification confirmed high-confidence behavioural anomaly.")

        # 2. Reduced confidence factors
        reduced_factors = []
        if visibility_score < 0.50:
            reduced_factors.append(f"Low camera visibility score ({int(visibility_score * 100)}%). Confidence penalized.")
        elif visibility_score < 0.70:
            reduced_factors.append(f"Partial camera occlusion detected ({int(visibility_score * 100)}% clear view).")

        if confidence < 0.75:
            reduced_factors.append(f"Model perception confidence is lower than optimal standard ({int(confidence * 100)}%).")

        if verification_status == "SECOND_PASS_DISPROVED":
            reduced_factors.append("Second-pass heavy verifier disproved the initial live alert threshold.")

        # 3. Recommendation
        if risk_score >= 80 and verification_status == "SECOND_PASS_CONFIRMED":
            recommendation = "Immediate human invigilator review recommended. Physical verification of desk area advised."
        elif risk_score >= 70:
            recommendation = "Human invigilator review recommended. Monitor seat area in live view."
        elif visibility_score < 0.50:
            recommendation = "Low visibility — behaviour confidence reduced. Consider adjusting camera angle or repositioning seat."
        else:
            recommendation = "Routine observation advised. Maintain standard invigilator monitoring."

        summary = (
            f"Unusual behavioural pattern flagged for Track {track_id} at Seat {seat_id or 'Unassigned'}. "
            f"Current risk score: {risk_score}/100 based on {len(observed_behaviours)} registered signal(s)."
        )

        return {
            "summary": summary,
            "observed_points": observed_points,
            "confidence_score": round(confidence, 2),
            "reduced_confidence_reasons": reduced_factors,
            "recommendation": recommendation
        }
