# --- Logic Snippet for your app.py ---

def calculate_detailed_emissions(inputs):
    # 1. Digital Footprint per Category
    # We apply the Monthly Computer Factor (6.44 kg) per person
    claimant_total_people = inputs['c_team'] + inputs['c_counsel'] + inputs['c_experts']
    respondent_total_people = inputs['r_team'] + inputs['r_counsel'] + inputs['r_experts']
    tribunal_people = inputs['arbitrators'] # Usually 3

    # Computer emissions = People * Months * Factor
    # Note: Tribunal often has the same duration as the case
    digital_co2 = (claimant_total_people + respondent_total_people + tribunal_people) * \
                   inputs['case_months'] * 6.44
    
    # 2. Travel to Hearing (The "Big" Logic)
    # We calculate the distance from each group's home city to the hearing city
    travel_co2 = 0
    
    # Example: Claimant Counsel Travel
    dist = get_distance(inputs['c_counsel_city'], inputs['hearing_city'])
    travel_co2 += (dist * 2 * inputs['c_counsel'] * get_transport_factor(inputs['c_counsel_mode']))
    
    # Example: Tribunal Travel
    # Arbitrators often travel from different global cities
    for arb_city, arb_mode in inputs['arbitrator_locations']:
        dist = get_distance(arb_city, inputs['hearing_city'])
        travel_co2 += (dist * 2 * 1 * get_transport_factor(arb_mode))

    return {"Digital": digital_co2, "Travel": travel_co2}
