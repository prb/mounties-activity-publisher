"""Parser for Mountaineers activity detail pages."""

from datetime import datetime
from lxml import html
import pytz
from dateutil import parser as date_parser

from ..models import Activity, Leader, Place


def parse_activity_detail(html_content: str, activity_url: str) -> Activity:
    """
    Parse activity detail page and extract all fields.

    Args:
        html_content: Raw HTML content from activity detail page
        activity_url: The URL of the activity (used as permalink)

    Returns:
        Activity object with all fields populated

    Example:
        >>> html = '<html>...</html>'
        >>> activity = parse_activity_detail(html, 'https://example.com/activity-1')
        >>> activity.title is not None
        True
    """
    tree = html.fromstring(html_content)

    # Extract basic fields
    title = extract_title(tree)
    description = extract_description(tree)
    activity_date = extract_activity_date(tree)
    difficulty_rating = extract_difficulty_rating(tree)

    # Extract leader information
    leader = extract_leader(tree)

    # Extract place information
    place = extract_place(tree)

    return Activity(
        activity_permalink=activity_url,
        title=title,
        description=description,
        difficulty_rating=difficulty_rating,
        activity_date=activity_date,
        place=place,
        leader=leader,
    )


def extract_title(tree) -> str:
    """
    Extract activity title.

    XPath: //*[@class='documentFirstHeading']/text()
    """
    title_nodes = tree.xpath("//*[@class='documentFirstHeading']/text()")
    if not title_nodes:
        raise ValueError("Could not find activity title")

    # Join and clean whitespace
    return ' '.join(''.join(title_nodes).split())


def extract_description(tree) -> str:
    """
    Extract activity description.

    XPath: //p[@class='documentDescription']/text()
    """
    desc_nodes = tree.xpath("//p[@class='documentDescription']/text()")
    if not desc_nodes:
        return ""

    # Join and clean whitespace
    return ' '.join(''.join(desc_nodes).split())


def extract_activity_date(tree) -> datetime:
    """
    Extract and parse activity date, converting from Pacific time to UTC.

    XPath: //div[@class='program-core']/ul[@class='details'][1]/li[1]/text()
    Format: %a, %b %d, %Y (e.g., "Tue, Feb 10, 2026")
    """
    date_nodes = tree.xpath("//div[@class='program-core']/ul[@class='details'][1]/li[1]/text()")
    if not date_nodes:
        raise ValueError("Could not find activity date")

    date_str = date_nodes[0].strip()

    # Parse the date (assumes Pacific time)
    pacific = pytz.timezone('America/Los_Angeles')
    naive_date = datetime.strptime(date_str, "%a, %b %d, %Y")

    # Localize to Pacific time, then convert to UTC
    pacific_date = pacific.localize(naive_date)
    utc_date = pacific_date.astimezone(pytz.UTC)

    return utc_date


def extract_difficulty_rating(tree) -> list[str]:
    """
    Extract difficulty rating(s).

    XPath: //div[@class='program-core']/ul[@class='details'][2]/li[1]//text()
    Returns: List of difficulty ratings (comma-delimited, whitespace trimmed)
    Note: The XPath returns text including "Difficulty:" label which needs to be stripped.
    """
    text_nodes = tree.xpath("//div[@class='program-core']/ul[@class='details'][2]/li[1]//text()")
    if not text_nodes:
        return []

    # Join all text nodes and strip
    full_text = ''.join(text_nodes).strip()

    # Remove "Difficulty:" prefix if present
    if full_text.startswith("Difficulty:"):
        full_text = full_text[len("Difficulty:"):].strip()

    # Split by comma and clean each item
    ratings = [r.strip() for r in full_text.split(',') if r.strip()]

    return ratings


def extract_leader(tree) -> Leader:
    """
    Extract leader information.

    XPaths:
      - Name: //div[@class='leaders']/div[@class='roster-contact']/div[not(@class)]/text()
      - Image: //div[@class='leaders']/div[@class='roster-contact']/img/@src
    """
    # Extract leader name
    name_nodes = tree.xpath("//div[@class='leaders']/div[@class='roster-contact']/div[not(@class)]/text()")
    if not name_nodes:
        raise ValueError("Could not find leader name")

    leader_name = name_nodes[0].strip()

    # Extract leader image URL (contains the profile URL before @@)
    img_nodes = tree.xpath("//div[@class='leaders']/div[@class='roster-contact']/img/@src")
    if not img_nodes:
        raise ValueError("Could not find leader image URL")

    img_url = img_nodes[0].strip()

    # Extract the profile URL (everything before @@)
    if '@@' in img_url:
        leader_permalink = img_url.split('@@')[0]
    else:
        # Fallback: try to construct from image URL pattern
        raise ValueError(f"Could not extract leader permalink from image URL: {img_url}")

    return Leader(
        leader_permalink=leader_permalink,
        name=leader_name,
    )


def extract_place(tree) -> Place:
    """
    Extract place/route information.

    XPaths:
      - Name: //div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']/h3/text()
      - URL: //div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']//a[contains(.,'See full')]/@href
    """
    # Extract place name
    name_nodes = tree.xpath(
        "//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']/h3/text()"
    )
    if not name_nodes:
        raise ValueError("Could not find place name")

    place_name = ''.join(name_nodes).strip()

    # Extract place URL
    url_nodes = tree.xpath(
        "//div[@class='tab-title' and contains(string(.),'Route/Place')]/following-sibling::div[@class='tab-content']//a[contains(.,'See full')]/@href"
    )
    if not url_nodes:
        raise ValueError("Could not find place URL")

    place_url = url_nodes[0].strip()

    return Place(
        place_permalink=place_url,
        name=place_name,
    )
