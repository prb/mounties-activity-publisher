from src.parsers.detail_parser import extract_activity_date
from lxml import html

def extract_activity_date_wrapper(date_str):
    # Create a dummy tree to pass to the function
    html_content = f"<html><body><div class='program-core'><ul class='details'><li>{date_str}</li></ul></div></body></html>"
    tree = html.fromstring(html_content)
    return extract_activity_date(tree)

def test_date_parsing():
    # Single day (should pass)
    date_str_single = "Tue, Feb 10, 2026"
    print(f"Testing single day: {date_str_single}")
    extract_activity_date_wrapper(date_str_single)
    print("PASS")

    # Multi day (should pass now)
    date_str_multi = "Wed, Feb 11, 2026 — Thu, Feb 12, 2026"
    print(f"Testing multi day: {date_str_multi}")
    try:
        extract_activity_date_wrapper(date_str_multi)
        print("PASS (Fixed)")
    except ValueError as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    test_date_parsing()
