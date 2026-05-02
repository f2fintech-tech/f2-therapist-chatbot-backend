#!/usr/bin/env python
"""
Pain Point Scenario Tester
Tests the emotion analyzer's ability to detect and classify pain point scenarios
Validates that the right stress level and emotional signals are detected for each pain point
"""

import json
import time
from pathlib import Path
from src.utils.emotion_analyzer import analyze_emotion
from src.utils.results_store import append_test_result


def run_pain_point_tests():
    """Run all pain point scenarios through emotion analyzer"""
    
    # Load pain point scenarios
    fixture_path = Path("tests/fixtures/pain_point_scenarios.json")
    if not fixture_path.exists():
        print(f"✗ Pain point fixture not found: {fixture_path}")
        return
    
    with open(fixture_path, 'r') as f:
        scenarios_data = json.load(f)
    
    scenarios = scenarios_data.get('scenarios', [])
    
    print("\n" + "="*80)
    print("PAIN POINT SCENARIO TESTING - EMOTION ANALYZER VALIDATION")
    print("="*80)
    print(f"Testing {len(scenarios)} pain point scenarios across {len(set(s['category'] for s in scenarios))} categories\n")
    
    # Track results by category
    results_by_category = {}
    all_results = []
    
    for scenario in scenarios:
        category = scenario['category']
        message = scenario['message']
        expected_stress = scenario['expected_stress_level']
        scenario_id = scenario['id']
        
        # Analyze emotion
        result = analyze_emotion(message)
        detected_stress = result.get('stress_level')
        
        # Track results
        match = detected_stress == expected_stress
        if category not in results_by_category:
            results_by_category[category] = {'total': 0, 'passed': 0, 'scenarios': []}
        
        results_by_category[category]['total'] += 1
        if match:
            results_by_category[category]['passed'] += 1
        
        results_by_category[category]['scenarios'].append({
            'id': scenario_id,
            'expected': expected_stress,
            'detected': detected_stress,
            'match': match
        })
        
        all_results.append({
            'category': category,
            'scenario_id': scenario_id,
            'message': message[:70] + "..." if len(message) > 70 else message,
            'expected_stress': expected_stress,
            'detected_stress': detected_stress,
            'match': match,
            'full_analysis': result
        })
    
    # Print results by category
    print("RESULTS BY PAIN POINT CATEGORY:")
    print("-" * 80)
    
    total_tests = 0
    total_passed = 0
    
    for category in sorted(results_by_category.keys()):
        cat_results = results_by_category[category]
        total = cat_results['total']
        passed = cat_results['passed']
        accuracy = (passed / total * 100) if total > 0 else 0
        
        total_tests += total
        total_passed += passed
        
        status_icon = "✓" if accuracy >= 80 else "⚠" if accuracy >= 60 else "✗"
        print(f"\n{status_icon} {category}: {passed}/{total} ({accuracy:.0f}%)")
        
        for scenario in cat_results['scenarios']:
            sc_status = "✓" if scenario['match'] else "✗"
            print(f"     {sc_status} {scenario['id']}: {scenario['expected']} -> {scenario['detected']}")
    
    # Overall results
    overall_accuracy = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    print("\n" + "="*80)
    print(f"OVERALL: {total_passed}/{total_tests} PAIN POINTS DETECTED CORRECTLY ({overall_accuracy:.1f}%)")
    print("="*80)
    
    if overall_accuracy >= 80:
        print("✓ EXCELLENT - Pain point detection is accurate and reliable")
    elif overall_accuracy >= 60:
        print("⚠ GOOD - Pain point detection works, but could be improved")
    else:
        print("✗ NEEDS WORK - More keyword tuning required for pain points")
    
    # Save results
    save_pain_point_test_results(scenarios_data, all_results, total_passed, total_tests, overall_accuracy)
    
    return all_results


def save_pain_point_test_results(scenarios_data, results, passed, total, accuracy):
    """Save pain point test results to model_test_results.json"""

    results_path = Path("src/model/model_test_results.json")

    # Create new run
    new_run = {
        'timestamp': time.time(),
        'mode': 'pain_point_scenario_test',
        'total_scenarios': total,
        'passed': passed,
        'accuracy': accuracy,
        'pain_point_categories': len(set(s['category'] for s in scenarios_data.get('scenarios', []))),
        'test_results': results
    }
    
    append_test_result(new_run, results_path)
    
    print(f"\n✓ Results saved to {results_path}")


if __name__ == "__main__":
    run_pain_point_tests()
