class RiskService:
    @staticmethod
    def calculate_priority(risk_score: int, confidence: float, visibility_context: float) -> str:
        """
        Calculates alert priority: LOW, MEDIUM, HIGH, CRITICAL.
        If visibility is very low (< 0.50), caps priority at MEDIUM/LOW and flags reduced confidence.
        """
        # Effective score adjusted for low visibility
        effective_confidence = confidence * (visibility_context if visibility_context < 0.60 else 1.0)
        
        if visibility_context < 0.50:
            # Low visibility penalty
            if risk_score >= 85 and effective_confidence >= 0.70:
                return "HIGH"
            elif risk_score >= 60:
                return "MEDIUM"
            else:
                return "LOW"

        if risk_score >= 85 and effective_confidence >= 0.70:
            return "CRITICAL"
        elif risk_score >= 70 and effective_confidence >= 0.60:
            return "HIGH"
        elif risk_score >= 40:
            return "MEDIUM"
        else:
            return "LOW"
