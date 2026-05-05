"""
Health monitoring for deployed services and API quotas.
Checks:
- API response latency and errors
- Gemini API quota availability
- Pinecone quota and index health
- Model response quality
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

load_dotenv()


class HealthMonitor:
    """Monitor service health, latency, quotas, and error rates."""

    def __init__(self):
        """Initialize health monitor with API clients."""
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.start_time = time.time()
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
            "alerts": [],
            "overall_status": "UNKNOWN"
        }

    def check_gemini_quota(self) -> Dict[str, Any]:
        """Check Gemini API quota availability."""
        check_name = "gemini_quota"
        logger.info(f"Running check: {check_name}")

        result = {
            "name": check_name,
            "status": "UNKNOWN",
            "message": "",
            "latency_ms": 0,
            "details": {}
        }

        if not self.gemini_api_key:
            result["status"] = "CRITICAL"
            result["message"] = "GEMINI_API_KEY not set"
            return result

        try:
            from google import genai

            start = time.time()
            client = genai.Client(api_key=self.gemini_api_key)

            # Test a simple embedding to verify quota is available
            embed_result = client.models.embed_content(
                model="gemini-embedding-2",
                contents="Health check test",
            )

            latency = (time.time() - start) * 1000
            result["latency_ms"] = latency
            result["status"] = "OK"
            result["message"] = f"Gemini API responding normally (latency: {latency:.0f}ms)"
            result["details"]["embedding_dim"] = len(embed_result.embeddings[0].values) if embed_result.embeddings else 0

        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "resource_exhausted" in error_msg or "exceeded" in error_msg:
                result["status"] = "CRITICAL"
                result["message"] = f"Gemini API quota exhausted: {str(e)[:100]}"
                self.results["alerts"].append({
                    "severity": "CRITICAL",
                    "service": "Gemini API",
                    "message": result["message"]
                })
            else:
                result["status"] = "WARNING"
                result["message"] = f"Gemini API error: {str(e)[:100]}"

        return result

    def check_pinecone_health(self) -> Dict[str, Any]:
        """Check Pinecone index health and connectivity."""
        check_name = "pinecone_health"
        logger.info(f"Running check: {check_name}")

        result = {
            "name": check_name,
            "status": "UNKNOWN",
            "message": "",
            "latency_ms": 0,
            "details": {}
        }

        if not self.pinecone_api_key:
            result["status"] = "WARNING"
            result["message"] = "PINECONE_API_KEY not set (optional for local testing)"
            return result

        try:
            from pinecone import Pinecone

            start = time.time()
            pc = Pinecone(api_key=self.pinecone_api_key)
            index = pc.Index("f2-therapy-index")

            # Get index stats
            stats = index.describe_index_stats()
            latency = (time.time() - start) * 1000

            result["latency_ms"] = latency
            result["status"] = "OK"
            result["message"] = f"Pinecone index healthy (latency: {latency:.0f}ms)"
            result["details"]["vector_count"] = stats.total_vector_count if hasattr(stats, 'total_vector_count') else "N/A"
            result["details"]["index_name"] = "f2-therapy-index"

        except Exception as e:
            result["status"] = "WARNING"
            result["message"] = f"Pinecone health check error: {str(e)[:100]}"
            self.results["alerts"].append({
                "severity": "WARNING",
                "service": "Pinecone",
                "message": result["message"]
            })

        return result

    def check_model_latency(self) -> Dict[str, Any]:
        """Check model response latency."""
        check_name = "model_latency"
        logger.info(f"Running check: {check_name}")

        result = {
            "name": check_name,
            "status": "UNKNOWN",
            "message": "",
            "latency_ms": 0,
            "details": {}
        }

        if not self.gemini_api_key:
            result["status"] = "SKIPPED"
            result["message"] = "Skipped - Gemini API key not set"
            return result

        try:
            from google import genai

            client = genai.Client(api_key=self.gemini_api_key)

            test_prompt = "I feel stressed. Help me briefly."
            start = time.time()

            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=test_prompt,
            )

            latency = (time.time() - start) * 1000
            result["latency_ms"] = latency
            result["details"]["response_length"] = len(response.text) if response and response.text else 0

            # Set status based on latency thresholds
            if latency < 2000:
                result["status"] = "OK"
                result["message"] = f"Model response latency: {latency:.0f}ms (acceptable)"
            elif latency < 5000:
                result["status"] = "WARNING"
                result["message"] = f"Model response latency: {latency:.0f}ms (degraded, >= 2s)"
                self.results["alerts"].append({
                    "severity": "WARNING",
                    "service": "Model Latency",
                    "message": result["message"]
                })
            else:
                result["status"] = "CRITICAL"
                result["message"] = f"Model response latency: {latency:.0f}ms (high, >= 5s)"
                self.results["alerts"].append({
                    "severity": "CRITICAL",
                    "service": "Model Latency",
                    "message": result["message"]
                })

        except Exception as e:
            result["status"] = "ERROR"
            result["message"] = f"Model latency check failed: {str(e)[:100]}"
            self.results["alerts"].append({
                "severity": "WARNING",
                "service": "Model",
                "message": result["message"]
            })

        return result

    def check_required_files(self) -> Dict[str, Any]:
        """Check that required configuration and data files exist."""
        check_name = "required_files"
        logger.info(f"Running check: {check_name}")

        result = {
            "name": check_name,
            "status": "OK",
            "message": "",
            "latency_ms": 0,
            "details": {"missing_files": []}
        }

        required_files = [
            Path("src/data/processed/system_prompt.md"),
            Path("src/data/processed/conversation_training_data.json"),
            Path("src/model/finetuned_system_prompt.txt"),
            Path("requirements.txt"),
        ]

        missing = [str(f) for f in required_files if not f.exists()]

        if missing:
            result["status"] = "WARNING"
            result["message"] = f"Missing files: {', '.join(missing)}"
            result["details"]["missing_files"] = missing
            self.results["alerts"].append({
                "severity": "WARNING",
                "service": "Configuration",
                "message": f"Missing required files: {', '.join(missing)}"
            })
        else:
            result["message"] = "All required files present"

        return result

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and compile results."""
        logger.info("Starting health monitoring checks...")

        # Run all checks
        self.results["checks"]["gemini_quota"] = self.check_gemini_quota()
        self.results["checks"]["pinecone_health"] = self.check_pinecone_health()
        self.results["checks"]["model_latency"] = self.check_model_latency()
        self.results["checks"]["required_files"] = self.check_required_files()

        # Determine overall status
        statuses = [c.get("status") for c in self.results["checks"].values() if c.get("status") != "SKIPPED"]

        if "CRITICAL" in statuses:
            self.results["overall_status"] = "CRITICAL"
        elif "ERROR" in statuses:
            self.results["overall_status"] = "ERROR"
        elif "WARNING" in statuses:
            self.results["overall_status"] = "WARNING"
        else:
            self.results["overall_status"] = "OK"

        # Calculate total monitoring time
        self.results["total_time_ms"] = (time.time() - self.start_time) * 1000

        logger.info(f"Health monitoring complete. Status: {self.results['overall_status']}")
        logger.info(f"Alerts: {len(self.results['alerts'])}")

        return self.results

    def save_results(self, output_path: str = "src/monitoring/health_check_results.json") -> None:
        """Save monitoring results to JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to {output_path}")

    def print_summary(self) -> None:
        """Print a summary of monitoring results."""
        print("\n" + "=" * 80)
        print("HEALTH MONITORING SUMMARY")
        print("=" * 80)
        print(f"Overall Status: {self.results['overall_status']}")
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Total Checks: {len(self.results['checks'])}")
        print(f"Total Alerts: {len(self.results['alerts'])}")
        print(f"Time: {self.results['total_time_ms']:.0f}ms\n")

        # Print check details
        print("CHECK RESULTS:")
        for check_name, check_result in self.results["checks"].items():
            status = check_result.get("status", "UNKNOWN")
            message = check_result.get("message", "")
            latency = check_result.get("latency_ms", 0)
            
            symbol = "✓" if status == "OK" else "✗" if status in ["ERROR", "CRITICAL"] else "⚠"
            latency_str = f" ({latency:.0f}ms)" if latency else ""
            print(f"{symbol} {check_name}: {status}{latency_str}")
            if message:
                print(f"  {message}")

        # Print alerts
        if self.results["alerts"]:
            print("\nALERTS:")
            for alert in self.results["alerts"]:
                severity = alert.get("severity", "INFO")
                service = alert.get("service", "Unknown")
                message = alert.get("message", "")
                symbol = "🔴" if severity == "CRITICAL" else "🟡" if severity == "WARNING" else "ℹ"
                print(f"{symbol} [{severity}] {service}: {message}")

        print("=" * 80 + "\n")


def should_alert(results: Dict[str, Any], threshold: str = "WARNING") -> bool:
    """Determine if an alert should be triggered based on threshold."""
    status = results.get("overall_status", "OK")
    
    if threshold == "CRITICAL":
        return status == "CRITICAL"
    elif threshold == "WARNING":
        return status in ["CRITICAL", "WARNING"]
    else:
        return False


def main():
    """Main entry point for health monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description="Run health monitoring checks")
    parser.add_argument(
        "--output",
        type=str,
        default="src/monitoring/health_check_results.json",
        help="Output file for results",
    )
    parser.add_argument(
        "--alert-threshold",
        type=str,
        choices=["CRITICAL", "WARNING"],
        default="WARNING",
        help="Alert severity threshold",
    )

    args = parser.parse_args()

    # Run monitoring
    monitor = HealthMonitor()
    results = monitor.run_all_checks()
    monitor.save_results(args.output)
    monitor.print_summary()

    # Exit with error code if alerts triggered
    if should_alert(results, args.alert_threshold):
        print(f"⚠ Alerts triggered (threshold: {args.alert_threshold})")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
