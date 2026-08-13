"""Curated river-delta observation points grouped by dominant forcing."""

from __future__ import annotations

from collections import Counter


RIVER_DOMINATED = "River-dominated"
WAVE_DOMINATED = "Wave-dominated"
TIDE_DOMINATED = "Tide-dominated"
DELTA_TYPES = (RIVER_DOMINATED, WAVE_DOMINATED, TIDE_DOMINATED)
DELTA_CATALOG_VERSION = 2


DELTAS = {
    # River-dominated end members and strongly fluvial examples.
    "Mississippi bird-foot · USA": {
        "latitude": 29.102,
        "longitude": -89.245,
        "width_km": 42,
        "type": RIVER_DOMINATED,
        "description": "Finger-like distributaries, wetlands and rapid land change.",
    },
    "Wax Lake · USA": {
        "latitude": 29.506,
        "longitude": -91.436,
        "width_km": 34,
        "type": RIVER_DOMINATED,
        "description": "A young, actively prograding delta built by river sediment.",
    },
    "Volga · Russia": {
        "latitude": 45.750,
        "longitude": 47.670,
        "width_km": 52,
        "type": RIVER_DOMINATED,
        "description": "A broad distributary network entering the low-energy Caspian Sea.",
    },
    "Lena · Russia": {
        "latitude": 72.620,
        "longitude": 126.870,
        "width_km": 52,
        "type": RIVER_DOMINATED,
        "description": "Arctic channels transformed by freeze, breakup and flood pulses.",
    },
    "Mackenzie · Canada": {
        "latitude": 69.050,
        "longitude": -135.300,
        "width_km": 52,
        "type": RIVER_DOMINATED,
        "description": "Lakes, distributaries and seasonal ice on the Beaufort coast.",
    },
    "Yukon · USA": {
        "latitude": 62.590,
        "longitude": -164.800,
        "width_km": 52,
        "type": RIVER_DOMINATED,
        "description": "A large subarctic lobe with shifting channels and sediment plumes.",
    },
    "Kolyma · Russia": {
        "latitude": 69.580,
        "longitude": 161.360,
        "width_km": 48,
        "type": RIVER_DOMINATED,
        "description": "An Arctic river mouth with strong seasonal hydrology and ice cover.",
    },
    "Indigirka · Russia": {
        "latitude": 71.080,
        "longitude": 150.170,
        "width_km": 48,
        "type": RIVER_DOMINATED,
        "description": "Low-relief tundra distributaries shaped by river floods and permafrost.",
    },
    "Yellow River · China": {
        "latitude": 37.750,
        "longitude": 119.150,
        "width_km": 46,
        "type": RIVER_DOMINATED,
        "description": "Rapidly migrating shoreline fed by an exceptionally sediment-rich river.",
    },
    "Selenga · Russia": {
        "latitude": 52.300,
        "longitude": 106.500,
        "width_km": 42,
        "type": RIVER_DOMINATED,
        "description": "An inland fluvial delta entering Lake Baikal.",
    },

    # Wave-dominated and strongly wave-reworked examples.
    "Nile · Egypt": {
        "latitude": 31.262,
        "longitude": 31.034,
        "width_km": 46,
        "type": WAVE_DOMINATED,
        "description": "A smooth Mediterranean shoreline with lagoons and intense land use.",
    },
    "Rhône · France": {
        "latitude": 43.350,
        "longitude": 4.820,
        "width_km": 38,
        "type": WAVE_DOMINATED,
        "description": "The Camargue coast, beach ridges, wetlands and salt ponds.",
    },
    "Ebro · Spain": {
        "latitude": 40.720,
        "longitude": 0.860,
        "width_km": 34,
        "type": WAVE_DOMINATED,
        "description": "A cuspate delta whose sediment is redistributed alongshore by waves.",
    },
    "Danube · Romania / Ukraine": {
        "latitude": 45.150,
        "longitude": 29.650,
        "width_km": 48,
        "type": WAVE_DOMINATED,
        "description": "Reed beds and distributaries meeting a wave-reworked Black Sea coast.",
    },
    "Po · Italy": {
        "latitude": 44.950,
        "longitude": 12.480,
        "width_km": 38,
        "type": WAVE_DOMINATED,
        "description": "A highly engineered Adriatic delta with curved coastal lobes.",
    },
    "São Francisco · Brazil": {
        "latitude": -10.450,
        "longitude": -36.400,
        "width_km": 34,
        "type": WAVE_DOMINATED,
        "description": "A wave-smoothed tropical mouth with beach ridges and sediment plumes.",
    },
    "Senegal · Senegal / Mauritania": {
        "latitude": 15.990,
        "longitude": -16.510,
        "width_km": 34,
        "type": WAVE_DOMINATED,
        "description": "A strongly wave-reworked mouth beside the Langue de Barbarie spit.",
    },
    "Mahanadi · India": {
        "latitude": 20.320,
        "longitude": 86.730,
        "width_km": 44,
        "type": WAVE_DOMINATED,
        "description": "Beach ridges and a smooth Bay of Bengal delta front.",
    },
    "Godavari · India": {
        "latitude": 16.580,
        "longitude": 82.320,
        "width_km": 44,
        "type": WAVE_DOMINATED,
        "description": "Agriculture, mangroves and wave-shaped distributary mouths.",
    },
    "Krishna · India": {
        "latitude": 15.730,
        "longitude": 80.970,
        "width_km": 42,
        "type": WAVE_DOMINATED,
        "description": "A low-lying, wave-reworked coast with aquaculture and mangroves.",
    },

    # Tide-dominated and strongly tide-influenced examples.
    "Ganges–Brahmaputra · Bangladesh": {
        "latitude": 21.872,
        "longitude": 89.205,
        "width_km": 52,
        "type": TIDE_DOMINATED,
        "description": "Tidal channels, mangroves, bars and cyclone-driven change.",
    },
    "Amazon · Brazil": {
        "latitude": 0.192,
        "longitude": -49.301,
        "width_km": 54,
        "type": TIDE_DOMINATED,
        "description": "Turbid tidal channels and mangrove islands at immense scale.",
    },
    "Orinoco · Venezuela": {
        "latitude": 8.660,
        "longitude": -61.450,
        "width_km": 42,
        "type": TIDE_DOMINATED,
        "description": "Western delta channels, mudbanks and mangroves inside a stable Sentinel-2 tile.",
    },
    "Fly · Papua New Guinea": {
        "latitude": -8.540,
        "longitude": 143.650,
        "width_km": 50,
        "type": TIDE_DOMINATED,
        "description": "A textbook tide-dominated mouth with elongated islands and bars.",
    },
    "Mekong · Vietnam": {
        "latitude": 9.620,
        "longitude": 106.500,
        "width_km": 46,
        "type": TIDE_DOMINATED,
        "description": "Tidal distributaries, aquaculture and seasonal sediment plumes.",
    },
    "Mahakam · Indonesia": {
        "latitude": -0.750,
        "longitude": 117.550,
        "width_km": 46,
        "type": TIDE_DOMINATED,
        "description": "Dense tidal channels and mangrove islands on the Makassar Strait.",
    },
    "Ayeyarwady · Myanmar": {
        "latitude": 15.790,
        "longitude": 95.000,
        "width_km": 50,
        "type": TIDE_DOMINATED,
        "description": "Multiple mouths, tidal flats and rapidly changing cultivated land.",
    },
    "Pearl River · China": {
        "latitude": 22.160,
        "longitude": 113.750,
        "width_km": 48,
        "type": TIDE_DOMINATED,
        "description": "Tidal channels transformed by ports, reclamation and urban growth.",
    },
    "Yangtze · China": {
        "latitude": 31.430,
        "longitude": 121.900,
        "width_km": 52,
        "type": TIDE_DOMINATED,
        "description": "Large tidal islands, shipping channels and engineered shorelines.",
    },
    "Indus · Pakistan": {
        "latitude": 23.980,
        "longitude": 67.450,
        "width_km": 50,
        "type": TIDE_DOMINATED,
        "description": "Arid tidal creeks, mudflats and mangroves under sediment stress.",
    },
}


def deltas_by_type(delta_type: str) -> list[str]:
    """Return the curated delta names in one morphodynamic class."""
    return [name for name, delta in DELTAS.items() if delta["type"] == delta_type]


def type_counts() -> Counter:
    """Return counts used by tests and compact UI labels."""
    return Counter(delta["type"] for delta in DELTAS.values())
