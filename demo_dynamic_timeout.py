"""
Demonstration of dynamic timeout functionality based on file size.
"""

import tempfile
import os
from src.core.utils import calculate_dynamic_timeout


def demonstrate_dynamic_timeouts():
    """Demonstrate how timeouts scale with file size."""
    print("Dynamic Timeout Scaling Based on File Size")
    print("=" * 50)
    
    # Test with different file sizes
    test_sizes = [
        ("1 KB", 1024),
        ("10 KB", 1024 * 10),
        ("100 KB", 1024 * 100),
        ("1 MB", 1024 * 1024),
        ("4 MB", 4 * 1024 * 1024),
        ("10 MB", 10 * 1024 * 1024),
        ("50 MB", 50 * 1024 * 1024),
        ("100 MB", 100 * 1024 * 1024),
    ]
    
    base_timeout = 300  # 5 minutes base for 1MB file
    min_timeout = 30    # 30 seconds minimum
    max_timeout = 3600  # 1 hour maximum
    
    print(f"Base timeout: {base_timeout}s for 1MB file")
    print(f"Min timeout: {min_timeout}s")
    print(f"Max timeout: {max_timeout}s")
    print()
    
    for size_name, size_bytes in test_sizes:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write content of specified size
            content = b"x" * size_bytes
            temp_file.write(content)
            temp_file.flush()
            
            try:
                calculated_timeout = calculate_dynamic_timeout(
                    temp_file.name, 
                    base_timeout=base_timeout,
                    min_timeout=min_timeout,
                    max_timeout=max_timeout
                )
                
                print(f"File size: {size_name:6s} -> Timeout: {calculated_timeout:4d}s "
                      f"(factor: {calculated_timeout/base_timeout:.2f}x)")
            finally:
                os.unlink(temp_file.name)
    
    print()
    print("Key Features:")
    print("- Timeouts scale with square root of file size to prevent extremely long timeouts")
    print("- Small files get minimum timeout to avoid unnecessary delays")
    print("- Large files get proportionally longer timeouts for processing")
    print("- All timeouts are clamped between minimum and maximum values")


def demonstrate_practical_impact():
    """Demonstrate the practical impact of dynamic timeouts."""
    print("\nPractical Impact of Dynamic Timeouts")
    print("=" * 40)
    
    print("BEFORE (fixed timeout):")
    print("  • Small files: Get same long timeout as large files (wasteful)")
    print("  • Large files: May timeout too early with fixed short timeout")
    print("  • Medium files: May timeout too early with conservative timeout")
    print()
    
    print("AFTER (dynamic timeout):")
    print("  • Small files: Get shorter, appropriate timeouts")
    print("  • Large files: Get longer, appropriate timeouts")
    print("  • All files: Processed with optimal timeout for their size")
    print()
    
    print("Benefits:")
    print("  • Improved success rate for large files")
    print("  • Reduced waiting time for small files")
    print("  • Better resource utilization")
    print("  • More predictable processing times")


if __name__ == "__main__":
    demonstrate_dynamic_timeouts()
    demonstrate_practical_impact()