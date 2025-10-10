from dash import html


def cbe_header():
    return html.Header(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Img(
                                src="../assets/img/logo-preliminary.png",
                                alt="tool-logo",
                            )
                        ],
                        className="tool-header-logo",
                    ),
                    # html.Div(
                    #     [html.A("Decarb Tool", href="/")], className="cbe-tool-title"
                    # ),
                    html.Nav(
                        [
                            html.A(
                                "About",
                                href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool/blob/main/README.md",
                                target="_blank",
                            ),
                            html.A(
                                "Documentation",
                                href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool/blob/main/docs/documentation-short.md",
                                target="_blank",
                            ),
                            html.A(
                                "Data",
                                href="#",
                                disable_n_clicks=True,
                                style={"color": "lightgrey"},
                            ),
                        ],
                        className="cbe-header-nav",
                    ),
                ],
                className="cbe-header-content",
            )
        ]
    )
