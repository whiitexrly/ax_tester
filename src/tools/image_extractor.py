import asyncio
import logging
import re
import threading

from playwright.async_api import async_playwright

from tools.base import Tool, ToolExecutionError, ToolResult, ToolStatus

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"url\([\'\"](.*?)[\'\"]\)")

JS_COLLECT = r"""
() => {
  function getAltLike(el) {
    // priority: alt (img) -> aria-label -> aria-labelledby -> figcaption/closest figure -> title

    // alt
    if (el.tagName === 'IMG') {
      const alt = el.getAttribute('alt');
      if (alt !== null) return alt; // can be empty
    }

    // aria-label
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel) return ariaLabel;

    // aria-labelledby
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const ids = labelledBy.split(/\s+/).filter(Boolean);
      const text = ids
        .map(id => document.getElementById(id))
        .filter(Boolean)
        .map(n => (n.innerText || n.textContent || '').trim())
        .filter(Boolean)
        .join(' ');
      if (text) return text;
    }

    // figcaption
    const figure = el.closest('figure');
    if (figure) {
      const fc = figure.querySelector('figcaption');
      if (fc) {
        const t = (fc.innerText || fc.textContent || '').trim();
        if (t) return t;
      }
    }

    // title
    const title = el.getAttribute('title');
    if (title) return title;

    return null;
  }

  function selectorFor(el) {
    // light selector for debugging
    if (!el) return null;
    const id = el.getAttribute && el.getAttribute('id');
    if (id) return `#${CSS.escape(id)}`;
    const cls = el.getAttribute && el.getAttribute('class');
    if (cls) {
      const c = cls.split(/\s+/).filter(Boolean)[0];
      if (c) return `${el.tagName.toLowerCase()}.${CSS.escape(c)}`;
    }
    return el.tagName ? el.tagName.toLowerCase() : null;
  }

  const results = [];

  // 1) <img>
  document.querySelectorAll('img').forEach(img => {
    results.push({
      type: 'img',
      url: img.currentSrc || img.src || null,
      alt_text: getAltLike(img),
      source_selector: selectorFor(img)
    });
  });

  // 2) SVG <image href=...> (rare but possible)
  document.querySelectorAll('svg image').forEach(im => {
    const href = im.getAttribute('href') || im.getAttribute('xlink:href');
    results.push({
      type: 'svg-image',
      url: href,
      alt_text: getAltLike(im),
      source_selector: selectorFor(im)
    });
  });

  // 3) Elements with CSS background-image (including role="img")
  const all = Array.from(document.querySelectorAll('body *'));
  for (const el of all) {
    const cs = getComputedStyle(el);
    const bg = cs.backgroundImage;
    if (bg && bg !== 'none' && bg.includes('url(')) {
      results.push({
        type: 'css-background',
        url: bg, // keep raw; parse in python to extract url(...)
        alt_text: getAltLike(el),
        source_selector: selectorFor(el)
      });
    }

    // pseudo-elements
    const b1 = getComputedStyle(el, '::before').backgroundImage;
    if (b1 && b1 !== 'none' && b1.includes('url(')) {
      results.push({
        type: 'css-background::before',
        url: b1,
        alt_text: getAltLike(el),
        source_selector: selectorFor(el)
      });
    }
    const b2 = getComputedStyle(el, '::after').backgroundImage;
    if (b2 && b2 !== 'none' && b2.includes('url(')) {
      results.push({
        type: 'css-background::after',
        url: b2,
        alt_text: getAltLike(el),
        source_selector: selectorFor(el)
      });
    }

    // content: url(...) on pseudo-elements
    const c1 = getComputedStyle(el, '::before').content;
    if (c1 && c1.startsWith('url(')) {
      results.push({
        type: 'css-content::before',
        url: c1,
        alt_text: getAltLike(el),
        source_selector: selectorFor(el)
      });
    }
    const c2 = getComputedStyle(el, '::after').content;
    if (c2 && c2.startsWith('url(')) {
      results.push({
        type: 'css-content::after',
        url: c2,
        alt_text: getAltLike(el),
        source_selector: selectorFor(el)
      });
    }
  }

  return results;
}
"""


