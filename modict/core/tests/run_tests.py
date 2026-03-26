"""
Script to run all tests for modict.
"""
import pytest
import sys
import os
import argparse

def run_tests_with_coverage(verbose=False, html_report=False):
    import coverage
    """Run tests with coverage measurement."""
    # Start coverage measurement
    cov = coverage.Coverage(
        source=['modict'],
        omit=['*/tests/*', '*/site-packages/*']
    )
    cov.start()

    # Discover and run tests
    verbosity = 2 if verbose else 1
    exit_code = pytest.main(['--verbose'] if verbose else [])
    
    # Stop coverage measurement
    cov.stop()
    cov.save()
    
    # Report coverage
    print("\nCoverage Summary:")
    cov.report()
    
    # Generate HTML report if requested
    if html_report:
        html_dir = os.path.join('tests', 'htmlcov')
        cov.html_report(directory=html_dir)
        print(f"\nHTML coverage report generated in {html_dir}")
    
    return exit_code


def run_tests(verbose=False):
    """Run tests without coverage measurement."""
    verbosity = 2 if verbose else 1
    return pytest.main(['--verbose'] if verbose else [])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run tests for modict')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-c', '--coverage', action='store_true', help='Run with coverage measurement')
    parser.add_argument('--html', action='store_true', help='Generate HTML coverage report')
    
    args = parser.parse_args()
    
    if args.coverage:
        try:
            exit_code = run_tests_with_coverage(args.verbose, args.html)
        except ImportError:
            print("Error: The 'coverage' package is required to run tests with coverage.")
            print("Install it with: pip install coverage")
            exit_code = 1
    else:
        exit_code = run_tests(args.verbose)
    
    sys.exit(exit_code)