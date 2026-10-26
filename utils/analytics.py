"""Usage tracking (Google Analytics 4 + UC Berkeley Siteimprove), injected into the page <head>.

Tracking only loads when ENABLE_ANALYTICS=true (set in the Dockerfile for production),
so local development runs do not show up in the statistics.
"""

import os

# GA4 measurement ID of the decarb-tool property; GA_MEASUREMENT_ID overrides it.
# Empty until the property is created, in which case only Siteimprove loads.
GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", "")

SITEIMPROVE_SRC = "https://siteimproveanalytics.com/js/siteanalyze_6294756.js"

GTAG_SNIPPET = """<!-- Global site tag (gtag.js) - Google Analytics -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=__GA_ID__"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '__GA_ID__');
        </script>"""

SITEIMPROVE_SNIPPET = f"""<!-- Siteimprove Analytics -->
        <script async src="{SITEIMPROVE_SRC}"></script>"""


def analytics_enabled() -> bool:
    return os.environ.get("ENABLE_ANALYTICS", "false").lower() == "true"


def build_analytics_head(ga_id: str | None) -> str:
    """HTML for the tracking scripts; the GA block is skipped without a measurement ID."""
    snippets = [GTAG_SNIPPET.replace("__GA_ID__", ga_id)] if ga_id else []
    snippets.append(SITEIMPROVE_SNIPPET)
    return "\n        ".join(snippets)


def add_analytics(index_string: str, enabled: bool, ga_id: str | None) -> str:
    """Insert the tracking scripts at the top of <head> in a Dash index string."""
    if not enabled:
        return index_string
    return index_string.replace("<head>", "<head>\n        " + build_analytics_head(ga_id), 1)
