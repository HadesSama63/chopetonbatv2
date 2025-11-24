import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from scipy.optimize import minimize
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
    st.title("Chope ton Bat Ultimate Edition")
st.markdown("### Système de Triangulation Tactique (Moteur SciPy)")

# --- MOTEUR MATHÉMATIQUE SCIENTIFIQUE ---

def earth_dist(lat1, lon1, lat2, lon2):
    """Distance précise sur une sphère (Haversine) pour l'optimiseur"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def error_function(guess, points, radii):
    """Fonction que l'IA doit réduire à 0"""
    lat, lon = guess
    err = 0
    for i in range(3):
        # On calcule la différence entre la distance réelle et le rayon voulu
        dist_calc = earth_dist(lat, lon, points[i][0], points[i][1])
        err += (dist_calc - radii[i])**2
    return err

def solve_trilateration(p1, r1, p2, r2, p3, r3):
    # 1. Point de départ intelligent (Barycentre pondéré)
    # On démarre la recherche au milieu des 3 points
    initial_guess = [
        (p1[0] + p2[0] + p3[0]) / 3,
        (p1[1] + p2[1] + p3[1]) / 3
    ]
    
    points = [p1, p2, p3]
    radii = [r1, r2, r3]

    # 2. Résolution par méthode de Nelder-Mead (Robuste pour la géométrie non-linéaire)
    result = minimize(
        error_function, 
        initial_guess, 
        args=(points, radii),
        method='Nelder-Mead',
        tol=1e-6
    )
    
    return result.x[0], result.x[1]

def get_coords(address):
    geolocator = Nominatim(user_agent="triangulation_app_hades_final")
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
        with st.spinner('Calcul scientifique de la position...'):
            p1 = get_coords(a1)
            p2 = get_coords(a2)
            p3 = get_coords(a3)

            if p1 and p2 and p3:
                # Appel du solveur SciPy
                final_pos = solve_trilateration(p1, d1, p2, d2, p3, d3)
                
                st.session_state.resultat = final_pos
                st.session_state.marge_erreur = marge
                st.session_state.coords_points = [(p1, d1), (p2, d2), (p3, d3)]
            else:
                st.error("Adresse introuvable.")
    else:
        st.warning("Données manquantes")

# --- CARTE 3D (VUE DRONE) ---
if st.session_state.resultat is not None:
    res = st.session_state.resultat
    pts = st.session_state.coords_points
    m_err = st.session_state.marge_erreur
    
    st.success(f"📍 Cible : {res[0]:.5f}, {res[1]:.5f}")
    
    # SETUP MAPBOX SATELLITE 3D
    # Si pas de token, fallback sur OpenStreetMap
    tile_layer = "OpenStreetMap"
    attr = "OSM"
    
    if "MAPBOX_TOKEN" in st.secrets:
        token = st.secrets["MAPBOX_TOKEN"]
        # Utilisation des tuiles Satellite
        tile_layer = f"https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={token}"
        attr = "Mapbox Satellite"
    
    # Création de la carte
    # LOCATION : Centre sur le résultat
    m = folium.Map(
        location=res, 
        zoom_start=14, # Zoom assez proche pour voir l'effet 3D
        tiles=None,
        control_scale=True
    )
    
    # Ajout du fond de carte
    folium.TileLayer(tiles=tile_layer, attr=attr, name="Satellite").add_to(m)

    # --- ÉLÉMENTS GRAPHIQUES ---
    for pt, dist in pts:
        # Cercles de marge (Pointillés blancs)
        folium.Circle(pt, radius=(dist-m_err)*1000, color="white", weight=1, dash_array='5,5', fill=False, opacity=0.5).add_to(m)
        folium.Circle(pt, radius=(dist+m_err)*1000, color="white", weight=1, dash_array='5,5', fill=False, opacity=0.5).add_to(m)
        
        # Cercle exact (Cyan)
        folium.Circle(pt, radius=dist*1000, color="#00FFFF", weight=2, fill=False).add_to(m)

    # CIBLE (Rouge)
    folium.Circle(res, radius=m_err*1000, color="#FF0000", fill=True, fill_opacity=0.3).add_to(m)
    folium.Marker(res, icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

    # --- EFFET 3D ---
    # C'est ici que la magie opère : on force l'inclinaison (pitch) via JavaScript
    # Car Folium python ne l'expose pas directement facilement
    m.get_root().html.add_child(folium.Element("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var map_instance = %s;
                // On force l'inclinaison à 60 degrés (Vue Drone)
                map_instance.getMap().setPitch(60);
                map_instance.getMap().setBearing(0);
            });
        </script>
    """ % m.get_name()))

    st_folium(m, width=700, height=500)