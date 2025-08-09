#!/usr/bin/env python3
"""
Integration Test Runner for Discord Ticket Bot

This script runs comprehensive integration tests to validate the complete
bot functionality including real Discord server simulation, command validation,
database operations under load, and error recovery mechanisms.
"""
import asyncio
import subprocess
import sys
import os
import time
import json
from pathlib import Path
from typing import Dict, List, Any


class IntegrationTestRunner:
    """Comprehensive integration test runner."""
    
    def __init__(self):
        self.test_results = {
            'unit_tests': {'passed': 0, 'failed': 0, 'errors': []},
            'integration_tests': {'passed': 0, 'failed': 0, 'errors': []},
            'system_tests': {'passed': 0, 'failed': 0, 'errors': []},
            'final_tests': {'passed': 0, 'failed': 0, 'errors': []},
            'performance_tests': {'passed': 0, 'failed': 0, 'errors': []},
            'total_duration': 0
        }
    
    def print_header(self, title: str):
        """Print a formatted header."""
        print("\n" + "=" * 80)
        print(f"🧪 {title}")
        print("=" * 80)
    
    def print_section(self, title: str):
        """Print a formatted section header."""
        print(f"\n📋 {title}")
        print("-" * 60)
    
    def run_pytest_suite(self, test_file: str, test_name: str) -> Dict[str, Any]:
        """Run a pytest suite and return results."""
        self.print_section(f"Running {test_name}")
        
        start_time = time.time()
        
        try:
            # Run pytest with verbose output
            cmd = [
                sys.executable, "-m", "pytest",
                test_file,
                "-v",
                "--tb=short"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            duration = time.time() - start_time
            
            # Parse results from pytest output
            output_lines = result.stdout.split('\n') if result.stdout else []
            
            # Count passed/failed tests from output
            passed_count = 0
            failed_count = 0
            
            for line in output_lines:
                if " PASSED " in line:
                    passed_count += 1
                elif " FAILED " in line or " ERROR " in line:
                    failed_count += 1
            
            # Parse results
            if result.returncode == 0:
                print(f"✅ {test_name} PASSED")
                passed = max(passed_count, 1) if passed_count > 0 else 1
                failed = 0
                errors = []
            else:
                print(f"❌ {test_name} FAILED")
                passed = passed_count
                failed = max(failed_count, 1) if failed_count > 0 else 1
                errors = [result.stderr] if result.stderr else ["Test execution failed"]
            
            print(f"Duration: {duration:.2f} seconds")
            if result.stdout:
                print("Output:", result.stdout[-500:])  # Last 500 chars
            if result.stderr:
                print("Errors:", result.stderr[-500:])  # Last 500 chars
            
            return {
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'duration': duration,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ {test_name} TIMED OUT after {duration:.2f} seconds")
            return {
                'passed': 0,
                'failed': 1,
                'errors': [f"{test_name} timed out after {duration:.2f} seconds"],
                'duration': duration,
                'returncode': -1
            }
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 {test_name} CRASHED: {str(e)}")
            return {
                'passed': 0,
                'failed': 1,
                'errors': [f"{test_name} crashed: {str(e)}"],
                'duration': duration,
                'returncode': -1
            }
    
    def run_python_test_suite(self, test_file: str, test_name: str) -> Dict[str, Any]:
        """Run a Python test suite directly."""
        self.print_section(f"Running {test_name}")
        
        start_time = time.time()
        
        try:
            # Run the test file directly
            cmd = [sys.executable, test_file]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            duration = time.time() - start_time
            
            # Parse results
            if result.returncode == 0:
                print(f"✅ {test_name} PASSED")
                # Try to extract test count from output
                output_lines = result.stdout.split('\n') if result.stdout else []
                passed_count = 0
                for line in output_lines:
                    if "PASSED" in line or "✅" in line:
                        passed_count += 1
                
                return {
                    'passed': max(passed_count, 1),
                    'failed': 0,
                    'errors': [],
                    'duration': duration,
                    'returncode': 0
                }
            else:
                print(f"❌ {test_name} FAILED")
                return {
                    'passed': 0,
                    'failed': 1,
                    'errors': [result.stderr] if result.stderr else ["Test execution failed"],
                    'duration': duration,
                    'returncode': result.returncode
                }
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ {test_name} TIMED OUT after {duration:.2f} seconds")
            return {
                'passed': 0,
                'failed': 1,
                'errors': [f"{test_name} timed out after {duration:.2f} seconds"],
                'duration': duration,
                'returncode': -1
            }
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 {test_name} CRASHED: {str(e)}")
            return {
                'passed': 0,
                'failed': 1,
                'errors': [f"{test_name} crashed: {str(e)}"],
                'duration': duration,
                'returncode': -1
            }
    
    def validate_environment(self) -> bool:
        """Validate test environment."""
        self.print_section("Validating Test Environment")
        
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 8):
            print("❌ Python 3.8+ required")
            return False
        print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # Check required packages
        required_packages = [
            'discord.py', 'pytest', 'pytest-asyncio', 'aiosqlite'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_').replace('.py', ''))
                print(f"✅ {package}")
            except ImportError:
                print(f"❌ {package} (missing)")
                missing_packages.append(package)
        
        if missing_packages:
            print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
            print("Install with: pip install " + " ".join(missing_packages))
            return False
        
        # Check test files exist
        test_files = [
            "tests/test_end_to_end_workflows.py",
            "tests/test_system_integration.py",
            "tests/test_final_integration.py"
        ]
        
        missing_files = []
        for test_file in test_files:
            if not Path(test_file).exists():
                print(f"❌ {test_file} (missing)")
                missing_files.append(test_file)
            else:
                print(f"✅ {test_file}")
        
        if missing_files:
            print(f"\n❌ Missing test files: {', '.join(missing_files)}")
            return False
        
        return True
    
    async def run_all_tests(self):
        """Run all integration tests."""
        self.print_header("DISCORD TICKET BOT - COMPREHENSIVE INTEGRATION TESTS")
        
        overall_start_time = time.time()
        
        # Validate environment
        if not self.validate_environment():
            print("\n❌ Environment validation failed. Cannot proceed with tests.")
            return False
        
        # Test suites to run
        test_suites = [
            {
                'type': 'pytest',
                'file': 'tests/test_end_to_end_workflows.py',
                'name': 'End-to-End Workflow Tests',
                'category': 'integration_tests'
            },
            {
                'type': 'pytest',
                'file': 'tests/test_system_integration.py',
                'name': 'System Integration Tests',
                'category': 'system_tests'
            },
            {
                'type': 'python',
                'file': 'tests/test_final_integration.py',
                'name': 'Final Integration Tests',
                'category': 'final_tests'
            }
        ]
        
        # Run each test suite
        for suite in test_suites:
            try:
                if suite['type'] == 'pytest':
                    result = self.run_pytest_suite(suite['file'], suite['name'])
                elif suite['type'] == 'python':
                    result = self.run_python_test_suite(suite['file'], suite['name'])
                
                # Store results
                category = suite['category']
                self.test_results[category]['passed'] += result['passed']
                self.test_results[category]['failed'] += result['failed']
                self.test_results[category]['errors'].extend(result['errors'])
                
            except Exception as e:
                print(f"💥 Failed to run {suite['name']}: {str(e)}")
                category = suite['category']
                self.test_results[category]['failed'] += 1
                self.test_results[category]['errors'].append(f"Failed to run {suite['name']}: {str(e)}")
        
        self.test_results['total_duration'] = time.time() - overall_start_time
        
        # Generate final report
        self.generate_final_report()
        
        # Return overall success
        total_failed = sum(cat['failed'] for cat in self.test_results.values() if isinstance(cat, dict))
        return total_failed == 0
    
    def generate_final_report(self):
        """Generate comprehensive final test report."""
        self.print_header("FINAL INTEGRATION TEST REPORT")
        
        # Calculate totals
        total_passed = 0
        total_failed = 0
        total_errors = []
        
        categories = ['integration_tests', 'system_tests', 'final_tests']
        
        for category in categories:
            if category in self.test_results:
                cat_data = self.test_results[category]
                total_passed += cat_data['passed']
                total_failed += cat_data['failed']
                total_errors.extend(cat_data['errors'])
        
        # Print summary
        print(f"📊 OVERALL RESULTS:")
        print(f"   Total Tests: {total_passed + total_failed}")
        print(f"   Passed: {total_passed} ✅")
        print(f"   Failed: {total_failed} ❌")
        
        if total_passed + total_failed > 0:
            success_rate = (total_passed / (total_passed + total_failed)) * 100
            print(f"   Success Rate: {success_rate:.1f}%")
        
        print(f"   Duration: {self.test_results['total_duration']:.2f} seconds")
        
        # Print category breakdown
        print(f"\n📋 CATEGORY BREAKDOWN:")
        for category in categories:
            if category in self.test_results:
                cat_data = self.test_results[category]
                cat_total = cat_data['passed'] + cat_data['failed']
                if cat_total > 0:
                    cat_success = (cat_data['passed'] / cat_total) * 100
                    status = "✅" if cat_data['failed'] == 0 else "❌"
                    print(f"   {category.replace('_', ' ').title()}: {cat_data['passed']}/{cat_total} ({cat_success:.1f}%) {status}")
        
        # Print errors if any
        if total_errors:
            print(f"\n❌ ERRORS ENCOUNTERED:")
            for i, error in enumerate(total_errors[:10], 1):  # Show first 10 errors
                print(f"   {i}. {error}")
            if len(total_errors) > 10:
                print(f"   ... and {len(total_errors) - 10} more errors")
        
        # Final verdict
        print(f"\n{'='*80}")
        if total_failed == 0:
            print("🎉 ALL INTEGRATION TESTS PASSED!")
            print("✅ The Discord Ticket Bot is ready for deployment.")
            print("✅ All requirements have been validated.")
            print("✅ Error handling and recovery mechanisms work correctly.")
            print("✅ Database operations perform well under load.")
            print("✅ Permission system is functioning properly.")
        else:
            print("⚠️  SOME INTEGRATION TESTS FAILED!")
            print("❌ Please review and fix issues before deployment.")
            print("🔧 Check the error messages above for specific issues.")
        print(f"{'='*80}")
    
    def save_report_to_file(self):
        """Save test report to file."""
        report_file = "integration_test_report.json"
        
        try:
            with open(report_file, 'w') as f:
                json.dump(self.test_results, f, indent=2, default=str)
            print(f"\n📄 Test report saved to: {report_file}")
        except Exception as e:
            print(f"\n⚠️  Failed to save report: {str(e)}")


async def main():
    """Main function to run integration tests."""
    runner = IntegrationTestRunner()
    
    try:
        success = await runner.run_all_tests()
        runner.save_report_to_file()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 Test runner crashed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Ensure we're in the right directory
    if not Path("bot.py").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    # Run the integration tests
    asyncio.run(main())