# Add this to your settings.py file in your Django project folder.

FLLFMS = {
    'EVENT_NAME': "My FLL Event",

    # ########### WARNING ########### #
    # ONCE YOU HAVE POPULATED YOUR DATABASE
    # IF YOU EDIT THESE VALUES, ONLY ADD, DO NOT REORDER OR REMOVE ANY
    # DOING SO WILL ALTER THE EXISTING ENUMERATED VALUES
    # BUT WILL NOT UPDATE THE DATABASE, LEADING TO INVALID DATA.
    # Alternatively, manually specify the choice numbers, and eliminate the
    # enumeration altogether. e.g. [(1, "playoff"), (3, "qualification")]

    # Table pairs, named after FRC fields.
    'FIELDS': list(enumerate([
        # Tables
        "A",
        "B",
        "C",
    ])),

    # Table sides, named after player stations from FRC.
    'STATIONS': list(enumerate([
        "1",
        "2",
    ])),

    # Only keep the tournaments you intend to use at an event. Place them in
    # in reverse order, so the first tournament is at the bottom of the list.
    # This is used to sort them automatically. Names are again inspired by FRC.
    # These should be capitalised as you intend them to appear.
    'TOURNAMENTS': list(enumerate([
        # "Finals",
        "Ranking",
        "Practice",
    ]))
}
