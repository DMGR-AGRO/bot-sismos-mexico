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
CHAT_ID = -1003994301891  # Limpiado espacio invisible

# Bounding Box Regional (México + Guatemala)
REGION_BOUNDS = {
    "lat_min": 12.0,  
    "lat_max": 35.0,  
    "lon_min": -118.0, 
    "lon_max": -87.0  
}

# Set global para que no se borre fácilmente si la función se re-ejecuta internamente
notificados = set()

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            print(f"Error de Telegram (Status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"Error crítico enviando a Telegram: {e}")

# --- 1. MONITOREO DE SISMOS (USGS) ---
def monitorear_sismos():
    global notificados
    print("Iniciando monitoreo sísmico regional (MX-GT)...")
    
    while True:
        try:
            # CAMBIO: Usamos el feed de la ÚLTIMA HORA para mayor velocidad y menor carga
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for sismo in data.get('features', []):
                    s_id = sismo['id']
                    
                    if s_id in notificados:
                        continue

                    coords = sismo['geometry']['coordinates']
                    lon, lat = coords[0], coords[1]
                    
                    # 1. Filtro Geográfico Regional
                    if (REGION_BOUNDS["lat_min"] <= lat <= REGION_BOUNDS["lat_max"] and 
                        REGION_BOUNDS["lon_min"] <= lon <= REGION_BOUNDS["lon_max"]):
                        
                        props = sismo['properties']
                        mag = props.get('mag')
                        
                        # 2. Filtro de Magnitud (Mayor o igual a 4.0)
                        if mag is not None and mag >= 4.0:
                            # Hora local (UTC -6)
                            fecha_local = datetime.fromtimestamp(props['time'] / 1000.0) - timedelta(hours=6)
                            hora_txt = fecha_local.strftime('%d/%m/%Y %H:%M:%S')
                            
                            mensaje = (f"⚠️ **SISMO DETECTADO**\n\n"
                                       f"📈 **Magnitud:** {mag}\n"
                                       f"🕒 **Hora local (UTC-6):** {hora_txt}\n"
                                       f"📍 **Lugar:** {props['place']}\n"
                                       f"🌐 [Ver mapa y detalles]({props['url']})")
                            
                            enviar_telegram(mensaje)
                            notificados.add(s_id) 
            else:
                print(f"USGS respondió con código de error: {response.status_code}")
                                
        except Exception as e:
            print(f"Error en hilo de sismos: {e}")
            
        time.sleep(30) # Revisión cada 30 segundos

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
        except Exception as e:
            print(f"Error en hilo de huracanes: {e}")
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
        except Exception as e:
            print(f"Error en hilo de volcanes: {e}")
        time.sleep(3600)

@app.route('/')
def home():
    return "✅ Centro de Monitoreo Multiamenaza (MX-GT) Activo"

if __name__ == "__main__":
    # Iniciar procesos en hilos separados
    threading.Thread(target=monitorear_sismos, daemon=True).start()
    threading.Thread(target=monitorear_huracanes, daemon=True).start()
    threading.Thread(target=monitorear_volcanes, daemon=True).start()
    
    # Puerto dinámico para despliegue
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
