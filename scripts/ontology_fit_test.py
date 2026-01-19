#!/usr/bin/env python3
"""
Ontology Fit Assessment for OG-RAG Integration

Tests BAS-Ontology /api/ground endpoint to evaluate its suitability
for OG-RAG-style ontology-grounded retrieval.

Usage:
    python scripts/ontology_fit_test.py [--url http://localhost:8000]
"""

import os
import sys
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import requests
from collections import defaultdict, Counter
import statistics

# Add reasonable defaults
BAS_ONTOLOGY_URL = os.getenv("BAS_ONTOLOGY_URL", "http://localhost:8000")
OUTPUT_DIR = "outputs"
RESULTS_FILE = f"{OUTPUT_DIR}/ontology_fit_results.jsonl"
SUMMARY_FILE = f"{OUTPUT_DIR}/ontology_fit_summary.md"

# Test query categories
TEST_QUERIES = {
    # BAS Jargon / Native Technical Language
    "jargon": [
        "VAV discharge air temperature too high",
        "AHU economizer occupied unoccupied sequence",
        "Supply fan proof not made",
        "Chiller low suction pressure alarm",
        "Boiler enable disable interlock",
        "Zone temp sensor reading unstable",
        "Damper command stuck at 0%",
        "BACnet MSTP device offline",
        "FCU heating valve position",
        "RTU compressor staging",
        "MAU mixed air damper actuator",
        "Exhaust fan VFD speed control",
        "Hot water pump differential pressure",
        "Cooling coil discharge temperature sensor",
        "Static pressure setpoint reset",
        "Occupancy schedule override",
        "DDC controller communication failure",
        "Glycol concentration low freeze protection",
        "Enthalpy economizer high limit cutout",
        "Terminal box airflow tracking",
        "Primary secondary pumping configuration",
        "Condenser water approach temperature",
        "Dew point control sequence",
        "Lead lag boiler rotation",
        "Free cooling changeover valve",
    ],

    # Natural Language Paraphrases
    "paraphrase": [
        "The air coming out is too warm at the terminal",
        "How do I set free cooling when the building is occupied?",
        "The fan won't start even though it's enabled",
        "Cooling machine pressure is low, what could cause it?",
        "Heating unit won't turn on unless something else is on",
        "Room temperature reading jumps around",
        "The air damper is not moving from zero",
        "Network device is not responding",
        "How hot should the water be at the coil?",
        "The pump isn't maintaining enough pressure",
        "The compressor keeps cycling on and off",
        "What controls the fan speed?",
        "Why is the building getting too much fresh air?",
        "How do I check if the valve is working?",
        "The outside air temperature sensor seems wrong",
        "How to tell if the economizer is enabled?",
        "What makes the boiler turn on?",
        "The cooling isn't working during hot days",
        "How to reset the time schedule?",
        "Why won't the unit respond to commands?",
        "What's the normal temperature for chilled water?",
        "How do I know if the filter needs changing?",
        "The building is too humid in summer",
        "What controls when the heat turns on?",
        "How to switch between primary and backup equipment?",
    ],

    # Ambiguous / Under-specified Queries
    "ambiguity": [
        "Fan not working",
        "Temperature too high",
        "Controller offline",
        "Alarm on unit",
        "Airflow problem",
        "Sensor error",
        "Valve stuck",
        "Pump failure",
        "Communication lost",
        "Setpoint change",
        "High pressure",
        "Low temperature",
        "Device unresponsive",
        "System fault",
        "Override active",
        "Schedule not running",
        "High humidity",
        "Low airflow",
        "Damper issue",
        "Network problem",
        "Temperature drift",
        "Pressure drop",
        "Flow rate low",
        "Equipment offline",
        "Control mode change",
    ],
}


@dataclass
class QueryResult:
    """Results from a single /api/ground query"""
    query: str
    category: str
    success: bool
    response_time_ms: float
    status_code: int
    error: Optional[str] = None

    # Grounding outputs
    concepts: List[Dict[str, Any]] = None
    equipment_detected: bool = False
    point_tags_detected: bool = False
    brick_mappings: List[str] = None
    confidence_scores: List[float] = None
    num_concepts: int = 0

    # Raw response
    raw_response: Dict[str, Any] = None

    def __post_init__(self):
        if self.concepts is None:
            self.concepts = []
        if self.brick_mappings is None:
            self.brick_mappings = []
        if self.confidence_scores is None:
            self.confidence_scores = []


