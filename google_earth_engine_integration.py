#!/usr/bin/env python3
"""
MRA Real Estate Solutions - Google Earth Engine Footprint & Height Integration
----------------------------------------------------------------------------
This module provides a production-grade template to connect coordinates (lat, lon)
in Dhaka, Bangladesh to building footprints and estimated heights (2.5D) using
the `GOOGLE/Research/open-buildings-temporal/v1` dataset in Google Earth Engine.

It implements the first layer of the MRA backend architecture:
"The Growth Layer: Estimating historical height timelines and construction velocity."
"""

import sys
import os
import datetime

# HSL-like ANSI terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[38;2;16;185;129m"
BLUE = "\033[38;2;59;130;246m"
YELLOW = "\033[38;2;245;158;11m"
CYAN = "\033[38;2;6;182;212m"
MAGENTA = "\033[38;2;139;92;246m"

def print_header():
    print(f"\n{CYAN}{BOLD}================================================================================{RESET}")
    print(f"{CYAN}{BOLD}              MRA SPATIAL ENGINE - GOOGLE EARTH ENGINE INTEGRATION              {RESET}")
    print(f"{CYAN}{BOLD}================================================================================{RESET}\n")

# MOCK ENGINE (Ensures the script runs and demonstrates output without immediate API authentication)
def run_mock_engine(lat, lon):
    print(f"{YELLOW}⚠️  Running in simulation mode (Google Earth Engine is not authenticated on this PC).{RESET}")
    print(f"To activate live connection, install `earthengine-api` and set `USE_GEE_LIVE = True` in this script.")
    print("-" * 80)
    print(f"Target Coordinate: {BOLD}Latitude: {lat}, Longitude: {lon}{RESET} (Bashundhara Block D, Dhaka)")
    print(f"Connecting to: {MAGENTA}GOOGLE/Research/open-buildings-temporal/v1{RESET} (Effective Res: 4m)")
    print("-" * 80)
    
    print(f"\n{BOLD}Fetching 2016-2023 Temporal Raster Timeline...{RESET}")
    print("Mosaicing annual Sentinel-2 indices...")
    
    timeline_data = [
        {"Year": 2016, "Presence_Conf": 0.45, "Avg_Height_M": 3.2, "Activity": "Low Rise / Ground footprint detected"},
        {"Year": 2018, "Presence_Conf": 0.48, "Avg_Height_M": 3.2, "Activity": "Stable"},
        {"Year": 2020, "Presence_Conf": 0.88, "Avg_Height_M": 12.5, "Activity": "Construction Detected (Active Development)"},
        {"Year": 2021, "Presence_Conf": 0.92, "Avg_Height_M": 22.0, "Activity": "Vertical expansion (Mid-rise building completed)"},
        {"Year": 2022, "Presence_Conf": 0.95, "Avg_Height_M": 28.5, "Activity": "Completing vertical levels"},
        {"Year": 2023, "Presence_Conf": 0.96, "Avg_Height_M": 28.5, "Activity": "Stable / Mid-rise occupied (Approx 9 Stories)"}
    ]
    
    print("\n" + "=" * 70)
    print(f" {BOLD}{GREEN}SATELLITE SCAN RESULTS: 2.5D BUILDING FOOTPRINT TIMELINE{RESET}")
    print("=" * 70)
    print(f"{BOLD}{'Year':<8} | {'Presence Conf':<15} | {'Avg Height (m)':<15} | {'Detected State':<30}{RESET}")
    print("-" * 70)
    for entry in timeline_data:
        presence_bar = "█" * int(entry["Presence_Conf"] * 10) + "░" * (10 - int(entry["Presence_Conf"] * 10))
        print(f"{entry['Year']:<8} | {presence_bar} {entry['Presence_Conf']:.2f} | {entry['Avg_Height_M']:<15.1f} | {entry['Activity']:<30}")
    print("=" * 70)
    
    # Calculate velocity
    p_start = timeline_data[0]["Presence_Conf"]
    p_end = timeline_data[-1]["Presence_Conf"]
    velocity_idx = (p_end - p_start) * 100 / (2023 - 2016)
    
    print(f"\n{BOLD}MRA Analytics Summary:{RESET}")
    print(f"  • {BOLD}Construction Growth Velocity:{RESET} {GREEN}{velocity_idx:.2f}% per year{RESET} (High-Growth Heatmap)")
    print(f"  • {BOLD}Estimate Stories (2023):{RESET} {BLUE}9.5 stories{RESET} (approx 28.5 meters / 3m per story)")
    print(f"  • {BOLD}Zoning Suitability Index:{RESET} {CYAN}Approved for High-Density redevelopment{RESET}\n")

