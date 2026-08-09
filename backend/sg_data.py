"""Static Singapore reference data: cooling spots, preparedness checklists, symptom rules."""

# Real Singapore cool spots: malls, parks, community centres, hydration/water points.
COOLING_SPOTS = [
    {"id": "cs1", "name": "ION Orchard", "type": "mall", "lat": 1.3040, "lng": 103.8318, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs2", "name": "VivoCity", "type": "mall", "lat": 1.2644, "lng": 103.8220, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs3", "name": "Jewel Changi Airport", "type": "mall", "lat": 1.3601, "lng": 103.9890, "amenities": ["air-con", "water", "seating", "washroom", "shade"]},
    {"id": "cs4", "name": "Tampines Mall", "type": "mall", "lat": 1.3524, "lng": 103.9449, "amenities": ["air-con", "water", "seating"]},
    {"id": "cs5", "name": "Jurong Point", "type": "mall", "lat": 1.3399, "lng": 103.7069, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs6", "name": "Bishan-Ang Mo Kio Park", "type": "park", "lat": 1.3620, "lng": 103.8483, "amenities": ["shade", "water", "seating"]},
    {"id": "cs7", "name": "East Coast Park", "type": "park", "lat": 1.3006, "lng": 103.9120, "amenities": ["shade", "water", "seating", "breeze"]},
    {"id": "cs8", "name": "Singapore Botanic Gardens", "type": "park", "lat": 1.3138, "lng": 103.8159, "amenities": ["shade", "water", "seating"]},
    {"id": "cs9", "name": "Gardens by the Bay (Cooled Domes)", "type": "park", "lat": 1.2816, "lng": 103.8636, "amenities": ["air-con", "shade", "water", "seating"]},
    {"id": "cs10", "name": "West Coast Park", "type": "park", "lat": 1.2919, "lng": 103.7644, "amenities": ["shade", "water", "seating"]},
    {"id": "cs11", "name": "National Library Building", "type": "public", "lat": 1.2966, "lng": 103.8547, "amenities": ["air-con", "seating", "water", "washroom"]},
    {"id": "cs12", "name": "Toa Payoh Community Club", "type": "community", "lat": 1.3343, "lng": 103.8497, "amenities": ["air-con", "water", "seating"]},
    {"id": "cs13", "name": "Our Tampines Hub", "type": "community", "lat": 1.3536, "lng": 103.9403, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs14", "name": "Waterway Point", "type": "mall", "lat": 1.4054, "lng": 103.9024, "amenities": ["air-con", "water", "seating"]},
    {"id": "cs15", "name": "Fort Canning Park", "type": "park", "lat": 1.2955, "lng": 103.8465, "amenities": ["shade", "seating"]},
    {"id": "cs16", "name": "Nex Mall Serangoon", "type": "mall", "lat": 1.3506, "lng": 103.8720, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs17", "name": "Plaza Singapura", "type": "mall", "lat": 1.3007, "lng": 103.8450, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs18", "name": "Bugis Junction", "type": "mall", "lat": 1.2994, "lng": 103.8555, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs19", "name": "Jurong East Regional Library", "type": "public", "lat": 1.3331, "lng": 103.7420, "amenities": ["air-con", "seating", "water", "washroom"]},
    {"id": "cs20", "name": "Woodlands Regional Library", "type": "public", "lat": 1.4350, "lng": 103.7865, "amenities": ["air-con", "seating", "water", "washroom"]},
    {"id": "cs21", "name": "Punggol Waterway Park", "type": "park", "lat": 1.4105, "lng": 103.9045, "amenities": ["shade", "water", "seating", "breeze"]},
    {"id": "cs22", "name": "Heartland Mall Kovan", "type": "mall", "lat": 1.3594, "lng": 103.8850, "amenities": ["air-con", "water", "seating"]},
    {"id": "cs23", "name": "Clementi Mall", "type": "mall", "lat": 1.3150, "lng": 103.7645, "amenities": ["air-con", "water", "seating", "washroom"]},
    {"id": "cs24", "name": "Bedok Public Library", "type": "public", "lat": 1.3270, "lng": 103.9308, "amenities": ["air-con", "seating", "water", "washroom"]},
]

PREPAREDNESS_CHECKLISTS = {
    "heatwave": {
        "title": "Heatwave Preparedness",
        "items": [
            "Keep a reusable water bottle filled and within reach",
            "Plan indoor or shaded routes for daytime travel",
            "Identify the nearest air-conditioned cool spot to your home",
            "Wear light, loose, light-coloured clothing and a hat",
            "Check on elderly relatives and neighbours twice a day",
            "Keep electrolyte drinks / oral rehydration salts at home",
            "Avoid strenuous outdoor activity between 11am and 4pm",
            "Ensure fans / air-conditioning are working",
        ],
    },
    "outdoor_work": {
        "title": "Outdoor Worker Heat Safety",
        "items": [
            "Follow the work/rest guidance for today's heat stress level",
            "Drink 200-300ml of water every 15-20 minutes",
            "Take rest breaks in shaded or cooled areas",
            "Acclimatise gradually over the first 1-2 weeks",
            "Use the buddy system to watch for heat-illness signs",
            "Report dizziness, cramps or nausea immediately",
        ],
    },
    "extreme_weather": {
        "title": "Extreme Weather (Storm / Heavy Rain)",
        "items": [
            "Move indoors and away from windows during thunderstorms",
            "Avoid low-lying and flood-prone areas",
            "Keep a charged power bank and a small torch",
            "Save emergency numbers: SCDF 995, Police 999, NEA 1800-2255-632",
            "Unplug non-essential electrical appliances",
        ],
    },
}

# Work-rest guidance aligned to Singapore's heat stress advisory (simple labels for users)
WORK_REST_GUIDANCE = [
    {"level": "Low", "work": "Normal work", "rest": "Hydration breaks as needed", "color": "low"},
    {"level": "Moderate", "work": "45 min work", "rest": "15 min rest per hour", "color": "moderate"},
    {"level": "High", "work": "30 min work", "rest": "30 min rest per hour", "color": "high"},
    {"level": "Very High", "work": "15 min work", "rest": "45 min rest / suspend heavy work", "color": "extreme"},
]

SYMPTOMS = [
    {"id": "heavy_sweating", "label": "Heavy sweating"},
    {"id": "muscle_cramps", "label": "Muscle cramps"},
    {"id": "dizziness", "label": "Dizziness or light-headedness"},
    {"id": "headache", "label": "Headache"},
    {"id": "nausea", "label": "Nausea or vomiting"},
    {"id": "weak_pulse", "label": "Weak, rapid pulse"},
    {"id": "confusion", "label": "Confusion or slurred speech"},
    {"id": "no_sweating", "label": "Hot, dry skin (not sweating)"},
    {"id": "high_temp", "label": "Very high body temperature"},
    {"id": "fainting", "label": "Loss of consciousness / fainting"},
]

# Red-flag symptoms indicating possible heat stroke -> emergency
HEAT_STROKE_FLAGS = {"confusion", "no_sweating", "high_temp", "fainting"}


def assess_symptoms(selected_ids):
    selected = set(selected_ids)
    if selected & HEAT_STROKE_FLAGS:
        return {
            "severity": "emergency",
            "condition": "Possible Heat Stroke",
            "color": "extreme",
            "advice": [
                "Call SCDF 995 immediately — this is a medical emergency",
                "Move the person to a cool, shaded place",
                "Cool them rapidly: cold water, ice packs to neck/armpits/groin, fan",
                "Do NOT give fluids if the person is confused or unconscious",
                "Stay with them until help arrives",
            ],
        }
    if {"muscle_cramps", "dizziness", "headache", "nausea", "weak_pulse"} & selected:
        return {
            "severity": "caution",
            "condition": "Heat Exhaustion",
            "color": "high",
            "advice": [
                "Stop all activity and rest in a cool place",
                "Sip cool water or an electrolyte drink slowly",
                "Loosen clothing and apply cool, wet cloths to the skin",
                "Seek medical help if symptoms worsen or last over 1 hour",
            ],
        }
    if selected:
        return {
            "severity": "mild",
            "condition": "Early Heat Stress",
            "color": "moderate",
            "advice": [
                "Move to shade or an air-conditioned space",
                "Drink water and rest",
                "Monitor how you feel over the next 30 minutes",
            ],
        }
    return {
        "severity": "none",
        "condition": "No significant symptoms",
        "color": "low",
        "advice": ["Stay hydrated and take breaks from the heat."],
    }