class OntologyFitTester:
    """Test harness for evaluating BAS-Ontology fit for OG-RAG"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.ground_endpoint = f"{self.base_url}/api/ground"
        self.results: List[QueryResult] = []

    def test_connection(self) -> bool:
        """Verify BAS-Ontology service is reachable"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Connected to BAS-Ontology at {self.base_url}")
                return True
            else:
                print(f"⚠️  BAS-Ontology responded with status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to BAS-Ontology at {self.base_url}")
            print(f"   Error: {e}")
            return False

    def query_ground(self, text: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Send query to /api/ground endpoint"""
        try:
            start = time.time()
            response = requests.post(
                self.ground_endpoint,
                json={"query": text},  # Fixed: BAS-Ontology expects "query" not "text"
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            elapsed_ms = (time.time() - start) * 1000

            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time_ms": elapsed_ms,
                "data": response.json() if response.status_code == 200 else None,
                "error": None if response.status_code == 200 else response.text
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "status_code": 504,
                "response_time_ms": timeout * 1000,
                "data": None,
                "error": "Request timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 500,
                "response_time_ms": 0,
                "data": None,
                "error": str(e)
            }

    def parse_ground_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse /api/ground response to extract relevant features.

        BAS-Ontology /api/ground returns:
        {
            "equipment_types": [...],
            "point_types": [...],
            "raw_tags": [...],
            "mappings": [...],
            "ontology_version": "4.0.0"
        }
        """
        parsed = {
            "concepts": [],
            "equipment_detected": False,
            "point_tags_detected": False,
            "brick_mappings": [],
            "confidence_scores": [],
            "num_concepts": 0
        }

        if not data:
            return parsed

        # Parse BAS-Ontology /api/ground response structure
        equipment_types = data.get("equipment_types", [])
        point_types = data.get("point_types", [])

        # Combine equipment and points as "concepts"
        parsed["concepts"] = equipment_types + point_types
        parsed["num_concepts"] = len(parsed["concepts"])

        # Equipment detection
        if equipment_types:
            parsed["equipment_detected"] = True
            for equip in equipment_types:
                if equip.get("brick_class"):
                    parsed["brick_mappings"].append(equip["brick_class"])
                if equip.get("confidence"):
                    parsed["confidence_scores"].append(equip["confidence"])

        # Point detection
        if point_types:
            parsed["point_tags_detected"] = True
            for point in point_types:
                if point.get("brick_class"):
                    parsed["brick_mappings"].append(point["brick_class"])
                if point.get("confidence"):
                    parsed["confidence_scores"].append(point["confidence"])

        return parsed

    def run_test_suite(self) -> None:
        """Execute all test queries"""
        print("\n" + "="*70)
        print("ONTOLOGY FIT TEST - Starting")
        print("="*70)

        total_queries = sum(len(queries) for queries in TEST_QUERIES.values())
        current = 0

        for category, queries in TEST_QUERIES.items():
            print(f"\n📋 Testing {category.upper()} queries ({len(queries)} queries)...")

            for query_text in queries:
                current += 1
                print(f"  [{current}/{total_queries}] {query_text[:60]}...", end=" ")

                # Query the grounding endpoint
                response = self.query_ground(query_text)

                # Parse response
                parsed = self.parse_ground_response(response["data"])

                # Create result record
                result = QueryResult(
                    query=query_text,
                    category=category,
                    success=response["success"],
                    response_time_ms=response["response_time_ms"],
                    status_code=response["status_code"],
                    error=response["error"],
                    concepts=parsed["concepts"],
                    equipment_detected=parsed["equipment_detected"],
                    point_tags_detected=parsed["point_tags_detected"],
                    brick_mappings=parsed["brick_mappings"],
                    confidence_scores=parsed["confidence_scores"],
                    num_concepts=parsed["num_concepts"],
                    raw_response=response["data"]
                )

                self.results.append(result)

                # Status indicator
                if result.success:
                    status = f"✓ ({result.num_concepts} concepts)"
                else:
                    status = f"✗ {result.error}"
                print(status)

                # Be nice to the API
                time.sleep(0.1)

        print(f"\n✅ Completed {len(self.results)} queries")

    def save_results(self) -> None:
        """Save raw results to JSONL file"""
        print(f"\n💾 Saving results to {RESULTS_FILE}...")

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        with open(RESULTS_FILE, 'w') as f:
            for result in self.results:
                f.write(json.dumps(asdict(result)) + "\n")

        print(f"✅ Saved {len(self.results)} results")

    def compute_metrics(self) -> Dict[str, Any]:
        """Compute comprehensive metrics from test results"""

        metrics = {
            "overall": {},
            "by_category": {},
            "failure_modes": [],
            "confidence_stats": {},
            "concept_stats": {}
        }

        # Overall metrics
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)

        metrics["overall"] = {
            "total_queries": total,
            "successful_queries": successful,
            "failed_queries": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "avg_response_time_ms": statistics.mean(r.response_time_ms for r in self.results) if self.results else 0
        }

        # Detection rates (only for successful queries)
        successful_results = [r for r in self.results if r.success]
        if successful_results:
            equip_detected = sum(1 for r in successful_results if r.equipment_detected)
            point_detected = sum(1 for r in successful_results if r.point_tags_detected)
            brick_detected = sum(1 for r in successful_results if r.brick_mappings)

            metrics["overall"]["equipment_detection_rate"] = equip_detected / len(successful_results)
            metrics["overall"]["point_detection_rate"] = point_detected / len(successful_results)
            metrics["overall"]["brick_mapping_rate"] = brick_detected / len(successful_results)

        # By-category breakdown
        for category in TEST_QUERIES.keys():
            cat_results = [r for r in self.results if r.category == category]
            cat_success = [r for r in cat_results if r.success]

            if cat_results:
                metrics["by_category"][category] = {
                    "total": len(cat_results),
                    "successful": len(cat_success),
                    "success_rate": len(cat_success) / len(cat_results),
                    "equipment_detection_rate": sum(1 for r in cat_success if r.equipment_detected) / len(cat_success) if cat_success else 0,
                    "point_detection_rate": sum(1 for r in cat_success if r.point_tags_detected) / len(cat_success) if cat_success else 0,
                    "brick_mapping_rate": sum(1 for r in cat_success if r.brick_mappings) / len(cat_success) if cat_success else 0,
                    "avg_concepts": statistics.mean(r.num_concepts for r in cat_success) if cat_success else 0
                }

        # Failure mode analysis
        failure_counter = Counter()
        for result in self.results:
            if not result.success:
                failure_counter[result.error or "unknown"] += 1
            elif result.num_concepts == 0:
                failure_counter["no_concepts_returned"] += 1

        metrics["failure_modes"] = [
            {"mode": mode, "count": count}
            for mode, count in failure_counter.most_common(10)
        ]

        # Confidence statistics
        all_confidences = []
        for result in successful_results:
            all_confidences.extend(result.confidence_scores)

        if all_confidences:
            metrics["confidence_stats"] = {
                "mean": statistics.mean(all_confidences),
                "median": statistics.median(all_confidences),
                "stdev": statistics.stdev(all_confidences) if len(all_confidences) > 1 else 0,
                "min": min(all_confidences),
                "max": max(all_confidences),
                "count": len(all_confidences)
            }

        # Concept count statistics
        concept_counts = [r.num_concepts for r in successful_results]
        if concept_counts:
            metrics["concept_stats"] = {
                "mean": statistics.mean(concept_counts),
                "median": statistics.median(concept_counts),
                "min": min(concept_counts),
                "max": max(concept_counts),
                "zero_concepts": sum(1 for c in concept_counts if c == 0)
            }

        return metrics

    def generate_summary_report(self, metrics: Dict[str, Any]) -> str:
        """Generate markdown summary report"""

        report = []
        report.append("# BAS-Ontology OG-RAG Fit Assessment")
        report.append("\n**Assessment Date:** " + time.strftime("%Y-%m-%d %H:%M:%S"))
        report.append(f"\n**Endpoint:** `{self.ground_endpoint}`")

        # Executive Summary
        report.append("\n## Executive Summary")
        report.append(f"\n- **Total Queries:** {metrics['overall']['total_queries']}")
        report.append(f"- **Success Rate:** {metrics['overall']['success_rate']:.1%}")
        report.append(f"- **Avg Response Time:** {metrics['overall']['avg_response_time_ms']:.1f}ms")

        if "equipment_detection_rate" in metrics["overall"]:
            report.append(f"- **Equipment Detection Rate:** {metrics['overall']['equipment_detection_rate']:.1%}")
            report.append(f"- **Point Detection Rate:** {metrics['overall']['point_detection_rate']:.1%}")
            report.append(f"- **Brick Mapping Rate:** {metrics['overall']['brick_mapping_rate']:.1%}")

        # Performance by Category
        report.append("\n## Performance by Query Category")
        report.append("\n| Category | Queries | Success | Equip | Points | Brick | Avg Concepts |")
        report.append("|----------|---------|---------|-------|--------|-------|--------------|")

        for category, stats in metrics["by_category"].items():
            report.append(
                f"| {category:12} | {stats['total']:7} | "
                f"{stats['success_rate']:6.1%} | "
                f"{stats['equipment_detection_rate']:5.1%} | "
                f"{stats['point_detection_rate']:6.1%} | "
                f"{stats['brick_mapping_rate']:5.1%} | "
                f"{stats['avg_concepts']:12.1f} |"
            )

        # Recall Drop Analysis
        report.append("\n## Recall Drop: Jargon → Paraphrase")
        jargon_stats = metrics["by_category"].get("jargon", {})
        para_stats = metrics["by_category"].get("paraphrase", {})

        if jargon_stats and para_stats:
            equip_drop = jargon_stats["equipment_detection_rate"] - para_stats["equipment_detection_rate"]
            point_drop = jargon_stats["point_detection_rate"] - para_stats["point_detection_rate"]

            report.append(f"\n- **Equipment Detection Drop:** {equip_drop:+.1%}")
            report.append(f"- **Point Detection Drop:** {point_drop:+.1%}")

            if abs(equip_drop) > 0.2 or abs(point_drop) > 0.2:
                report.append("\n⚠️ **SIGNIFICANT RECALL DROP** when queries use natural language vs BAS jargon")

        # Confidence Statistics
        if metrics["confidence_stats"]:
            conf = metrics["confidence_stats"]
            report.append("\n## Confidence Score Distribution")
            report.append(f"\n- **Mean:** {conf['mean']:.3f}")
            report.append(f"- **Median:** {conf['median']:.3f}")
            report.append(f"- **Std Dev:** {conf['stdev']:.3f}")
            report.append(f"- **Range:** [{conf['min']:.3f}, {conf['max']:.3f}]")

        # Concept Statistics
        if metrics["concept_stats"]:
            concepts = metrics["concept_stats"]
            report.append("\n## Concept Count Statistics")
            report.append(f"\n- **Mean Concepts per Query:** {concepts['mean']:.1f}")
            report.append(f"- **Median:** {concepts['median']:.1f}")
            report.append(f"- **Range:** [{concepts['min']}, {concepts['max']}]")
            report.append(f"- **Queries with Zero Concepts:** {concepts['zero_concepts']}")

        # Failure Modes
        if metrics["failure_modes"]:
            report.append("\n## Top Failure Modes")
            report.append("\n| Failure Mode | Count |")
            report.append("|--------------|-------|")
            for failure in metrics["failure_modes"][:10]:
                report.append(f"| {failure['mode'][:60]} | {failure['count']} |")

        # Sample Outputs
        report.append("\n## Sample Grounding Outputs")

        # Show 3 examples from each category
        for category in ["jargon", "paraphrase", "ambiguity"]:
            cat_results = [r for r in self.results if r.category == category and r.success][:3]
            if cat_results:
                report.append(f"\n### {category.title()} Examples")
                for i, result in enumerate(cat_results, 1):
                    report.append(f"\n**{i}. Query:** \"{result.query}\"")
                    report.append(f"- Concepts: {result.num_concepts}")
                    report.append(f"- Equipment: {'✓' if result.equipment_detected else '✗'}")
                    report.append(f"- Points: {'✓' if result.point_tags_detected else '✗'}")
                    if result.brick_mappings:
                        report.append(f"- Brick: {', '.join(result.brick_mappings[:3])}")

        return "\n".join(report)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Test BAS-Ontology fit for OG-RAG")
    parser.add_argument("--url", default=BAS_ONTOLOGY_URL,
                       help="BAS-Ontology service URL")
    args = parser.parse_args()

    # Initialize tester
    tester = OntologyFitTester(args.url)

    # Test connection
    if not tester.test_connection():
        print("\n❌ Cannot proceed without connection to BAS-Ontology")
        print(f"   Make sure the service is running at {args.url}")
        sys.exit(1)

    # Run test suite
    tester.run_test_suite()

    # Save raw results
    tester.save_results()

    # Compute metrics
    print("\n📊 Computing metrics...")
    metrics = tester.compute_metrics()

    # Generate report
    print(f"📝 Generating summary report...")
    report = tester.generate_summary_report(metrics)

    # Save report
    with open(SUMMARY_FILE, 'w') as f:
        f.write(report)

    print(f"\n✅ Summary report saved to {SUMMARY_FILE}")

    # Print key findings
    print("\n" + "="*70)
    print("KEY FINDINGS")
    print("="*70)
    print(f"Success Rate: {metrics['overall']['success_rate']:.1%}")
    if "equipment_detection_rate" in metrics["overall"]:
        print(f"Equipment Detection: {metrics['overall']['equipment_detection_rate']:.1%}")
        print(f"Point Detection: {metrics['overall']['point_detection_rate']:.1%}")
        print(f"Brick Mapping: {metrics['overall']['brick_mapping_rate']:.1%}")

    print(f"\n📄 Full report: {SUMMARY_FILE}")
    print(f"📄 Raw results: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
