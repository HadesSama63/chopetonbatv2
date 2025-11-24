import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from scipy.optimize import least_squares
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
    st.title("Chope ton Bat Ultimate")
st.markdown("### Système de Triangulation (Ultimate 3D)")

# --- MOTEUR MATHÉMATIQUE PRO (MOINDRES CARRÉS) ---

def haversine_np(lon1, lat1, lon2, lat2):
    """
    Calcule la distance Haversine de manière vectorisée (compatible numpy)
    """
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6371 * c
    return km

def residuals(guess, points, radii):
    """
    Fonction de résidus pour least_squares.
    Calcule la différence entre la distance actuelle et le rayon cible pour chaque point.
    L'optimiseur cherche à rendre ces différences aussi proches de 0 que possible.
    """
    lat_guess, lon_guess = guess
    res = []
    for i in range(len(points)):
        # points[i] est (lat, lon)
        dist_calc = haversine_np(lon_guess, lat_guess, points[i][1], points[i][0])
        # On veut que (distance calculée - rayon donné) soit = 0
        res.append(dist_calc - radii[i])
    return np.array(res)

def solve_trilateration_robust(p1, r1, p2, r2, p3, r3):
    points = [p1, p2, p3]
    radii = [r1, r2, r3]
    
    # 1. Point de départ approximatif (moyenne simple)
    initial_guess = [
        np.mean([p[0] for p in points]),
        np.mean([p[1] for p in points])
    ]

    # 2. Résolution par Moindres Carrés Non-Linéaires (Trust Region Reflective)
    # C'est la méthode la plus robuste pour ce type de problème géométrique.
    result = least_squares(
        residuals, 
        initial_guess, 
        args=(points, radii),
        method='trf', # Très robuste pour les problèmes bornés
        loss='soft_l1', # Résistant aux données aberrantes
        ftol=1e-8,
        xtol=1e-8
    )
    
    return result.x[0], result.x[1]

def get_coords(address):
    geolocator = Nominatim(user_agent="triangulation_app_hades_pro")
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
        with st.spinner('Calcul de convergence optimal...'):
            p1 = get_coords(a1)
            p2 = get_coords(a2)
            p3 = get_coords(a3)

            if p1 and p2 and p3:
                # Appel du solveur robuste
                final_pos = solve_trilateration_robust(p1, d1, p2, d2, p3, d3)
                
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
    
    st.success(f"📍 Point de convergence optimal : {res[0]:.5f}, {res[1]:.5f}")
    
    # SETUP MAPBOX VECTOR
    tile_layer = "OpenStreetMap"
    attr = "OSM"
    
    if "MAPBOX_TOKEN" in st.secrets:
        token = st.secrets["MAPBOX_TOKEN"]
        # Utilisation du style "Streets" vectoriel (très propre) au lieu du satellite
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
        # Marge (Pointillés Gris)
        folium.Circle(pt, radius=(dist-m_err)*1000, color="#555555", weight=1, dash_array='5,5', fill=False, opacity=0.6).add_to(m)
        folium.Circle(pt, radius=(dist+m_err)*1000, color="#555555", weight=1, dash_array='5,5', fill=False, opacity=0.6).add_to(m)
        
        # Cercle exact (Bleu vif)
        folium.Circle(pt, radius=dist*1000, color="#007cbf", weight=2, fill=False).add_to(m)
        # Marqueur numéroté
        folium.Marker(pt, icon=folium.DivIcon(html=f"""<div style="font-family: sans-serif; color: white; background-color: #007cbf; width: 20px; height: 20px; border-radius: 50%; text-align: center; line-height: 20px;">{i+1}</div>""")).add_to(m)


    # CIBLE (Rouge vif avec halo)
    folium.Circle(res, radius=m_err*1000, color="red", weight=1, fill=True, fill_color="#ff0000", fill_opacity=0.2).add_to(m)
    folium.Marker(res, icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

    # --- EFFET 3D (Inclinaison forcée) ---
    m.get_root().html.add_child(folium.Element("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var map_instance = %s;
                // Inclinaison à 55 degrés pour l'effet 3D
                map_instance.getMap().setPitch(55);
                // Orientation vers le Nord
                map_instance.getMap().setBearing(0);
            });
        </script>
    """ % m.get_name()))

    st_folium(m, width=700, height=500)