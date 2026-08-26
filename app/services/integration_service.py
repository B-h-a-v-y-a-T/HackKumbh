from datetime import datetime, timezone
from typing import Dict, Any

class IntegrationService:
    """
    Tracks connectivity and health status of AI Module integrations (Parts 1, 2, and 3).
    Allows system to report status cleanly if an AI module disconnects.
    """
    _status = {
        "part1": {"connected": True, "mode": "SIMULATED", "last_heartbeat": datetime.now(tz=timezone.utc).isoformat(), "events_processed": 0},
        "part2": {"connected": True, "mode": "SIMULATED", "last_heartbeat": datetime.now(tz=timezone.utc).isoformat(), "events_processed": 0},
        "part3": {"connected": True, "mode": "SIMULATED", "last_heartbeat": datetime.now(tz=timezone.utc).isoformat(), "events_processed": 0},
    }

    @classmethod
    def reset(cls):
        for key in cls._status:
            cls._status[key]["connected"] = True
            cls._status[key]["mode"] = "SIMULATED"
            cls._status[key]["last_heartbeat"] = datetime.now(tz=timezone.utc).isoformat()
            cls._status[key]["events_processed"] = 0

    @classmethod
    def update_module_heartbeat(cls, module_name: str, mode: str = "LIVE"):
        if module_name in cls._status:
            cls._status[module_name]["connected"] = True
            cls._status[module_name]["mode"] = mode
            cls._status[module_name]["last_heartbeat"] = datetime.now(tz=timezone.utc).isoformat()
            cls._status[module_name]["events_processed"] += 1

    @classmethod
    def set_module_status(cls, module_name: str, connected: bool, mode: str = "LIVE"):
        if module_name in cls._status:
            cls._status[module_name]["connected"] = connected
            cls._status[module_name]["mode"] = mode
            if connected:
                cls._status[module_name]["last_heartbeat"] = datetime.now(tz=timezone.utc).isoformat()

    @classmethod
    def get_system_status(cls) -> Dict[str, Any]:
        now = datetime.now(tz=timezone.utc)
        overall_health = "HEALTHY"
        
        modules_res = {}
        mod_map = {
            "part1": "part1_perception",
            "part2": "part2_behaviour",
            "part3": "part3_verification"
        }

        for key, name in mod_map.items():
            mod_data = cls._status[key]
            last_hb = datetime.fromisoformat(mod_data["last_heartbeat"])
            sec_since = (now - last_hb).total_seconds()
            
            is_connected = mod_data["connected"] and (sec_since < 120)
            
            if not mod_data["connected"]:
                status_str = "Offline"
                overall_health = "DEGRADED"
            elif is_connected:
                status_str = "Connected (Simulated)"
            elif mod_data["events_processed"] > 0:
                status_str = "Simulation Complete"
            else:
                status_str = "Idle/Standby"

            modules_res[name] = {
                "status": status_str,
                "mode": mod_data["mode"],
                "events_ingested": mod_data["events_processed"],
                "last_active": mod_data["last_heartbeat"]
            }

        return {
            "system_health": overall_health,
            "active_exam_id": "EXAM_001",
            "timestamp": now.isoformat(),
            "ai_modules": modules_res,
            "websocket_channel": "ONLINE",
            "api_latency_ms": 14.2
        }
