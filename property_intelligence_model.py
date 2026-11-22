#!/usr/bin/env python3
"""
MRA Real Estate Solutions - Property Intelligence & 5-Factor Analysis Model
---------------------------------------------------------------------------
This is a local command-line automation tool that calculates redevelopment potential
and 5-factor location scores for properties in Dhaka, Bangladesh.

It implements the MRA core philosophy:
"We do not just show a property; we show the Context (Growth Velocity + FAR Potential)."
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Harmonious HSL-like CLI colors using ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[38;2;16;185;129m"
BLUE = "\033[38;2;59;130;246m"
YELLOW = "\033[38;2;245;158;11m"
RED = "\033[38;2;239;68;68m"
CYAN = "\033[38;2;6;182;212m"
MAGENTA = "\033[38;2;139;92;246m"
WHITE = "\033[37m"

DHAKA_AREAS = {
    "GULSHAN": {
        "Jobs": 9.5, "Education": 9.0, "Infrastructure": 9.5, "Safety": 9.5, "Amenities": 9.8,
        "Growth_Velocity": "Stable High (Premium)", "Base_Price_Per_Sqft": 22000, "DAP_Compliance": "Highly Regulated"
    },
    "BANANI": {
        "Jobs": 9.2, "Education": 8.8, "Infrastructure": 9.0, "Safety": 9.0, "Amenities": 9.5,
        "Growth_Velocity": "Stable High", "Base_Price_Per_Sqft": 20000, "DAP_Compliance": "Highly Regulated"
    },
    "BASHUNDHARA": {
        "Jobs": 8.0, "Education": 9.5, "Infrastructure": 8.8, "Safety": 9.2, "Amenities": 9.0,
        "Growth_Velocity": "Very High (>15% annual construction velocity)", "Base_Price_Per_Sqft": 13500, "DAP_Compliance": "Approved"
    },
    "UTTARA": {
        "Jobs": 7.5, "Education": 8.8, "Infrastructure": 8.5, "Safety": 8.5, "Amenities": 8.5,
        "Growth_Velocity": "High (Metro-Rail Accelerated)", "Base_Price_Per_Sqft": 11000, "DAP_Compliance": "Approved"
    },
    "MIRPUR": {
        "Jobs": 6.8, "Education": 7.5, "Infrastructure": 7.8, "Safety": 7.5, "Amenities": 8.0,
        "Growth_Velocity": "High (Densifying)", "Base_Price_Per_Sqft": 7500, "DAP_Compliance": "Mixed Use"
    }
}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_rajuk_far(road_size_ft):
    """
    Approximates RAJUK DAP FAR rules based on road width.
    """
    if road_size_ft < 12:
        return 2.50, 50.0  # (FAR, Max Ground Coverage %)
    elif road_size_ft < 20:
        return 3.15, 52.5
    elif road_size_ft < 30:
        return 3.50, 55.0
    elif road_size_ft < 40:
        return 4.00, 57.5
    elif road_size_ft < 60:
        return 4.75, 60.0
    else:
        return 5.50, 62.5

def calculate_redevelopment_score(land_kathas, current_stories, allowed_far):
    """
    Compares current utilized floor space with maximum allowed floor space.
    1 Katha = 720 Sqft
    """
    land_area_sqft = land_kathas * 720
    # Assume typical ground coverage is 50% for current building
    current_footprint = land_area_sqft * 0.5
    current_built_area = current_footprint * current_stories
    
    max_built_area = land_area_sqft * allowed_far
    potential_stories = int((max_built_area) / current_footprint)
    
    redevelopment_ratio = max_built_area / max(1, current_built_area)
    
    score = min(10.0, redevelopment_ratio * 2.5) # Scale to 10 max
    
    return score, max_built_area, current_built_area, potential_stories

def print_header():
    print(f"\n{CYAN}{BOLD}================================================================================{RESET}")
    print(f"{CYAN}{BOLD}               MRA REAL ESTATE - SPATIAL INTELLIGENCE & SCORING MODEL           {RESET}")
    print(f"{CYAN}{BOLD}================================================================================{RESET}\n")

def main():
    clear_screen()
    print_header()
    
    print(f"{BOLD}Step 1: Enter Dhaka Property Characteristics{RESET}")
    print("-" * 45)
    
    # 1. Select Area
    print(f"\nSelect Dhaka Area:")
    areas = list(DHAKA_AREAS.keys())
    for idx, area in enumerate(areas, 1):
        print(f"  [{idx}] {area.title()}")
    
    try:
        area_choice = int(input(f"\nSelect Area [1-{len(areas)}]: "))
        selected_area_name = areas[area_choice - 1]
    except (ValueError, IndexError):
        print(f"\n{RED}Invalid choice. Defaulting to BASHUNDHARA.{RESET}")
        selected_area_name = "BASHUNDHARA"
        
    area_data = DHAKA_AREAS[selected_area_name]
    
    # 2. Road Size
    try:
        road_size = float(input(f"Enter Road Size in front of property (in feet): "))
    except ValueError:
        print(f"{RED}Invalid input. Defaulting to 20 feet.{RESET}")
        road_size = 20.0
        
    # 3. Land Area
    try:
        land_area = float(input(f"Enter Land Area (in Kathas): "))
    except ValueError:
        print(f"{RED}Invalid input. Defaulting to 5 Kathas.{RESET}")
        land_area = 5.0

    # 4. Current building stories
    try:
        current_stories = int(input(f"Enter Current Building Height (Stories, 0 for empty plot): "))
    except ValueError:
        print(f"{RED}Invalid input. Defaulting to 2 stories.{RESET}")
        current_stories = 2

    # Calculations
    allowed_far, max_mgc = get_rajuk_far(road_size)
    redev_score, max_built, current_built, pot_stories = calculate_redevelopment_score(
        land_area, current_stories, allowed_far
    )
    
    # 5-Factor Area Calculation
    area_factors = [
        area_data["Jobs"],
        area_data["Education"],
        area_data["Infrastructure"],
        area_data["Safety"],
        area_data["Amenities"]
    ]
    avg_area_score = sum(area_factors) / len(area_factors)
    
    # Combined Investment Score (Weighted)
    # If empty plot (current_stories = 0), redevelopment potential is maximum (10.0)
    if current_stories == 0:
        redev_score = 10.0
        
    investment_viability = (redev_score * 0.45) + (avg_area_score * 0.40) + ((road_size/20) * 0.15)
    investment_viability = min(10.0, investment_viability)

    # Printing Results
    clear_screen()
    print_header()
    
    # Compliance Card
    print(f"{GREEN}{BOLD}┌──────────────────────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{GREEN}{BOLD}│                          RAJUK REGULATORY COMPLIANCE CARD                    │{RESET}")
    print(f"{GREEN}{BOLD}├──────────────────────────────────────────────────────────────────────────────┤{RESET}")
    print(f"{GREEN}{BOLD}│{RESET}  {BOLD}Location:{RESET} {selected_area_name.title():<22} {GREEN}{BOLD}│{RESET}  {BOLD}DAP Zoning Status:{RESET} {area_data['DAP_Compliance']:<22} {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}│{RESET}  {BOLD}Road Width:{RESET} {road_size:<5} ft               {GREEN}{BOLD}│{RESET}  {BOLD}Estimated Max FAR:{RESET} {allowed_far:<21} {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}│{RESET}  {BOLD}Land Size:{RESET} {land_area:<5} Kathas ({int(land_area*720)} sqft) {GREEN}{BOLD}│{RESET}  {BOLD}Max Ground Coverage:{RESET} {max_mgc:<19}% {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}└──────────────────────────────────────────────────────────────────────────────┘{RESET}\n")

    # Redevelopment Potential Details (Sellers / Developers view)
    print(f"{BLUE}{BOLD}📈 PROPERTY REDEVELOPMENT POTENTIAL (THE 'GOLDMINE CHECK'){RESET}")
    print("-" * 80)
    if current_stories > 0:
        print(f"  • Current Built Area:    {int(current_built):,d} sqft ({current_stories} stories)")
    else:
        print(f"  • Current Built Area:    0 sqft (Vacant Land)")
    print(f"  • Max Allowed Floor Area: {int(max_built):,d} sqft (Based on FAR {allowed_far})")
    print(f"  • Potential Story Capacity: {pot_stories} stories on allowed ground coverage")
    
    redev_color = GREEN if redev_score > 7 else (YELLOW if redev_score > 4 else RED)
    redev_label = "HIGH REDEVELOPMENT POTENTIAL (GOLDMINE)" if redev_score > 7 else ("MODERATE POTENTIAL" if redev_score > 4 else "LOW POTENTIAL")
    print(f"  • {BOLD}Redevelopment Potential Score: {redev_color}{redev_score:.2f} / 10.0 ({redev_label}){RESET}")
    print("-" * 80)

    # 5-Factor Area Score Details
    print(f"\n{YELLOW}{BOLD}🏘️ 5-FACTOR AREA NEIGHBORHOOD CONTEXT{RESET}")
    print("-" * 80)
    print(f"  1. Job Opportunities:  [{'★'*int(area_data['Jobs'])}{'☆'*(10-int(area_data['Jobs']))}] {area_data['Jobs']:.1f}/10")
    print(f"  2. Education & Schools: [{'★'*int(area_data['Education'])}{'☆'*(10-int(area_data['Education']))}] {area_data['Education']:.1f}/10")
    print(f"  3. Infrastructure:     [{'★'*int(area_data['Infrastructure'])}{'☆'*(10-int(area_data['Infrastructure']))}] {area_data['Infrastructure']:.1f}/10")
    print(f"  4. Safety & Security:  [{'★'*int(area_data['Safety'])}{'☆'*(10-int(area_data['Safety']))}] {area_data['Safety']:.1f}/10")
    print(f"  5. Amenities & Retail: [{'★'*int(area_data['Amenities'])}{'☆'*(10-int(area_data['Amenities']))}] {area_data['Amenities']:.1f}/10")
    print(f"  • {BOLD}Overall Neighborhood Context Score: {YELLOW}{avg_area_score:.2f} / 10.0{RESET}")
    print(f"  • {BOLD}Growth Velocity Indicator:          {MAGENTA}{area_data['Growth_Velocity']}{RESET}")
    print("-" * 80)

    # Summary investment decision (Buyer Decision Intelligence layer)
    print(f"\n{MAGENTA}{BOLD}📊 MRA DECISION INTELLIGENCE SUMMARY{RESET}")
    print("=" * 80)
    viability_color = GREEN if investment_viability > 7.5 else (YELLOW if investment_viability > 5.0 else RED)
    print(f"  {BOLD}MRA INVESTMENT VIABILITY INDEX: {viability_color}{investment_viability:.2f} / 10.0{RESET}")
    print(f"  {BOLD}Dhaka Base Market Price:       {BOLD}৳ {area_data['Base_Price_Per_Sqft']:,d} per sqft{RESET}")
    print(f"  {BOLD}Investment Action Suggestion:  {RESET}", end="")
    if investment_viability > 7.5:
        print(f"{GREEN}{BOLD}STRONG BUY (Under-utilized asset in high-growth corridor. High FAR yield potential.){RESET}")
    elif investment_viability > 5.0:
        print(f"{YELLOW}{BOLD}HOLD & NEGOTIATE (Good location, but premium pricing or current build limits immediate ROI.){RESET}")
    else:
        print(f"{RED}{BOLD}AVOID / RE-EVALUATE (Poor redevelopment prospects, sub-optimal road sizing, or high compliance friction.){RESET}")
    print("=" * 80)
    print(f"\n{WHITE}Compiled by MRA Real Estate Solutions Platform CLI.{RESET}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python property_intelligence_model.py")
        sys.exit(0)
    main()