# LIVE ENGINE (Used when Earth Engine client library is installed & authenticated)
def run_live_engine(lat, lon):
    try:
        import ee
    except ImportError:
        print(f"{RED}Error: earthengine-api not installed. Run `pip install earthengine-api`{RESET}")
        sys.exit(1)
        
    print(f"{GREEN}✓ Earth Engine Python Client detected. Initializing GEE connection...{RESET}")
    
    try:
        # Initialize Google Earth Engine API
        ee.Initialize()
    except Exception as e:
        print(f"{YELLOW}Earth Engine not authenticated. Prompting authentication instructions...{RESET}")
        print(f"Run `earthengine authenticate` in your terminal to log in to your Google Cloud Project.")
        print("-" * 80)
        # Fallback to simulation
        run_mock_engine(lat, lon)
        return

    # GEE live computations
    point = ee.Geometry.Point([lon, lat])
    col = ee.ImageCollection('GOOGLE/Research/open-buildings-temporal/v1')
    
    # Query timestamps distinct list
    try:
        timestamps = col.filterBounds(point) \
                        .aggregate_array('system:time_start') \
                        .distinct() \
                        .sort() \
                        .getInfo()
    except Exception as e:
        print(f"{RED}GEE API query failed: {e}{RESET}")
        return

    print(f"Successfully connected! Found {len(timestamps)} annual raster footprints in Google Open Buildings timeline.")
    print("Extracting building_presence and building_height bands...")
    
    print("\n" + "=" * 70)
    print(f" {BOLD}{GREEN}LIVE SCAN RESULTS: 2.5D BUILDING FOOTPRINT TIMELINE{RESET}")
    print("=" * 70)
    print(f"{BOLD}{'Year':<8} | {'Presence Conf':<15} | {'Avg Height (m)':<15}{RESET}")
    print("-" * 70)
    
    for ts in timestamps:
        year = datetime.datetime.fromtimestamp(ts/1000.0).year
        # Filter collection and mosaic tiles
        year_img = col.filter(ee.Filter.eq('system:time_start', ts)).mosaic()
        
        # Reduce region around coordinate to fetch pixel values
        stats = year_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point.buffer(10), # 10m radius buffer around coordinates
            scale=0.5
        ).getInfo()
        
        presence = stats.get('building_presence', 0.0) or 0.0
        height = stats.get('building_height', 0.0) or 0.0
        
        presence_bar = "█" * int(presence * 10) + "░" * (10 - int(presence * 10))
        print(f"{year:<8} | {presence_bar} {presence:.2f} | {height:<15.2f}")
        
    print("=" * 70)
    print("\nUse these GEE variables to enrich MRA Spatial Intelligence maps directly!\n")

if __name__ == "__main__":
    # Toggle live engine connection (True if authenticated, False for interactive mockup scan)
    USE_GEE_LIVE = False
    
    # Coordinates for Dhaka, Bashundhara Block D
    DHAKA_LAT = 23.8164
    DHAKA_LON = 90.4285
    
    print_header()
    if USE_GEE_LIVE:
        run_live_engine(DHAKA_LAT, DHAKA_LON)
    else:
        run_mock_engine(DHAKA_LAT, DHAKA_LON)
