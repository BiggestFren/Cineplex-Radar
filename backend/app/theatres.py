from __future__ import annotations

from typing import Final


# Current Cineplex locations whose official theatre pages list a Toronto address.
# Keep this server-side so the Android app can receive catalogue updates without
# changing its UI or storage format.
TORONTO_THEATRES: Final[tuple[dict[str, str], ...]] = (
    {
        "name": "Cineplex Cinemas Yonge-Dundas and VIP",
        "address": "10 Dundas Street East, Suite 402",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-yongedundas-and-vip",
    },
    {
        "name": "Scotiabank Theatre Toronto",
        "address": "259 Richmond Street West",
        "city": "Toronto",
        "province": "ON",
        "slug": "scotiabank-theatre-toronto",
    },
    {
        "name": "Cineplex Cinemas Varsity and VIP",
        "address": "55 Bloor Street West",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-varsity-and-vip",
    },
    {
        "name": "Cineplex Cinemas Yonge-Eglinton and VIP",
        "address": "2300 Yonge Street",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-yongeeglinton-and-vip",
    },
    {
        "name": "Cineplex VIP Cinemas Don Mills (age restricted 19+)",
        "address": "12 Marie Labatte Road, Unit B7",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-vip-cinemas-don-mills-age-restricted-19",
    },
    {
        "name": "Cineplex Cinemas Empress Walk",
        "address": "5095 Yonge Street, 3rd Floor",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-empress-walk",
    },
    {
        "name": "Cineplex Cinemas Yorkdale",
        "address": "3401 Dufferin Street",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-yorkdale",
    },
    {
        "name": "Cineplex Cinemas Fairview Mall",
        "address": "1800 Sheppard Avenue East, Unit Y007",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-fairview-mall",
    },
    {
        "name": "Cineplex Cinemas Scarborough",
        "address": "300 Borough Drive",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-scarborough",
    },
    {
        "name": "Cineplex Odeon Eglinton Town Centre Cinemas",
        "address": "22 Lebovic Avenue",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-odeon-eglinton-town-centre-cinemas",
    },
    {
        "name": "Cineplex Odeon Morningside Cinemas",
        "address": "785 Milner Avenue",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-odeon-morningside-cinemas",
    },
    {
        "name": "Cineplex Cinemas Queensway and VIP",
        "address": "1025 The Queensway",
        "city": "Toronto",
        "province": "ON",
        "slug": "cineplex-cinemas-queensway-and-vip",
    },
)


def toronto_theatre_names() -> list[str]:
    return [item["name"] for item in TORONTO_THEATRES]
