"""
AirRev Engine — Rent Insight Service
LTR rent estimates by community + bedroom count

Data source: Calgary Community Rent Breakdown (April 2026) + Airdrie/Chestermere/Okotoks
             Rent Report (May 2026). Compiled from RentFaster, Zumper, Apartments.com,
             liv.rent, CMHC, and active listing data.

Refresh cadence: Quarterly (Feb / May / Aug / Nov). Update RENT_DATA_VINTAGE below
                 and re-run the data collection script when refreshing.

Format: community_key -> {bedrooms: (low, avg, high)}
  - bedrooms: 0=studio, 1, 2, 3, 4
  - all figures CAD/month, unfurnished, April 2026 unless noted
  - community_key: lowercase, spaces stripped to match DDF CommunityName
"""

from typing import Dict, Optional, Tuple
from app.models.schemas import RentInsightResponse
from datetime import datetime

RENT_DATA_VINTAGE = "2026-04"  # Update when data is refreshed


# ─────────────────────────────────────────────────────────────────────────────
# CALGARY — 80+ communities, April 2026
# Sources: liv.rent, RentFaster, Zumper, Apartments.com, CMHC
# ─────────────────────────────────────────────────────────────────────────────

CALGARY_RENT_DATA: Dict[str, Dict[int, Tuple[float, float, float]]] = {

    # ── City Centre / Inner City ──────────────────────────────────────────────
    "Downtown East Village": {
        1: (1800, 2136, 2200),
        2: (2200, 2650, 3100),
        3: (3000, 3500, 4000),
    },
    "Downtown Commercial Core": {
        1: (1700, 1965, 2100),
        2: (2100, 2450, 2800),
        3: (2800, 3400, 4000),
    },
    "Eau Claire": {
        1: (1500, 1625, 1750),
        2: (1900, 2150, 2400),
    },
    "Beltline": {
        0: (1400, 1650, 1950),
        1: (1600, 1871, 2000),
        2: (2100, 2450, 2800),
        3: (3000, 3375, 3750),
    },
    "Cliff Bungalow": {
        1: (1800, 2001, 2200),
        2: (2400, 2600, 2800),
        3: (3000, 3250, 3500),
    },
    "Mission": {
        0: (1350, 1550, 1850),
        1: (1700, 1955, 2100),
        2: (2100, 2450, 2800),
        3: (2800, 3150, 3500),
    },
    "Kensington": {
        0: (1300, 1500, 1800),
        1: (1900, 1950, 2000),
        2: (2200, 2450, 2700),
        3: (2800, 3150, 3500),
    },
    "Hillhurst": {
        1: (1900, 1950, 2000),
        2: (2200, 2450, 2700),
        3: (2800, 3150, 3500),
    },
    "Bridgeland": {
        0: (1300, 1500, 1800),
        1: (1530, 1885, 2000),
        2: (1900, 2330, 2760),
        3: (2850, 3175, 3500),
    },
    "Inglewood": {
        0: (1250, 1450, 1750),
        1: (1600, 1846, 1988),
        2: (2000, 2300, 2600),
        3: (2500, 2850, 3200),
    },
    "Ramsay": {
        1: (1700, 1892, 2000),
        2: (2000, 2250, 2500),
    },
    "Bankview": {
        0: (1000, 1200, 1500),
        1: (1200, 1418, 1600),
        2: (1500, 1750, 2000),
    },
    "Sunalta": {
        1: (1350, 1487, 1600),
        2: (1600, 1800, 2000),
    },
    "Lower Mount Royal": {
        1: (1400, 1548, 1700),
        2: (1700, 1950, 2200),
    },
    "Upper Mount Royal": {
        1: (1350, 1469, 1600),
        2: (1600, 1850, 2100),
    },
    "Crescent Heights": {
        1: (1400, 1550, 1700),
        2: (1700, 1950, 2200),
        3: (2200, 2500, 2800),
    },
    "Mount Pleasant": {
        1: (1400, 1550, 1700),
        2: (1700, 1950, 2200),
        3: (2200, 2500, 2800),
    },
    "Renfrew": {
        1: (1500, 1650, 1800),
        2: (1900, 2150, 2400),
        3: (2500, 2825, 3500),
    },
    "Tuxedo Park": {
        1: (1400, 1507, 1650),
        2: (1700, 1900, 2100),
    },
    "Altadore": {
        0: (1200, 1400, 1650),
        1: (1350, 1841, 1950),
        2: (1800, 2200, 2850),
        3: (1550, 2375, 3200),
        4: (3200, 3800, 4600),
    },
    "Marda Loop": {
        1: (1350, 1841, 1950),
        2: (1800, 2200, 2850),
        3: (1550, 2375, 3200),
    },

    # ── Southwest (SW) ────────────────────────────────────────────────────────
    "Garrison Woods": {
        1: (1500, 1650, 1800),
        2: (1800, 2100, 2400),
        3: (2200, 2500, 2800),
    },
    "South Calgary": {
        1: (1500, 1650, 1800),
        2: (1800, 2100, 2400),
        3: (2200, 2500, 2800),
    },
    "Erlton": {
        1: (1600, 1750, 1900),
        2: (1900, 2150, 2400),
    },
    "Parkhill": {
        1: (1600, 1750, 1900),
        2: (1900, 2150, 2400),
    },
    "Windsor Park": {
        1: (1500, 1650, 1800),
        2: (1800, 2100, 2400),
        3: (2200, 2600, 3000),
    },
    "Britannia": {
        1: (1500, 1650, 1800),
        2: (1800, 2100, 2400),
        3: (2200, 2600, 3000),
    },
    "Kingsland": {
        1: (1400, 1553, 1650),
        2: (1800, 2000, 2200),
    },
    "Haysboro": {
        1: (1500, 1771, 1900),
        2: (1800, 2050, 2200),
    },
    "Oakridge": {
        1: (1400, 1575, 1650),
        2: (1700, 1950, 2200),
        3: (2000, 2300, 2600),
    },
    "Braeside": {
        1: (1300, 1499, 1600),
        2: (1600, 1850, 2100),
        3: (2000, 2300, 2500),
    },
    "Glamorgan": {
        1: (1400, 1550, 1700),
        2: (1700, 2000, 2300),
        3: (2100, 2450, 2800),
    },
    "Lakeview": {
        1: (1400, 1600, 1800),
        2: (1800, 2100, 2400),
        3: (2200, 2500, 2800),
    },
    "Signal Hill": {
        1: (1650, 1950, 2350),
        2: (2150, 2550, 3050),
        3: (2750, 3200, 3900),
        4: (3200, 3800, 4600),
    },
    "Chinook Park": {
        1: (1600, 1704, 1950),
        2: (1900, 2150, 2400),
    },
    "Southwood": {
        1: (1600, 1891, 1950),
        2: (1900, 2150, 2400),
    },
    "Applewood Park": {
        0: (900, 1100, 1300),
        1: (1100, 1306, 1400),
        2: (1400, 1600, 1800),
    },

    # ── Northwest (NW) ────────────────────────────────────────────────────────
    "Varsity": {
        1: (1499, 1875, 2000),
        2: (1819, 2057, 2200),
        3: (2200, 2500, 2800),
    },
    "Brentwood": {
        1: (1300, 1500, 1700),
        2: (1519, 1860, 2200),
        3: (2251, 2476, 2700),
    },
    "Dalhousie": {
        1: (1600, 2000, 2095),
        2: (2000, 2250, 2500),
        3: (2400, 2800, 3200),
    },
    "Bowness": {
        0: (1100, 1492, 1600),
        1: (1492, 1735, 1810),
        2: (1600, 1900, 2200),
        3: (2000, 2350, 2700),
    },
    "Montgomery": {
        1: (1600, 1750, 1900),
        2: (1900, 2163, 2400),
        3: (2200, 2500, 2800),
    },
    "Royal Oak": {
        1: (1600, 1800, 1900),
        2: (1900, 2150, 2400),
        3: (2100, 2450, 2800),
    },
    "Tuscany": {
        1: (1700, 1980, 2380),
        2: (2180, 2580, 3080),
        3: (2780, 3250, 3950),
        4: (3250, 3850, 4650),
    },
    "Sage Hill": {
        0: (1200, 1322, 1500),
        1: (1322, 1710, 1985),
        2: (1704, 2033, 2040),
        3: (2095, 2223, 2350),
    },
    "Evanston": {
        1: (1468, 1631, 1795),
        2: (1671, 1936, 2200),
        3: (2200, 2475, 2700),
        4: (3200, 3800, 4600),
    },
    "Nolan Hill": {
        1: (1425, 1563, 1700),
        2: (1700, 1950, 2200),
        3: (2100, 2400, 2700),
    },
    "Panorama Hills": {
        1: (1336, 1683, 1950),
        2: (1950, 2119, 2350),
        3: (2089, 2420, 2750),
        4: (3200, 3800, 4600),
    },
    "Sherwood": {
        1: (1600, 1750, 1900),
        2: (1900, 2150, 2400),
        3: (2200, 2500, 2800),
    },
    "Kincora": {
        1: (1600, 1800, 1900),
        2: (1999, 2100, 2400),
        3: (2200, 2450, 2700),
    },

    # ── Southeast (SE) ────────────────────────────────────────────────────────
    "Mahogany": {
        1: (1363, 1748, 1800),
        2: (1974, 2255, 2500),
        3: (2300, 2780, 3500),
        4: (3259, 3900, 4900),
    },
    "Auburn Bay": {
        1: (1225, 1528, 1650),
        2: (1150, 1927, 2266),
        3: (2500, 2868, 3200),
        4: (3350, 3950, 4750),
    },
    "Seton": {
        1: (1265, 1671, 1850),
        2: (1833, 2100, 2550),
        3: (2280, 2760, 3500),
    },
    "McKenzie Towne": {
        1: (1495, 1648, 1800),
        2: (2200, 2300, 2400),
        3: (2000, 2400, 2800),
    },
    "Cranston": {
        1: (1600, 1756, 1900),
        2: (1900, 2150, 2400),
        3: (2400, 2700, 3000),
        4: (3300, 3900, 4700),
    },
    "Copperfield": {
        1: (1415, 1615, 1765),
        2: (1650, 1875, 2100),
        3: (2299, 2650, 3000),
    },
    "New Brighton": {
        1: (1685, 1717, 1999),
        2: (1599, 1979, 2200),
        3: (2300, 2650, 3000),
    },
    "Legacy": {
        1: (1500, 1650, 1800),
        2: (1800, 2100, 2400),
        3: (2200, 2500, 2800),
    },
    "Walden": {
        1: (1600, 1750, 1900),
        2: (1900, 2125, 2350),
        3: (2200, 2450, 2700),
    },
    "Chaparral": {
        1: (1500, 1585, 1800),
        2: (1670, 1935, 2200),
        3: (2200, 2450, 2700),
    },
    "Quarry Park": {
        1: (1682, 1841, 2000),
        2: (1900, 2021, 2400),
        3: (2400, 2700, 3000),
    },
    "Douglasdale": {
        1: (1600, 1760, 1900),
        2: (1726, 1963, 2200),
        3: (2400, 2600, 2800),
    },
    "Riverbend": {
        1: (1600, 1726, 1900),
        2: (1726, 1963, 2200),
        3: (2400, 2600, 2800),
    },
    "Forest Lawn": {
        0: (950, 1100, 1350),
        1: (1200, 1490, 1600),
        2: (1400, 1648, 1900),
        3: (1700, 2000, 2300),
    },
    "Albert Park": {
        1: (1200, 1400, 1600),
        2: (1400, 1650, 1900),
        3: (1700, 2000, 2300),
    },
    "Silverado": {
        1: (1400, 1607, 1700),
        2: (1700, 1928, 2100),
        3: (2000, 2250, 2500),
    },

    # ── Northeast (NE) ────────────────────────────────────────────────────────
    "Saddle Ridge": {
        1: (1391, 1496, 1600),
        2: (1500, 1750, 2000),
        3: (2000, 2200, 2400),
    },
    "Cornerstone": {
        1: (1500, 1625, 1750),
        2: (1550, 1873, 2195),
        3: (2195, 2448, 2700),
    },
    "Skyview Ranch": {
        1: (1500, 1625, 1750),
        2: (1675, 1913, 2200),
        3: (2195, 2448, 2700),
    },
    "Livingston": {
        1: (1300, 1450, 1600),
        2: (1500, 1750, 2000),
        3: (2000, 2250, 2500),
    },
    "Redstone": {
        1: (1100, 1300, 1500),
        2: (1400, 1700, 2000),
        3: (1999, 2150, 2300),
    },
    "Cityscape": {
        1: (1400, 1550, 1700),
        2: (1400, 1600, 1800),
        3: (2200, 2450, 2700),
    },
    "Falconridge": {
        1: (1275, 1438, 1600),
        2: (1600, 1850, 2100),
        3: (1900, 2075, 2250),
    },
    "Martindale": {
        1: (1300, 1450, 1600),
        2: (1500, 1700, 1900),
        3: (1900, 2050, 2200),
    },
    "Taradale": {
        1: (1300, 1450, 1600),
        2: (1500, 1700, 1900),
        3: (1900, 2050, 2200),
    },
    "Castleridge": {
        1: (1275, 1438, 1600),
        2: (1600, 1800, 2000),
        3: (1850, 2025, 2200),
    },
    "Rundle": {
        1: (1200, 1350, 1500),
        2: (1400, 1600, 1800),
        3: (1700, 1950, 2200),
    },
    "Pineridge": {
        1: (1200, 1350, 1500),
        2: (1400, 1600, 1800),
        3: (1700, 1950, 2200),
    },
    "Temple": {
        1: (1200, 1350, 1500),
        2: (1400, 1600, 1800),
        3: (1700, 1950, 2200),
    },

    # ── North Calgary ────────────────────────────────────────────────────────
    "Country Hills": {
        1: (1400, 1550, 1700),
        2: (1750, 1975, 2200),
        3: (2100, 2400, 2700),
    },
    "Country Hills Village": {
        1: (1400, 1550, 1700),
        2: (1750, 1975, 2200),
        3: (2100, 2400, 2700),
    },
    "Coventry Hills": {
        1: (1400, 1550, 1700),
        2: (1750, 1975, 2200),
        3: (2200, 2850, 3500),
        4: (3100, 3500, 4000),
    },
    "Beddington Heights": {
        1: (1500, 1656, 1800),
        2: (1700, 1955, 2100),
        3: (1844, 2022, 2200),
    },
    "Thorncliffe": {
        1: (1500, 1811, 1800),
        2: (1700, 1955, 2100),
        3: (1850, 2025, 2200),
    },
    "Huntington Hills": {
        1: (1300, 1450, 1600),
        2: (1550, 1775, 2000),
        3: (1800, 2000, 2200),
    },
    "Carrington": {
        1: (1600, 1750, 1900),
        2: (1999, 2200, 2400),
        3: (2200, 2450, 2700),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# AIRDRIE — May 2026
# Sources: RentFaster, Zumper, Apartments.com
# ─────────────────────────────────────────────────────────────────────────────

AIRDRIE_RENT_DATA: Dict[str, Dict[int, Tuple[float, float, float]]] = {
    # City-wide fallback (used when community not found)
    "_default": {
        0: (1100, 1100, 1100),
        1: (1344, 1450, 1503),
        2: (1756, 1770, 1784),
        3: (2199, 2269, 2338),
        4: (2637, 3013, 4389),
    },
    "Downtown Airdrie": {
        1: (1450, 1562, 1674),
        2: (1757, 1759, 1760),
        3: (2217, 2217, 2250),
    },
    "King's Heights": {
        1: (1900, 2108, 2315),
        2: (1900, 2000, 2100),
        3: (2095, 2420, 3299),
        4: (2744, 3022, 3299),
    },
    "Bayside": {
        2: (2000, 2374, 2850),
        3: (2600, 2700, 2800),
    },
    "South Point": {
        2: (2350, 2413, 2475),
        3: (2600, 2688, 2775),
    },
    "Cooper's Crossing": {
        1: (1100, 1100, 1100),   # basement
        2: (2300, 2325, 2350),   # duplex
        3: (2750, 2750, 2750),   # house
    },
    "Luxstone": {
        3: (2500, 2900, 3300),
        4: (3000, 3300, 3600),
    },
    "Windsong": {
        2: (2000, 2200, 2400),
        3: (2200, 2450, 2700),
    },
    "Canals": {
        1: (1578, 1715, 1851),
        2: (2000, 2200, 2400),
        3: (2000, 2200, 2400),
    },
    "Morningside": {
        1: (1400, 1700, 2000),
        2: (1700, 2050, 2400),
    },
    "Woodside": {
        1: (1100, 1250, 1400),
        2: (1500, 1700, 1900),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# CHESTERMERE — May 2026
# Sources: RentFaster, Apartments.com, REW, Kijiji
# Note: thin market (6-26 active listings) — treat as directional
# ─────────────────────────────────────────────────────────────────────────────

CHESTERMERE_RENT_DATA: Dict[str, Dict[int, Tuple[float, float, float]]] = {
    "_default": {
        1: (1370, 1459, 1547),
        2: (1637, 1659, 1681),
        3: (2047, 2127, 2207),
        4: (2842, 2842, 2842),
    },
    "Dawson Landing": {
        1: (1548, 1548, 1548),
        2: (1698, 1698, 1698),
        3: (1899, 1999, 2099),
    },
    "Kinniburgh": {
        2: (1600, 1800, 2000),
        3: (2000, 2200, 2400),
    },
    "Chelsea": {
        2: (2048, 2048, 2048),
        3: (2000, 2100, 2200),
    },
    "South Shore": {
        3: (2050, 2073, 2095),
        4: (2400, 2600, 2800),
    },
    "Crystal Shores": {
        3: (2095, 2298, 2500),
        4: (2500, 3000, 3615),
    },
    "Westmere": {
        2: (1200, 2098, 2995),
        3: (1899, 2200, 2500),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# OKOTOKS — May 2026
# Sources: RentFaster, ApartmentHomeLiving, Apartments.com, Kijiji, RentCafe
# ─────────────────────────────────────────────────────────────────────────────

OKOTOKS_RENT_DATA: Dict[str, Dict[int, Tuple[float, float, float]]] = {
    "_default": {
        0: (1375, 1512, 1722),
        1: (1569, 1627, 1679),
        2: (1880, 1970, 2039),
        3: (2144, 2294, 2444),
        4: (2725, 2938, 3150),
    },
    "Drake Landing": {
        0: (1890, 2145, 3400),
        2: (915, 1405, 1895),
        3: (1800, 1900, 2000),
    },
    "Crystal Shores": {
        2: (1700, 1850, 2000),
        3: (2950, 2950, 2950),
    },
    "Cimarron": {
        3: (1800, 2100, 2400),
        4: (2400, 2700, 3000),
    },
    "Drake Landing Blvd Area": {
        3: (1800, 1900, 2000),
    },
    "Air Ranch": {
        3: (2200, 2600, 3000),
        4: (2800, 3200, 3600),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# CITY ROUTER — maps property city to correct dataset
# ─────────────────────────────────────────────────────────────────────────────

CITY_RENT_MAP = {
    "calgary":     CALGARY_RENT_DATA,
    "airdrie":     AIRDRIE_RENT_DATA,
    "chestermere": CHESTERMERE_RENT_DATA,
    "okotoks":     OKOTOKS_RENT_DATA,
}

# Calgary-wide fallback by bedroom (used when community not found in Calgary table)
CALGARY_DEFAULT_BY_BEDROOM: Dict[int, Tuple[float, float, float]] = {
    0: (1100, 1322, 1600),
    1: (1320, 1530, 1800),   # April 2026 Calgary city-wide avg ~$1,440 (liv.rent)
    2: (1650, 1907, 2200),   # Calgary 2-bed avg ~$1,907 (RentFaster)
    3: (2000, 2236, 2600),   # Calgary 3-bed avg ~$2,236 (RentFaster)
    4: (2600, 3000, 3800),
}

# YoY rent change estimates by area type (April 2026 data)
YOY_CHANGE = {
    "inner_city":  -0.06,   # City Centre down ~6% YoY (liv.rent Apr 2026)
    "sw":          -0.05,   # SW down ~5%
    "nw":          -0.10,   # NW down ~10% (highest new supply)
    "se":          -0.08,   # SE net correction
    "ne":          -0.11,   # NE down ~11%
    "suburban":    -0.03,   # Airdrie/satellite cities softer but milder
    "default":     -0.07,
}

INNER_CITY_COMMUNITIES = {
    "Beltline", "Downtown East Village", "Downtown Commercial Core",
    "Eau Claire", "Mission", "Kensington", "Hillhurst", "Bridgeland",
    "Inglewood", "Ramsay", "Cliff Bungalow", "Chinatown",
    "Bankview", "Sunalta", "Lower Mount Royal", "Upper Mount Royal",
    "Crescent Heights", "Mount Pleasant", "Renfrew", "Tuxedo Park",
    "Altadore", "Marda Loop",
}

SW_COMMUNITIES = {
    "Garrison Woods", "South Calgary", "Erlton", "Parkhill", "Windsor Park",
    "Britannia", "Kingsland", "Haysboro", "Oakridge", "Braeside",
    "Glamorgan", "Lakeview", "Signal Hill", "Chinook Park", "Southwood",
    "Applewood Park",
}

NW_COMMUNITIES = {
    "Varsity", "Brentwood", "Dalhousie", "Bowness", "Montgomery",
    "Royal Oak", "Tuscany", "Sage Hill", "Evanston", "Nolan Hill",
    "Panorama Hills", "Sherwood", "Kincora", "Carrington",
    "Country Hills", "Country Hills Village", "Coventry Hills",
    "Beddington Heights", "Thorncliffe", "Huntington Hills",
}

SE_COMMUNITIES = {
    "Mahogany", "Auburn Bay", "Seton", "McKenzie Towne", "Cranston",
    "Copperfield", "New Brighton", "Legacy", "Walden", "Chaparral",
    "Quarry Park", "Douglasdale", "Riverbend", "Forest Lawn", "Albert Park",
    "Silverado",
}


def _get_yoy(community: str) -> float:
    if community in INNER_CITY_COMMUNITIES:
        return YOY_CHANGE["inner_city"]
    if community in SW_COMMUNITIES:
        return YOY_CHANGE["sw"]
    if community in NW_COMMUNITIES:
        return YOY_CHANGE["nw"]
    if community in SE_COMMUNITIES:
        return YOY_CHANGE["se"]
    return YOY_CHANGE["default"]


class RentInsightService:

    def get_rent_estimate(
        self,
        community: str,
        bedrooms: int,
        property_type: str = "Apartment",
        square_footage: Optional[float] = None,
        city: str = "Calgary",
    ) -> RentInsightResponse:
        """
        Return rent range for a community + bedroom combo.
        Routes by city first, then community within that city.
        Falls back to city-wide defaults if community not found.
        """
        community_normalized = community.strip().title()
        city_key = city.lower().strip()

        # Get the right city dataset
        city_data = CITY_RENT_MAP.get(city_key, CALGARY_RENT_DATA)
        community_data = city_data.get(community_normalized, {})

        # Try _default key for non-Calgary cities if community not found
        if not community_data and "_default" in city_data:
            community_data = city_data["_default"]
            found = False
        elif community_data:
            found = True
        else:
            # Calgary fallback
            community_data = {}
            found = False

        rent_range = community_data.get(bedrooms)

        if not rent_range:
            # Walk down bedroom count until we find data
            for bd in [bedrooms, max(0, bedrooms - 1), 2, 1]:
                if bd in community_data:
                    rent_range = community_data[bd]
                    break

        if not rent_range:
            rent_range = CALGARY_DEFAULT_BY_BEDROOM.get(bedrooms, (1400, 1800, 2200))

        low, avg, high = rent_range

        # Property type adjustments
        type_multipliers = {
            "House": 1.15,
            "Detached": 1.15,
            "Semi-Detached": 1.08,
            "Townhouse": 1.05,
            "Condo": 1.0,
            "Apartment": 1.0,
            "Basement Suite": 0.78,
        }
        multiplier = type_multipliers.get(property_type, 1.0)
        low = round(low * multiplier)
        avg = round(avg * multiplier)
        high = round(high * multiplier)

        # Square footage premium (above 1,200 sqft)
        if square_footage and square_footage > 1200:
            premium = min((square_footage - 1200) / 1000 * 0.08, 0.15)
            low = round(low * (1 + premium))
            avg = round(avg * (1 + premium))
            high = round(high * (1 + premium))

        yoy = _get_yoy(community_normalized) if city_key == "calgary" else YOY_CHANGE["suburban"]

        label = community_normalized if found else f"{community_normalized} (est.)"
        return RentInsightResponse(
            community=label,
            bedrooms=bedrooms,
            property_type=property_type,
            avg_rent=float(avg),
            low_rent=float(low),
            high_rent=float(high),
            median_rent=float(round((low + high) / 2)),
            yoy_change_pct=round(yoy * 100, 1),
            sample_size=30 if found else 10,
            last_updated=RENT_DATA_VINTAGE,
            comparable_listings=[],
        )


# Singleton
rent_service = RentInsightService()
