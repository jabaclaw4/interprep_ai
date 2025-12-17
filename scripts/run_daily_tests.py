# scripts/run_daily_tests.py
# !/usr/bin/env python3
"""
Скрипт для ежедневного прогона тестов и генерации отчета.
Запускается по cron: 0 2 * * * (каждую ночь в 2:00)
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e.test_metrics import TestAccuracyMetrics
from tests.e2e.test_feedback_quality import TestFeedbackQuality
from tests.e2e.test_scenario_coverage import TestScenarioCoverage
from tests.performance.test_response_time import TestPerformanceMetrics
from tests.integration.test_agent_workflow import TestFunctionalCompleteness


async def run_daily_tests():
    """Запуск всех тестов и сбор метрик."""

    report = {
        "date": datetime.now().isoformat(),
        "version": "MVP v1.2",
        "metrics": {}
    }

    print("=" * 60)
    print("DAILY QUALITY TESTS - AI AGENTS")
    print(f"Date: {report['date']}")
    print("=" * 60)

    try:
        # 1. Точность
        print("\n1. Testing Accuracy (>85%)...")
        accuracy_test = TestAccuracyMetrics()
        await accuracy_test.test_overall_accuracy()
        report["metrics"]["accuracy"] = getattr(accuracy_test, "custom_metrics", {})
        print("✓ Accuracy tests completed")

    except Exception as e:
        report["metrics"]["accuracy"] = {"error": str(e)}
        print(f"✗ Accuracy tests failed: {e}")

    try:
        # 2. Качество фидбэка
        print("\n2. Testing Feedback Quality (>80%)...")
        feedback_test = TestFeedbackQuality()
        await feedback_test.test_feedback_usefulness()
        print("✓ Feedback tests completed")

    except Exception as e:
        print(f"✗ Feedback tests failed: {e}")

    try:
        # 3. Покрытие тем
        print("\n3. Testing Topic Coverage...")
        coverage_test = TestScenarioCoverage()
        await coverage_test.test_topic_coverage()
        report["metrics"]["coverage"] = getattr(coverage_test, "coverage_metrics", {})
        print("✓ Coverage tests completed")

    except Exception as e:
        report["metrics"]["coverage"] = {"error": str(e)}
        print(f"✗ Coverage tests failed: {e}")

    try:
        # 4. Производительность
        print("\n4. Testing Performance (<3s)...")
        perf_test = TestPerformanceMetrics()
        await perf_test.test_response_time_threshold()
        report["metrics"]["performance"] = getattr(perf_test, "performance_metrics", {})
        print("✓ Performance tests completed")

    except Exception as e:
        report["metrics"]["performance"] = {"error": str(e)}
        print(f"✗ Performance tests failed: {e}")

    try:
        # 5. Функциональная полнота
        print("\n5. Testing Functional Completeness...")
        func_test = TestFunctionalCompleteness()
        await func_test.test_all_agents_integrated()
        print("✓ Functional tests completed")

    except Exception as e:
        print(f"✗ Functional tests failed: {e}")

    # Сохраняем отчет
    reports_dir = project_root / "reports"
    reports_dir.mkdir(exist_ok=True)

    report_file = reports_dir / f"daily_metrics_{datetime.now().strftime('%Y%m%d')}.json"

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Report saved to: {report_file}")
    print(f"{'=' * 60}")

    # Проверяем критичные метрики
    critical_failures = []

    if "accuracy" in report["metrics"]:
        accuracy = report["metrics"]["accuracy"].get("accuracy_overall", 0)
        if accuracy < 85:
            critical_failures.append(f"Accuracy below 85%: {accuracy:.1f}%")

    if "performance" in report["metrics"]:
        avg_time = report["metrics"]["performance"].get("avg_response_time", 10)
        if avg_time > 3:
            critical_failures.append(f"Performance above 3s: {avg_time:.2f}s")

    if critical_failures:
        print("\n⚠️  CRITICAL FAILURES DETECTED:")
        for failure in critical_failures:
            print(f"  - {failure}")

        # Здесь можно добавить отправку алерта (Slack, email, etc.)
        # send_alert_to_slack(critical_failures)

        sys.exit(1)  # Возвращаем ошибку для CI/CD

    print("\n✅ All critical metrics are within thresholds")
    return report


if __name__ == "__main__":
    asyncio.run(run_daily_tests())