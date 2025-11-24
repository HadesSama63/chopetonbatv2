import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import math
from PIL import Image

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Chope ton Bat", page_icon="🦇", layout="centered")

# Style CSS
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

# --- GESTION DE LA MÉMOIRE ---
if 'resultat' not in st.session_state:
    st.session_state.resultat = None
if 'coords_points' not in st.session_state:
    st.session_state.coords_points = None
if 'marge_erreur' not in st.session_state:
    st.session_state.marge_erreur = 1.0

# --- EN-TÊTE ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    try:
        image = Image.open("hades.png") 
        st.image(image, width=100)
    except FileNotFoundError:
        st.warning("Logo?")
with col_title:
    st.title("Chope ton Bat")
st.markdown("### Système de Triangulation Tactique")

# --- MOTEUR MATHÉMATIQUE ---

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def trilateration_optimize(p1, r1, p2, r2, p3, r3):
    lat = (p1[0] + p2[0] + p3[0]) / 3
    lon = (p1[1] + p2[1] + p3[1]) / 3
    
    step_size = 1.0
    min_step = 0.00001
    
    for i in range(2000):
        d1 = haversine_distance(lat, lon, p1[0], p1[1])
        d2 = haversine_distance(lat, lon, p2[0], p2[1])
        d3 = haversine_distance(lat, lon, p3[0], p3[1])
        
        current_error = (d1 - r1)**2 + (d2 - r2)**2 + (d3 - r3)**2
        
        if step_size < min_step:
            break
            
        best_lat, best_lon = lat, lon
        best_err = current_error
        found_better = False
        
        moves = [(step_size, 0), (-step_size, 0), (0, step_size), (0, -step_size)]
        
        for d_lat, d_lon in moves:
            test_lat = lat + d_lat
            test_lon = lon + d_lon
            td1 = haversine_distance(test_lat, test_lon, p1[0], p1[1])
            td2 = haversine_distance(test_lat, test_lon, p2[0], p2[1])
            td3 = haversine_distance(test_lat, test_lon, p3[0], p3[1])
            test_err = (td1 - r1)**2 + (td2 - r2)**2 + (td3 - r3)**2
            
            if test_err < best_err:
                best_lat, best_lon = test_lat, test_lon
                best_err = test_err
                found_better = True

        if found_better:
            lat, lon = best_lat, best_lon
        else:
            step_size /= 2.0

    return lat, lon

def get_coords(address):
    geolocator = Nominatim(user_agent="triangulation_app_hades_v4")
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            return None
    except:
        return None

# --- FORMULAIRE ---
st.markdown("#### Paramètres")
marge = st.slider("Marge d'erreur visuelle (km)", 0.1, 5.0, 1.0, 0.1)

col1, col2 = st.columns([3, 1])
addr1 = col1.text_input("Adresse 1", placeholder="Ex: Tour Eiffel, Paris")
dist1 = col2.number_input("Dist 1 (km)", min_value=0.1, format="%.2f")

col3, col4 = st.columns([3, 1])
addr2 = col3.text_input("Adresse 2")
dist2 = col4.number_input("Dist 2 (km)", min_value=0.1, format="%.2f")

col5, col6 = st.columns([3, 1])
addr3 = col5.text_input("Adresse 3")
dist3 = col6.number_input("Dist 3 (km)", min_value=0.1, format="%.2f")

# --- ACTION ---
if st.button("LANCER LA TRIANGULATION"):
    if addr1 and addr2 and addr3 and dist1 > 0 and dist2 > 0 and dist3 > 0:
        with st.spinner('Triangulation satellite en cours...'):
            c1 = get_coords(addr1)
            c2 = get_coords(addr2)
            c3 = get_coords(addr3)

            if c1 and c2 and c3:
                final_pos = trilateration_optimize(c1, dist1, c2, dist2, c3, dist3)
                
                st.session_state.resultat = final_pos
                st.session_state.marge_erreur = marge
                st.session_state.coords_points = [(c1, dist1), (c2, dist2), (c3, dist3)]
            else:
                st.error("Une adresse est introuvable.")
    else:
        st.warning("Remplissez tout.")

# --- AFFICHAGE CARTE MAPBOX ---
if st.session_state.resultat is not None:
    res = st.session_state.resultat
    points = st.session_state.coords_points
    marge_actuelle = st.session_state.marge_erreur
    
    st.success(f"📍 Cible localisée : {res[0]:.5f}, {res[1]:.5f}")
    
    # Configuration Mapbox
    # Si le token n'est pas trouvé (local sans secrets), on utilise OpenStreetMap par défaut pour éviter le crash
    if "MAPBOX_TOKEN" in st.secrets:
        mapbox_token = st.secrets["MAPBOX_TOKEN"]
        
        # STYLE SATELLITE (Tactique) :
        tiles_url = f"https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={mapbox_token}"
        
        # SI TU VEUX LE STYLE DARK (Hades), décommente cette ligne et commente celle du dessus :
        # tiles_url = f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/{{z}}/{{x}}/{{y}}?access_token={mapbox_token}"
        
        attr = "Mapbox"
    else:
        tiles_url = "OpenStreetMap"
        attr = "OpenStreetMap"
        st.warning("⚠️ Clé Mapbox non trouvée dans les secrets. Affichage standard.")

    # Création de la carte
    m = folium.Map(location=res, zoom_start=12, tiles=None) # tiles=None car on ajoute le calque manuellement
    
    # Ajout du fond de carte Mapbox
    folium.TileLayer(tiles=tiles_url, attr=attr, name="Mapbox").add_to(m)
    
    # Affichage des éléments graphiques
    for i, (pt, dist) in enumerate(points):
        # Cercles en BLANC pour bien ressortir sur le satellite
        r_min = max(0, dist - marge_actuelle) * 1000
        folium.Circle(pt, radius=r_min, color="white", weight=1, fill=False, opacity=0.5, dash_array='5, 5').add_to(m)
        
        r_max = (dist + marge_actuelle) * 1000
        folium.Circle(pt, radius=r_max, color="white", weight=1, fill=False, opacity=0.5, dash_array='5, 5').add_to(m)

        folium.Circle(pt, radius=dist*1000, color="#00FFFF", weight=2, fill=False).add_to(m) # Cyan néon
        folium.Marker(pt, tooltip=f"Point {i+1}", icon=folium.Icon(color="blue", icon="map-marker")).add_to(m)
    
    folium.Circle(res, radius=marge_actuelle*1000, color="#FF3333", fill=True, fill_opacity=0.4).add_to(m)
    folium.Marker(res, icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

    st_folium(m, width=700)