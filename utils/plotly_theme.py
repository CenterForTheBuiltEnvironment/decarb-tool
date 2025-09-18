import plotly.io as pio

custom_colors = (
    "#277da1",
    "#577590",
    "#4d908e",
    "#43aa8b",
    "#90be6d",
    "#f9c74f",
    "#f9844a",
    "#f8961e",
    "#f3722c",
    "#f94144",
)

extended_custom_colors = (
    # Original Colors
    "#277da1",
    "#577590",
    "#4d908e",
    "#43aa8b",
    "#90be6d",
    "#f9c74f",
    "#f9844a",
    "#f8961e",
    "#f3722c",
    "#f94144",
    # Pastel Variations
    "#a8dce2",  # Pastel version of #277da1
    "#b3bfc9",  # Pastel version of #577590
    "#a8cfc9",  # Pastel version of #4d908e
    "#a8dfd2",  # Pastel version of #43aa8b
    "#d2e8c0",  # Pastel version of #90be6d
    "#fde7a6",  # Pastel version of #f9c74f
    "#f9cfbd",  # Pastel version of #f9844a
    "#fbd3a7",  # Pastel version of #f8961e
    "#f9b39c",  # Pastel version of #f3722c
    "#f9a3a5",  # Pastel version of #f94144
)


custom_template = pio.templates["ggplot2"].update(
    layout_colorway=extended_custom_colors,
    layout_plot_bgcolor="rgba(0,0,0,0)",
    layout_paper_bgcolor="rgba(0,0,0,0)",
    layout_font=dict(family="Helvetica, sans-serif", size=14, color="black"),
)

pio.templates["decarb-tool-theme"] = custom_template
pio.templates.default = "decarb-tool-theme"
