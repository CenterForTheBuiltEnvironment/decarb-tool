import dash_mantine_components as dmc


def shell_header():
    burger = dmc.Burger(
        id="burger",
        size="sm",
        opened=True,
    )

    logo = dmc.Image(
        src="../assets/img/logo-preliminary.png",
        alt="tool-logo",
        h=80,
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
        [header_group],
        justify="space-between",
        align="center",
        gap="md",
        h="100%",
        w="100%",
        px="md",
    )
