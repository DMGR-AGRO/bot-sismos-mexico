import os
import time
import requests
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = "8107696402:AAEwS9w1AcFYY8jY-vrENEtcvkEcAjuq-QI"
CHAT_ID = -1003994301891 

# Bounding Box de México
MEXICO_BOUNDS = {
    "lat_min": 14.5, "lat_max": 32.7, 
    "lon_min": -118.4, "lon_max": -86.7
}

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

# --- 1. MONITOREO DE SISMOS (USGS - FEED DIARIO) ---
def monitorear_sismos():
    vistos = set()
    print("Iniciando monitoreo de sismos (Feed Diario)...")
    while True:
        try:
            # CAMBIO CLAVE: Usamos 'all_day' para no perder sismos con retraso de procesamiento
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            for sismo in data['features']:
                coords = sismo['geometry']['coordinates']
                lon, lat, s_id = coords[0], coords[1], sismo['id']
                
                # Filtrar zona geográfica
                if (MEXICO_BOUNDS["lat_min"] <= lat <= MEXICO_BOUNDS["lat_max"] and 
                    MEXICO_BOUNDS["lon_min"] <= lon <= MEXICO_BOUNDS["lon_max"]):
                    
                    if s_id not in vistos:
                        props = sismo['properties']
                        mag = props['mag']
                        
                        # Solo procesar si tiene magnitud (a veces la USGS sube eventos sin mag inicial)
                        if mag is not None and mag >= 2.5: 
                            # Hora local México (UTC -6)
                            fecha_mex = datetime.fromtimestamp(props['time'] / 1000.0) - timedelta(hours=6)
                            hora_txt = fecha_mex.strftime('%d/%m/%Y %H:%M:%S')
                            
                            mensaje = (f"⚠️ **SISMO DETECTADO (USGS)**\n\n"
                                       f"📈 **Magnitud:** {mag}\n"
                                       f"🕒 **Hora local:** {hora_txt}\n"
                                       f"📍 **Lugar:** {props['place']}\n"
                                       f"🌐 [Ver mapa y detalles]({props['url']})")
                            
                            enviar_telegram(mensaje)
                        
                        vistos.add(s_id)
        except Exception as e:
            print(f"Error en sismos: {e}")
            
        # Esperar 30 segundos entre consultas para mayor rapidez
        time.sleep(30)

# --- 2. MONITOREO DE HURACANES (NHC) ---
def monitorear_huracanes():
    vistos_h = set()
    while True:
        try:
            urls = ["https://www.nhc.noaa.gov/index-at.xml", "https://www.nhc.noaa.gov/index-ep.xml"]
            for url in urls:
                res = requests.get(url, timeout=10)
                root = ET.fromstring(res.content)
                for item in root.findall('.//item'):
                    title = item.find('title').text
                    if any(x in title for x in ["Tropical", "Hurricane", "Storm", "Depression"]):
                        if title not in vistos_h:
                            link = item.find('link').text
                            enviar_telegram(f"🌀 **ALERTA CICLÓNICA (NHC)**\n\n📢 {title}\n🌐 [Ver detalles]({link})")
                            vistos_h.add(title)
        except: pass
        time.sleep(1800)

# --- 3. MONITOREO VOLCÁNICO (CENAPRED) ---
def monitorear_volcanes():
    vistos_v = set()
    url_cenapred = "https://www.gob.mx/cenapred/archivo/articulos.rss"
    while True:
        try:
            res = requests.get(url_cenapred, timeout=10)
            root = ET.fromstring(res.content)
            for item in root.findall('.//item'):
                title = item.find('title').text
                if "Popocatépetl" in title:
                    if title not in vistos_v:
                        link = item.find('link').text
                        enviar_telegram(f"🌋 **ACTIVIDAD VOLCÁNICA (CENAPRED)**\n\n📢 {title}\n🌐 [Ver reporte]({link})")
                        vistos_v.add(title)
        except: pass
        time.sleep(3600)

@app.route('/')
def home():
    return "✅ Centro de Monitoreo Multiamenaza Activo (Sismos: Diario/30s)"

if __name__ == "__main__":
    # Iniciar hilos
    threading.Thread(target=monitorear_sismos, daemon=True).start()
    threading.Thread(target=monitorear_huracanes, daemon=True).start()
    threading.Thread(target=monitorear_volcanes, daemon=True).start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
