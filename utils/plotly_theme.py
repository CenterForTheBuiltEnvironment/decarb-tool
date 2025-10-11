import plotly.io as pio

custom_colors = (
    "#004AAE",
    "#9FD1FF",
    "#018943",
    "#B3E59A",
    "#FFC31B",
    "#FFE88D",
    "#E7115E",
    "#FFCFE5",
    "#8236C7",
    "#D9CEFF",
)

extended_custom_colors = (
    "#004AAE",
    "#9FD1FF",
    "#018943",
    "#B3E59A",
    "#FFC31B",
    "#FFE88D",
    "#E7115E",
    "#FFCFE5",
    "#8236C7",
    "#D9CEFF",
)


custom_template = pio.templates["ggplot2"].update(
    layout_colorway=extended_custom_colors,
    layout_plot_bgcolor="rgba(0,0,0,0)",
    layout_paper_bgcolor="rgba(0,0,0,0)",
    layout_font=dict(family="Helvetica, sans-serif", size=14, color="black"),
)

pio.templates["decarb-tool-theme"] = custom_template
pio.templates.default = "decarb-tool-theme"
