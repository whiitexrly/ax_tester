import base64

from playwright.async_api import ElementHandle, Page


async def get_element_screenshot(page: Page, element: ElementHandle, margin: int = 50) -> str | None:
    """Return a base64 screenshot of the element, or None on failure."""
    try:
        box = await element.bounding_box()
        if not box:
            return None

        # capture a padded clip around the focused element
        clip = {
            "x": max(0, box["x"] - margin),
            "y": max(0, box["y"] - margin),
            "width": box["width"] + margin * 2,
            "height": box["height"] + margin * 2,
        }

        shot = await page.screenshot(clip=clip)
        return base64.b64encode(shot).decode("ascii")
    except Exception:
        return None


async def get_page_screenshot(page: Page, full_page: bool = False) -> str | None:
    """Return a base64 screenshot of the page, or None on failure."""
    try:
        shot = await page.screenshot(full_page=full_page)
        return base64.b64encode(shot).decode("ascii")
    except Exception:
        return None
