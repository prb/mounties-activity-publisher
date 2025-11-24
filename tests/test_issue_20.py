
from lxml import html
from src.parsers.detail_parser import extract_activity_date
import pytest

def test_reproduce_issue_20():
    # The error message suggests the date string looks like:
    # "Thu, Jul 30, 2026 - Fri, Jul 31, 2026"
    # The current code only splits on "—" (em-dash)
    
    date_str = "Thu, Jul 30, 2026 - Fri, Jul 31, 2026"
    html_content = f"""
    <div class="program-core">
        <ul class="details">
            <li>{date_str}</li>
        </ul>
    </div>
    """
    tree = html.fromstring(html_content)
    
    # Should not raise ValueError anymore
    try:
        date = extract_activity_date(tree)
        assert date is not None
        print("Successfully parsed date!")
    except ValueError as e:
        pytest.fail(f"Should not have raised ValueError: {e}")

if __name__ == "__main__":
    test_reproduce_issue_20()
