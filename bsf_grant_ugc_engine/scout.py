#!/usr/bin/env python3
"""
scout.py — Builds paginated search URLs across Grant & B2B Partner verticals.
"""
import urllib.parse

QUERY_MATRIX = [
    # Rotation Day 0: Water Cleaning Agent Vertical
    {
        "vertical": "Water Cleaning Agent (Chitosan Flocculant)",
        "grant_key": "grant_water_bd",
        "grant_query": 'site:ngoab.gov.bd OR site:undp.org OR site:adb.org "Bangladesh" ("water purification" OR "wastewater" OR "effluent") grant call for proposals',
        "partner_key": "partner_water_lab_bd",
        "partner_query": '"Bangladesh" ("water treatment" OR "effluent treatment plant" OR "analytical laboratory") ("chemist" OR "R&D" OR "formulation") Dhaka'
    },
    # Rotation Day 1: Cosmopharma Combinations Vertical
    {
        "vertical": "Cosmopharma & Biopolymer Skincare",
        "grant_key": "grant_climate_ngo",
        "grant_query": '("biotechnology" OR "circular economy" OR "biomaterials") grant funding application ("Asia" OR "Bangladesh" OR "developing countries")',
        "partner_key": "partner_cosmo_chemist_bd",
        "partner_query": '"Bangladesh" ("cosmetics" OR "dermatology" OR "pharmaceutical") ("formulation chemist" OR "contract manufacturing" OR "R&D lab") Dhaka'
    },
    # Rotation Day 2: Insect Pet Food & Aquaculture Vertical
    {
        "vertical": "BSF Insect Pet Food & Prebiotic Chitin",
        "grant_key": "grant_bioeconomy",
        "grant_query": '("black soldier fly" OR "alternative protein" OR "aquaculture innovation" OR "waste to value") grant funding fellowship NGO',
        "partner_key": "partner_petfood_mill_bd",
        "partner_query": '"Bangladesh" ("pet food" OR "aqua feed" OR "poultry nutrition") ("formulator" OR "nutritionist" OR "manufacturer" OR "dealership")'
    }
]


def build_google_url(query: str, page: int = 1) -> str:
    start = max(0, (page - 1) * 10)
    params = {"q": query, "start": start, "hl": "en"}
    return f"https://www.google.com/search?{urllib.parse.urlencode(params)}"
