import dash_mantine_components as dmc


def cbe_footer():
    # --- Top band: logos, nav links, socials, citation ---

    logos = dmc.Group(
        [
            dmc.Image(
                src="../assets/img/CBE-logo-2019-white.png",
                alt="CBE Logo",
                h=60,
            ),
            dmc.Image(
                src="../assets/img/UCB-logo-white-transparent.png",
                alt="UC Berkeley Logo",
                h=60,
            ),
        ],
        gap="md",
        align="center",
        justify="space-between",
        wrap="nowrap",
    )

    nav_links = dmc.Group(
        [
            dmc.Anchor(
                "Contact Us",
                href="https://cbe.berkeley.edu/about-us/contact/",
                target="_blank",
                underline=False,
                fz="md",
                c="white",
            ),
            dmc.Anchor(
                "Report Issues",
                href=(
                    "https://github.com/CenterForTheBuiltEnvironment/"
                    "cbe-tool-template/issues/new"
                    "?labels=bug&template=issue--bug-report.md"
                ),
                target="_blank",
                underline=False,
                fz="md",
                c="white",
            ),
        ],
        gap="xl",
        align="center",
    )

    social = dmc.Group(
        [
            dmc.Anchor(
                dmc.Image(
                    src="../assets/img/github-white-transparent.png",
                    alt="GitHub",
                    h=40,
                ),
                href="#",
            ),
            dmc.Anchor(
                dmc.Image(
                    src="../assets/img/linkedin-white-transparent.png",
                    alt="LinkedIn",
                    h=40,
                ),
                href="#",
            ),
        ],
        gap="lg",
    )

    citation = dmc.Stack(
        [
            dmc.Text(
                "Please cite us if you use this software:",
                fw=600,
                fz="sm",
            ),
            dmc.Group(
                [
                    dmc.Text("CITATION", fz="sm"),
                    dmc.Anchor(
                        "DOI",
                        href="link-to-doi",
                        target="_blank",
                        underline=False,
                        fz="sm",
                    ),
                ],
                gap="xs",
            ),
        ],
        gap="xs",
    )

    top_row = dmc.Group(
        [
            logos,
            nav_links,
            social,
            citation,
        ],
        justify="space-between",
        align="flex-start",
        gap="md",
        wrap="wrap",
        c="white",
    )

    # --- Bottom band: copyright + version/license ---

    copyright_text = dmc.Text(
        "Copyright © 2025 The Center for the Built Environment and UC Regents. "
        "All rights reserved.",
        fz="xs",
        c="dimmed",
    )

    version_and_license = dmc.Group(
        [
            dmc.Text("Version 1.00", fz="xs", c="dimmed"),
            dmc.Anchor(
                dmc.Image(
                    src="https://img.shields.io/badge/License-MIT-yellow.svg",
                    alt="License: MIT",
                    h=18,
                ),
                href="https://opensource.org/licenses/MIT",
            ),
        ],
        gap="sm",
        align="center",
    )

    bottom_row = dmc.Group(
        [
            copyright_text,
            version_and_license,
        ],
        justify="space-between",
        align="center",
        gap="md",
        wrap="wrap",
    )

    # --- Whole footer content (AppShellFooter wraps this) ---

    return dmc.Stack(
        [
            dmc.Box(  # top band
                top_row,
                bg="#0077c2",
                px="md",
                py="md",
                w="100%",
            ),
            dmc.Box(  # bottom band
                bottom_row,
                bg="#0c2772",
                px="md",
                py="xs",
                w="100%",
            ),
        ],
        gap=0,
        w="100%",
    )
