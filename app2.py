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
    st.title("Chope ton Bat")
st.markdown("### Système de Triangulation (Ultimate)")

# --- MOTEUR MATHÉMATIQUE "MARGE-AWARE" ---

def haversine_scalar(lat1, lon1, lat2, lon2):
    """Distance précise sur une sphère (km)"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def cost_function_zones(coords, points, radii, margin):
    """
    C'est ici que la magie opère.
    Au lieu de pénaliser la distance exacte, on pénalise seulement
    si on est SORTI de la zone (Rayon +/- Marge).
    """
    lat, lon = coords
    total_penalty = 0
    
    for i in range(len(points)):
        target_dist = radii[i]
        actual_dist = haversine_scalar(lat, lon, points[i][0], points[i][1])
        
        # On calcule l'écart absolu par rapport au rayon idéal
        deviation = abs(actual_dist - target_dist)
        
        # Si l'écart est plus petit que la marge, le coût est 0 (on est dans la zone verte)
        # Sinon, le coût augmente
        penalty = max(0, deviation - margin)
        
        # On met au carré pour punir sévèrement les grands écarts
        total_penalty += penalty**2
        
    return total_penalty

def solve_trilateration_zones(p1, r1, p2, r2, p3, r3, margin):
    points = [p1, p2, p3]
    radii = [r1, r2, r3]
    
    # 1. Point de départ : Barycentre géométrique
    initial_guess = [
        np.mean([p[0] for p in points]),
        np.mean([p[1] for p in points])
    ]

    # 2. Minimisation de la fonction de coût "Zones"
    # On utilise Nelder-Mead car la fonction cost_function_zones n'est pas lisse (à cause du max(0, ...))
    result = minimize(
        cost_function_zones,
        initial_guess,
        args=(points, radii, margin),
        method='Nelder-Mead',
        tol=1e-7
    )
    
    return result.x[0], result.x[1]

def get_coords(address):
    geolocator = Nominatim(user_agent="triangulation_app_hades_zones")
    try:
        location = geolocator.geocode(address, timeout=10)
        return (location.latitude, location.longitude) if location else None
    except:
        return None

# --- UI ---
st.markdown("#### Paramètres Tactiques")
# Le slider définit maintenant la "Zone de vérité"
marge = st.slider("Marge d'erreur / Épaisseur de zone (km)", 0.1, 10.0, 1.0, 0.1)

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
        with st.spinner('Recherche de l\'intersection des zones...'):
            p1 = get_coords(a1)
            p2 = get_coords(a2)
            p3 = get_coords(a3)

            if p1 and p2 and p3:
                # On passe la marge à la fonction de résolution
                final_pos = solve_trilateration_zones(p1, d1, p2, d2, p3, d3, marge)
                
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
    
    st.success(f"📍 Zone d'intersection optimale : {res[0]:.5f}, {res[1]:.5f}")
    
    # SETUP MAPBOX
    tile_layer = "OpenStreetMap"
    attr = "OSM"
    if "MAPBOX_TOKEN" in st.secrets:
        token = st.secrets["MAPBOX_TOKEN"]
        tile_layer = f"https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={token}"
        attr = "Mapbox Streets"
    
    # Carte centrée
    m = folium.Map(location=res, zoom_start=13, tiles=None, control_scale=True)
    folium.TileLayer(tiles=tile_layer, attr=attr, detect_retina=True).add_to(m)

    # --- ÉLÉMENTS GRAPHIQUES ---
    for i, (pt, dist) in enumerate(pts):
        # On dessine la ZONE (La bande de tolérance)
        # Cercle Extérieur (Gris foncé)
        folium.Circle(pt, radius=(dist + m_err)*1000, color="#666", weight=1, dash_array='5,5', fill=False).add_to(m)
        # Cercle Intérieur (Gris foncé)
        folium.Circle(pt, radius=max(0, dist - m_err)*1000, color="#666", weight=1, dash_array='5,5', fill=False).add_to(m)
        
        # La ligne théorique (Bleue)
        folium.Circle(pt, radius=dist*1000, color="#2196F3", weight=2, fill=False, opacity=0.6).add_to(m)
        
        folium.Marker(pt, tooltip=f"Point {i+1}").add_to(m)

    # CIBLE (Rouge)
    # Le rayon rouge correspond maintenant visuellement à la marge d'erreur
    folium.Circle(res, radius=m_err*1000, color="red", weight=1, fill=True, fill_color="#ff0000", fill_opacity=0.3).add_to(m)
    folium.Marker(res, icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

    # --- EFFET 3D ---
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