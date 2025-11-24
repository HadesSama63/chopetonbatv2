import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from scipy.optimize import differential_evolution
import math
from PIL import Image
import numpy as np

# --- CONFIGURATION ---
st.set_page_config(page_title="Chope ton Bat V2", page_icon="🦇", layout="centered")

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
        st.image(image, width=100)
    except:
        pass
with col_title:
    st.title("Chope ton Bat")
st.markdown("### Système de Triangulation (Moteur Ultimate)")

# --- MOTEUR MATHÉMATIQUE GLOBAL (EVOLUTION DIFFÉRENTIELLE) ---

def haversine_scalar(lat1, lon1, lat2, lon2):
    """Distance précise sur une sphère (Haversine)"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def error_function_global(coords, points, radii):
    """
    Fonction d'erreur pour l'évolution différentielle.
    coords: [lat, lon] candidat
    """
    lat, lon = coords
    total_error = 0
    
    for i in range(len(points)):
        p_lat, p_lon = points[i]
        target_radius = radii[i]
        
        # Distance calculée entre le point testé et l'antenne
        dist = haversine_scalar(lat, lon, p_lat, p_lon)
        
        # On ajoute l'erreur au carré
        total_error += (dist - target_radius)**2
        
    return total_error

def solve_trilateration_global(p1, r1, p2, r2, p3, r3):
    points = [p1, p2, p3]
    radii = [r1, r2, r3]
    
    # 1. Définir la ZONE DE RECHERCHE (Bounding Box)
    # On prend les lats/lons min et max des points et on ajoute une marge
    # pour être sûr que l'intersection est dedans.
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    max_dist = max(radii) * 2 / 111.0 # Conversion approx km vers degrés pour la marge
    
    bounds = [
        (min(lats) - max_dist, max(lats) + max_dist), # Latitude min/max
        (min(lons) - max_dist, max(lons) + max_dist)  # Longitude min/max
    ]

    # 2. Algorithme d'Évolution Différentielle
    # Il "parachutes" des points partout dans la zone et fait survivre les meilleurs.
    result = differential_evolution(
        error_function_global,
        bounds,
        args=(points, radii),
        strategy='best1bin',
        maxiter=1000,
        popsize=15,
        tol=1e-7,
        mutation=(0.5, 1),
        recombination=0.7
    )
    
    return result.x[0], result.x[1]

def get_coords(address):
    geolocator = Nominatim(user_agent="triangulation_app_hades_evo")
    try:
        location = geolocator.geocode(address, timeout=10)
        return (location.latitude, location.longitude) if location else None
    except:
        return None

# --- UI ---
st.markdown("#### Paramètres")
marge = st.slider("Marge d'erreur visuelle (km)", 0.1, 10.0, 1.0, 0.1)

c1, c2 = st.columns([3, 1])
a1 = c1.text_input("Adresse 1")
d1 = c2.number_input("Dist 1 (km)", min_value=0.1, format="%.2f")

c3, c4 = st.columns([3, 1])
a2 = c3.text_input("Adresse 2")
d2 = c4.number_input("Dist 2 (km)", min_value=0.1, format="%.2f")

c5, c6 = st.columns([3, 1])
a3 = c5.text_input("Adresse 3")
d3 = c6.number_input("Dist 3 (km)", min_value=0.1, format="%.2f")

# --- EXECUTION ---
if st.button("LANCER LA TRIANGULATION"):
    if a1 and a2 and a3 and d1 and d2 and d3:
        with st.spinner('Scan global de la zone (Differential Evolution)...'):
            p1 = get_coords(a1)
            p2 = get_coords(a2)
            p3 = get_coords(a3)

            if p1 and p2 and p3:
                # Appel du solveur global
                final_pos = solve_trilateration_global(p1, d1, p2, d2, p3, d3)
                
                st.session_state.resultat = final_pos
                st.session_state.marge_erreur = marge
                st.session_state.coords_points = [(p1, d1), (p2, d2), (p3, d3)]
            else:
                st.error("Adresse introuvable.")
    else:
        st.warning("Données manquantes")

# --- CARTE VECTEUR 3D ---
if st.session_state.resultat is not None:
    res = st.session_state.resultat
    pts = st.session_state.coords_points
    m_err = st.session_state.marge_erreur
    
    st.success(f"📍 Meilleure convergence trouvée : {res[0]:.5f}, {res[1]:.5f}")
    
    # SETUP MAPBOX VECTOR
    tile_layer = "OpenStreetMap"
    attr = "OSM"
    
    if "MAPBOX_TOKEN" in st.secrets:
        token = st.secrets["MAPBOX_TOKEN"]
        # Style Vectoriel Streets
        tile_layer = f"https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={token}"
        attr = "Mapbox Streets"
    
    # Création de la carte
    m = folium.Map(
        location=res, 
        zoom_start=13,
        tiles=None,
        control_scale=True
    )
    
    folium.TileLayer(tiles=tile_layer, attr=attr, name="Vector Map", detect_retina=True).add_to(m)

    # --- ÉLÉMENTS GRAPHIQUES ---
    for i, (pt, dist) in enumerate(pts):
        # Marge (Gris)
        folium.Circle(pt, radius=(dist-m_err)*1000, color="#666", weight=1, dash_array='5,5', fill=False, opacity=0.5).add_to(m)
        folium.Circle(pt, radius=(dist+m_err)*1000, color="#666", weight=1, dash_array='5,5', fill=False, opacity=0.5).add_to(m)
        
        # Cercle exact (Bleu)
        folium.Circle(pt, radius=dist*1000, color="#2196F3", weight=2, fill=False).add_to(m)
        
        # Marqueur
        folium.Marker(pt, tooltip=f"Repère {i+1}").add_to(m)


    # CIBLE (Rouge avec Pulsation simulée par 2 cercles)
    folium.Circle(res, radius=m_err*1000, color="red", weight=1, fill=True, fill_color="#ff0000", fill_opacity=0.3).add_to(m)
    folium.Circle(res, radius=(m_err*1000)/3, color="red", weight=2, fill=True, fill_color="#ff0000", fill_opacity=0.8).add_to(m)
    folium.Marker(res, icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

    # --- EFFET 3D ---
    m.get_root().html.add_child(folium.Element("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var map_instance = %s;
                map_instance.getMap().setPitch(60); // Inclinaison max
                map_instance.getMap().setBearing(0);
            });
        </script>
    """ % m.get_name()))

    st_folium(m, width=700, height=500)