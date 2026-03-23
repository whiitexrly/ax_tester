import logging
from typing import Any

from playwright.async_api import CDPSession, ElementHandle

_EMPTY_AX: dict[str, Any] = {"role": None, "name": None, "description": None, "properties": {}}

logger = logging.getLogger(__name__)


async def get_backend_dom_node_id_for_object_id(cdp: CDPSession, object_id: str) -> int | None:
    """Return backendDOMNodeId for a given Runtime objectId via CDP."""
    try:
        desc = await cdp.send("DOM.describeNode", {"objectId": object_id})
        return desc.get("node", {}).get("backendNodeId")
    except Exception:
        return None


async def get_backend_dom_node_id(cdp: CDPSession, element: ElementHandle) -> int | None:
    """Return backendDOMNodeId for a Playwright element via CDP."""
    tmp_key = "__pw_backend_id_113"
    object_id: str | None = None
    try:
        await element.evaluate("(node, key) => { globalThis[key] = node; }", tmp_key)
        remote = await cdp.send(
            "Runtime.evaluate",
            {"expression": f"globalThis[{tmp_key!r}]", "returnByValue": False},
        )
        object_id = remote.get("result", {}).get("objectId")
        if not object_id:
            return None
        return await get_backend_dom_node_id_for_object_id(cdp, object_id)
    finally:  # cleanup
        await delete_global_key(cdp, tmp_key)
        await release_remote_object(cdp, object_id)


async def get_ax_info_cdp(cdp: CDPSession, element: ElementHandle) -> dict[str, Any]:
    """Fetch basic accessibility info for a Playwright element via CDP.

    Stores the element on a temporary `globalThis` key, resolves a remote
    object id, queries `Accessibility.getPartialAXTree` (no relatives),

    Args:
        element: Playwright element handle to inspect.
        cdp: Connected CDP session (e.g., `page.context.new_cdp_session`).

    Returns:
        Dict with `role`, `name`, `description` and `properties` keys (values may be `None`).

    Example:
        >>> browser = await playwright.chromium.launch(headless=False, slow_mo=1)
        >>> context = await browser.new_context()
        >>> page = await context.new_page()
        >>> await page.goto(URL, wait_until="networkidle")
        >>> cdp = await page.context.new_cdp_session(page)
        >>> handle = await page.evaluate_handle("() => document.activeElement")
        >>> element = handle.as_element()
        >>> ax_info = get_ax_info_cdp(cdp, element)

    """
    tmp_key = "__pw_ax_113"
    object_id: str | None = None

    try:
        # store element on global to access via CDP
        await element.evaluate("(node, key) => { globalThis[key] = node; }", tmp_key)
        remote = await cdp.send(
            "Runtime.evaluate",
            {"expression": f"globalThis[{tmp_key!r}]", "returnByValue": False},
        )
        object_id = remote.get("result", {}).get("objectId")
        if not object_id:
            return dict(_EMPTY_AX)

        # request AX tree for this node only
        ax = await cdp.send(
            "Accessibility.getPartialAXTree",
            {"objectId": object_id, "fetchRelatives": False},
        )
        nodes = ax.get("nodes", [])
        if not nodes:
            return dict(_EMPTY_AX)

        # pick best matching node from response
        target = nodes[0]
        if len(nodes) > 1:
            # if multiple nodes are returned -> try to match the DOM backend id
            backend_node_id = await get_backend_dom_node_id_for_object_id(cdp, object_id)
            if backend_node_id is not None:
                for node in nodes:
                    if node.get("backendDOMNodeId") == backend_node_id:
                        target = node
                        break

        properties = {}
        for prop in target.get("properties", []):
            value = prop.get("value", {}).get("value")
            properties[prop.get("name")] = value

        return {
            "role": target.get("role", {}).get("value"),
            "name": target.get("name", {}).get("value"),
            "description": target.get("description", {}).get("value"),
            "properties": properties,
        }
    except Exception:
        logger.error(f"Unable to extract ax info from element {element}", exc_info=True)
        return dict(_EMPTY_AX)
    finally:  # cleanup
        await delete_global_key(cdp, tmp_key)
        await release_remote_object(cdp, object_id)


# --- clean up functions ---
async def release_remote_object(cdp: CDPSession, object_id: str) -> None:
    """Release a Runtime objectId if present, ignoring errors."""
    try:
        await cdp.send("Runtime.releaseObject", {"objectId": object_id})
    except Exception:
        pass


async def delete_global_key(cdp: CDPSession, key: str) -> None:
    """Delete a globalThis key if present, ignoring errors."""
    try:
        await cdp.send(
            "Runtime.evaluate",
            {"expression": f"delete globalThis[{key!r}]", "returnByValue": True},
        )
    except Exception:
        pass
