import dash_mantine_components as dmc


def cbe_header():
    burger = dmc.Burger(
        id="burger",
        size="sm",
        opened=False,
    )

    # ---- alpha badge ----
    alpha_badge = dmc.Badge(
        "Alpha Version",
        color="red",
        variant="filled",
        radius="sm",
        style={"marginTop": 10},
    )

    logo = dmc.Image(
        src="../assets/img/logo-preliminary.png",
        alt="tool-logo",
        h=100,  # you can tune this down later if needed
        fit="contain",
        style={"display": "block"},
    )

    header_group = dmc.Group(
        [burger, logo],
        gap="md",
        justify="flex-start",
        align="center",
        wrap="nowrap",
    )

    return dmc.Group(
        [header_group, alpha_badge],
        justify="space-between",
        align="center",
        gap="md",
        h="100%",
        w="100%",
        px="md",
    )
