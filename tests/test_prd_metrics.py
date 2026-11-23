"""
PRD Benchmark Evaluation Test Suite:
Validates the 3 Key Success Metrics defined in PRD Section 1:
1. Basic Extraction Completeness: >= 90%
2. Deduplication Accuracy: 0% duplicate rate
3. Execution Stability: Process at least 100 entities in one work cycle
"""
import pytest
from loop.evaluator import PRDEvaluator
from storage.database import DatabaseManager


class TestPRDMetricsBenchmark:
    def test_completeness_rate_threshold_90_percent(self):
        # Generate 100 mock entities: 95 complete, 5 missing phone
        entities = []
        for i in range(100):
            item = {
                "business_name": f"Bisnis Sukses {i}",
                "address": f"Jl. Jenderal Sudirman No. {i}, Jakarta",
                "phone_number": f"+628120000{i:04d}" if i < 95 else None,
                "website_url": f"https://bisnis{i}.com",
            }
            entities.append(item)

        report = PRDEvaluator.evaluate_entities(entities)
        assert report.total_entities == 100
        assert report.completeness_rate == 0.95
        assert report.completeness_target_met is True

        # Test failure case when completeness drops below 90%
        failing_entities = [dict(e) for e in entities]
        for j in range(20):
            failing_entities[j]["phone_number"] = None

        fail_report = PRDEvaluator.evaluate_entities(failing_entities)
        assert fail_report.completeness_rate < 0.90
        assert fail_report.completeness_target_met is False

    def test_deduplication_zero_percent_rate(self):
        # 100 unique entities
        entities = [
            {
                "business_name": f"Cafe Unik {i}",
                "address": f"Jl. Merdeka No. {i}",
                "phone_number": f"+628130000{i:04d}",
            }
            for i in range(100)
        ]

        report = PRDEvaluator.evaluate_entities(entities)
        assert report.duplicate_count == 0
        assert report.deduplication_target_met is True

        # Introduce duplicate
        entities.append({
            "business_name": "Cafe Unik 0",
            "address": "Jl. Merdeka No. 0",
            "phone_number": "+6281300000000",
        })
        dup_report = PRDEvaluator.evaluate_entities(entities)
        assert dup_report.duplicate_count == 1
        assert dup_report.deduplication_target_met is False

    def test_execution_stability_100_entities_cycle(self):
        # Verifies stability counter reaches minimum 100 entities
        db = DatabaseManager("sqlite:///:memory:")
        for i in range(110):
            db.insert_or_update_entity(
                search_keyword="restoran",
                business_name=f"Restoran Nusantara {i}",
                category="Indonesian Restaurant",
                address=f"Jl. Diponegoro No. {i}, Jakarta",
                phone_number=f"+628110000{i:04d}",
                website_url=f"https://resto{i}.co.id",
            )

        entities = db.get_all_entities_as_dicts()
        report = PRDEvaluator.evaluate_entities(entities)
        assert report.stability_processed_count >= 100
        assert report.stability_target_met is True
        assert report.all_targets_met is True
