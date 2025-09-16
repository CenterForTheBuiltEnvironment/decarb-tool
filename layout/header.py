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
                            html.A("About", href="about.html"),
                            html.A("Documentation", href="#"),
                            html.A("Data", href="#"),
                        ],
                        className="cbe-header-nav",
                    ),
                ],
                className="cbe-header-content",
            )
        ]
    )