class ImageExtractor(Tool):
    """Extract images and image-like resources from a webpage using Playwright."""

    def __init__(self, config=None):
        super().__init__(config)
        self.wait_ms = self.config.get("wait_ms", 2000)
        self.headless = self.config.get("headless", True)
        self.wait_for = self.config.get("wait_for", "networkidle")
        self.timeout = self.config.get("timeout", 30)

    def execute(self, url: str, **kwargs) -> ToolResult:
        logger.info(
            f"Extracting images from {url} with wait_ms={self.wait_ms}, headless={self.headless}, wait_for={self.wait_for}, timeout={self.timeout}"
        )

        try:
            url = self.validate_url(url)

            wait_ms = kwargs.get("wait_ms", self.wait_ms)
            timeout = kwargs.get("timeout", self.timeout)

            result = self._run_async(self._extract_images_async(url, wait_ms, timeout))

            return ToolResult(
                tool_name="image-extractor",
                status=ToolStatus.SUCCESS,
                data=result,
                metadata={"url": url},
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in image extractor for {url}")
            return ToolResult(
                tool_name="image-extractor",
                status=ToolStatus.FAILURE,
                data={},
                error=str(e),
                metadata={"url": url},
            )

    def _run_async(self, coro):
        """Run an async coroutine safely from sync code, even if an event loop exists."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result_holder = {}
        error_holder = {}

        def _runner():
            try:
                result_holder["value"] = asyncio.run(coro)
            except Exception as e:
                error_holder["error"] = e

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder.get("value")

    async def _extract_images_async(self, page_url: str, wait_ms: int, timeout: int) -> dict:
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                await page.goto(
                    page_url,
                    wait_until=self.wait_for,
                    timeout=timeout * 1000,
                )
                await page.wait_for_timeout(wait_ms)

                raw = await page.evaluate(JS_COLLECT)

                out = []
                for item in raw:
                    url_raw = item.get("url")
                    if not url_raw:
                        continue
                    if "https://" not in url_raw and "http://" not in url_raw:
                        continue
                    if item["type"].startswith("css-") and isinstance(url_raw, str):
                        extracted = self._extract_url(url_raw)
                        url = extracted
                    else:
                        url = url_raw

                    if url in (None, "", "about:blank"):
                        continue

                    out.append(
                        {
                            "type": item.get("type"),
                            "url": url,
                            "alt_text": item.get("alt_text"),
                            "source_selector": item.get("source_selector"),
                        }
                    )

            except Exception as e:
                logger.exception(f"Playwright execution error for {page_url}")
                raise ToolExecutionError(f"Playwright error: {e!s}") from e

            finally:  # close browser
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

        # deduplication
        dedup = {}
        for x in out:
            key = (x["url"], x.get("alt_text"), x.get("type"))
            dedup[key] = x

        return {
            "page_url": page_url,
            "images": list(dedup.values()),
        }

    def _extract_url(self, css_value: str):
        if not css_value:
            return None
        m = URL_RE.search(css_value)
        return m.group(1) if m else None


# sample usage for testing/debugging
if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO)

    # default = "https://apple.com"
    default_url = "https://shop.reply.com"
    url = default_url if len(sys.argv) < 2 else sys.argv[1]

    result = ImageExtractor().execute(url).data

    assert type(result) is dict, f"Expected dict, got {type(result)}"
    assert type(result["images"]) is list, f"Expected list, got {type(result['images'])}"
    assert type(result["images"][0]) is dict, f"Expected dict, got {type(result['images'][0])}"
    print(json.dumps(result, indent=2, ensure_ascii=False))
