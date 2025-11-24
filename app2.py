import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from scipy.optimize import differential_evolution
import math
from PIL import Image
import numpy as np

# --- CONFIGURATION ---
st.set_page_config(page_title=":clown: Chope ton Bat :clown: ", page_icon="🦇", layout="centered")

# CSS
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        height: 3em;
        border-radius: 10px;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- SESSION ---
if 'resultat' not in st.session_state: st.session_state.resultat = None
if 'coords_points' not in st.session_state: st.session_state.coords_points = None
if 'marge_erreur' not in st.session_state: st.session_state.marge_erreur = 1.0

# --- HEADER ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    try:
        image = Image.open("hades.png")
        st.image(image, width=200)
    except:
        pass
with col_title:
    st.title("Chope ton Bat")
st.markdown("### Système de Triangulation (Hades Edition)")

# --- MOTEUR MATHÉMATIQUE (ÉVOLUTION DIFFÉRENTIELLE) ---

def haversine_scalar(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def cost_function_zones_global(coords, points, radii, margin):
    lat, lon = coords
    total_penalty = 0
    for i in range(len(points)):
        target_dist = radii[i]
        actual_dist = haversine_scalar(lat, lon, points[i][0], points[i][1])
        deviation = abs(actual_dist - target_dist)
        penalty = max(0, deviation - margin)
        total_penalty += penalty**2
    return total_penalty

def solve_trilateration_global(p1, r1, p2, r2, p3, r3, margin):
    points = [p1, p2, p3]
    radii = [r1, r2, r3]
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    max_r = max(radii)
    lat_margin = max_r / 110.574 + 2 
    lon_margin = max_r / (111.320 * math.cos(math.radians(np.mean(lats)))) + 2

    bounds = [
        (min(lats) - lat_margin, max(lats) + lat_margin),
        (min(lons) - lon_margin, max(lons) + lon_margin)
    ]

    result = differential_evolution(
        cost_function_zones_global,
        bounds,
        args=(points, radii, margin),
        strategy='best1bin',
        maxiter=1000,
        popsize=15,
        tol=0.01,
        mutation=(0.5, 1),
        recombination=0.7,
        seed=42,
        workers=-1
    )
    return result.x[0], result.x[1]

def get_coords(address):
    geolocator = Nominatim(user_agent="triangulation_app_hades_custom")
    try:
        location = geolocator.geocode(address, timeout=10)
        return (location.latitude, location.longitude) if location else None
    except:
        return None

# --- UI ---
st.markdown("#### Paramètres Tactiques")
marge = st.slider("Marge d'erreur / Épaisseur de zone (km)", 0.1, 50.0, 1.1, 0.1)

c1, c2 = st.columns([3, 1])
a1 = c1.text_input("Adresse 1", value="Tour Eiffel, Paris")
d1 = c2.number_input("Dist 1 (km)", min_value=0.1, value=777.19, format="%.2f")

c3, c4 = st.columns([3, 1])
a2 = c3.text_input("Adresse 2", value="Colisée, Rome")
d2 = c4.number_input("Dist 2 (km)", min_value=0.1, value=1886.20, format="%.2f")

c5, c6 = st.columns([3, 1])
a3 = c5.text_input("Adresse 3", value="Statue de la Liberté, New York")
d3 = c6.number_input("Dist 3 (km)", min_value=0.1, value=5071.90, format="%.2f")

# --- EXECUTION ---
if st.button("LANCER LA TRIANGULATION"):
    if a1 and a2 and a3 and d1 and d2 and d3:
        with st.spinner('Scan global en cours...'):
            p1 = get_coords(a1)
            p2 = get_coords(a2)
            p3 = get_coords(a3)

            if p1 and p2 and p3:
                final_pos = solve_trilateration_global(p1, d1, p2, d2, p3, d3, marge)
                st.session_state.resultat = final_pos
                st.session_state.marge_erreur = marge
                st.session_state.coords_points = [(p1, d1), (p2, d2), (p3, d3)]
            else:
                st.error("Adresse introuvable.")
    else:
        st.warning("Données manquantes")

# --- CARTE MAPBOX CUSTOM ---
if st.session_state.resultat is not None:
    res = st.session_state.resultat
    pts = st.session_state.coords_points
    m_err = st.session_state.marge_erreur
    
    st.success(f"📍 Zone d'intersection : {res[0]:.5f}, {res[1]:.5f}")
    
    # SETUP MAPBOX CUSTOM STYLE
    tile_layer = "OpenStreetMap"
    attr = "OSM"
    if "MAPBOX_TOKEN" in st.secrets:
        token = st.secrets["MAPBOX_TOKEN"]
        # ICI ON UTILISE TON STYLE HADES63
        style_user = "hades63"
        style_id = "ckrw7gl1g5hc217pfq2vz8we8"
        tile_layer = f"https://api.mapbox.com/styles/v1/{style_user}/{style_id}/tiles/{{z}}/{{x}}/{{y}}?access_token={token}"
        attr = "Mapbox Custom Hades"
    
    # Carte
    m = folium.Map(location=res, zoom_start=6, tiles=None, control_scale=True)
    folium.TileLayer(tiles=tile_layer, attr=attr, detect_retina=True).add_to(m)

    # --- ÉLÉMENTS GRAPHIQUES (Couleurs adaptées au style sombre probable) ---
    for i, (pt, dist) in enumerate(pts):
        # Bandes de tolérance (Blanc transparent pour ressortir sur du sombre)
        folium.Circle(pt, radius=(dist + m_err)*1000, color="#ffffff", weight=1, dash_array='5,5', fill=False, opacity=0.4).add_to(m)
        folium.Circle(pt, radius=max(0, dist - m_err)*1000, color="#ffffff", weight=1, dash_array='5,5', fill=False, opacity=0.4).add_to(m)
        # Ligne exacte (Cyan Néon)
        folium.Circle(pt, radius=dist*1000, color="#00FFFF", weight=2, fill=False).add_to(m)

    # CIBLE (Rouge Vif)
    folium.Circle(res, radius=m_err*1000, color="#FF0033", weight=1, fill=True, fill_color="#FF0033", fill_opacity=0.3).add_to(m)
    folium.Marker(res, icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

    # --- EFFET PERSPECTIVE 3D ---
    m.get_root().html.add_child(folium.Element("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var map_instance = %s;
                map_instance.getMap().setPitch(60); 
                map_instance.getMap().setBearing(0);
            });
        </script>
    """ % m.get_name()))

    st_folium(m, width=700, height=500)