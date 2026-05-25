import os
import time
import requests
import threading
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = "8107696402:AAEwS9w1AcFYY8jY-vrENEtcvkEcAjuq-QI"
CHAT_ID = -1003994301891  # Identificador de Telegram sin espacios ocultos

# Bounding Box Regional (México + Guatemala)
REGION_BOUNDS = {
    "lat_min": 12.0,  
    "lat_max": 35.0,  
    "lon_min": -118.0, 
    "lon_max": -87.0  
}

# Registros de Namespaces obligatorios para el XML de la NOAA / NHC
NAMESPACES = {
    'georss': 'http://www.georss.org/georss',
    'nhc': 'https://www.nhc.noaa.gov'
}

# --- MEMORIA GLOBAL DE NOTIFICACIONES ---
notificados_sismos = set()
vistos_huracanes = set()
vistos_volcanes = set()

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
    global notificados_sismos
    print("Iniciando monitoreo sísmico regional (MX-GT)...")
    
    while True:
        try:
            # Feed de la ÚLTIMA HORA para optimizar consumo y procesar eventos inmediatos
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for sismo in data.get('features', []):
                    s_id = sismo['id']
                    
                    if s_id in notificados_sismos:
                        continue

                    coords = sismo['geometry']['coordinates']
                    lon, lat = coords[0], coords[1]
                    
                    # Filtro Geográfico Regional
                    if (REGION_BOUNDS["lat_min"] <= lat <= REGION_BOUNDS["lat_max"] and 
                        REGION_BOUNDS["lon_min"] <= lon <= REGION_BOUNDS["lon_max"]):
                        
                        props = sismo['properties']
                        mag = props.get('mag')
                        
                        # Filtro de Magnitud (Mínimo 4.0)
                        if mag is not None and mag >= 4.0:
                            # Conversión a Hora local (UTC -6)
                            fecha_local = datetime.fromtimestamp(props['time'] / 1000.0) - timedelta(hours=6)
                            hora_txt = fecha_local.strftime('%d/%m/%Y %H:%M:%S')
                            
                            mensaje = (f"⚠️ **SISMO DETECTADO (REGIONAL)**\n\n"
                                       f"📈 **Magnitud:** {mag}\n"
                                       f"🕒 **Hora local (UTC-6):** {hora_txt}\n"
                                       f"📍 **Lugar:** {props['place']}\n"
                                       f"🌐 [Ver mapa y detalles]({props['url']})")
                            
                            enviar_telegram(mensaje)
                            notificados_sismos.add(s_id) 
            else:
                print(f"USGS respondió con código de error: {response.status_code}")
                                
        except Exception as e:
            print(f"Error en hilo de sismos: {e}")
            
        time.sleep(30)  # Revisión estructural cada 30 segundos

# --- 2. MONITOREO DE HURACANES (NHC / NOAA) ---
def monitorear_huracanes():
    global vistos_huracanes
    print("Iniciando monitoreo de ciclones con rastreo de actualizaciones (NHC)...")
    
    while True:
        try:
            # Tus dos URLs originales e intactas para el Atlántico y el Pacífico Este
            urls = ["https://www.nhc.noaa.gov/index-at.xml", "https://www.nhc.noaa.gov/index-ep.xml"]
            
            for url in urls:
                res = requests.get(url, timeout=10)
                if res.status_code != 200:
                    continue
                    
                root = ET.fromstring(res.content)
                cuenca = "ATLÁNTICO / CARIBE" if "index-at" in url else "PACÍFICO ESTE"
                
                for item in root.findall('.//item'):
                    title = item.find('title').text
                    
                    # Filtros de control: Ignorar periodos de inactividad o reportes rutinarios sin peligro
                    if "no tropical cyclones" in title.lower():
                        continue
                    
                    desc_text = item.find('description').text or ""
                    if "formation is not expected" in desc_text.lower() and "Tropical Weather Outlook" in title:
                        continue
                    
                    # Extraer fecha/hora del boletín específico
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "No especificada"
                    
                    # Firma única (Título + Hora de emisión) para capturar actualizaciones horarias del mismo fenómeno
                    firma_alerta = f"{title}_{pub_date}"
                    
                    if firma_alerta not in vistos_huracanes:
                        link = item.find('link').text
                        
                        # Extracción de datos geoespaciales y meteorológicos del XML de la NOAA
                        punto_geo = item.find('georss:point', NAMESPACES)
                        coordenadas = punto_geo.text if punto_geo is not None else "No disponible"
                        
                        viento_elem = item.find('nhc:wind', NAMESPACES)
                        presion_elem = item.find('nhc:pressure', NAMESPACES)
                        
                        viento = viento_elem.text if viento_elem is not None else None
                        presion = presion_elem.text if presion_elem is not None else None
                        
                        detalles_tecnicos = ""
                        if coordenadas != "No disponible":
                            detalles_tecnicos += f"📍 **Ubicación (Lat, Lon):** {coordenadas}\n"
                        if viento:
                            try:
                                v_kmh = round(float(viento.split()[0]) * 1.852)
                                detalles_tecnicos += f"💨 **Vientos máximos:** {viento} (~{v_kmh} km/h)\n"
                            except:
                                detalles_tecnicos += f"💨 **Vientos máximos:** {viento}\n"
                        if presion:
                            detalles_tecnicos += f"📉 **Presión Mínima:** {presion}\n"

                        # Asignación de semáforo de emojis según el boletín
                        emoji = "🌀"
                        if "Hurricane" in title or "Huracán" in title: emoji = "🔴 **[ACTUALIZACIÓN DE HURACÁN]**"
                        elif "Storm" in title: emoji = "⛈️ **[ACTUALIZACIÓN TORMENTA]**"
                        elif "Depression" in title: emoji = "🌧️ **[ACTUALIZACIÓN DEPRESIÓN]**"
                        elif "Disturbance" in title: emoji = "🟡 **[MONITOREO DE INESTABILIDAD]**"

                        mensaje = (
                            f"{emoji} **ALERTA CICLÓNICA ({cuenca})**\n\n"
                            f"📢 **Fenómeno:** {title}\n"
                            f"{detalles_tecnicos}"
                            f"📅 **Emisión del boletín:** {pub_date}\n\n"
                            f"🌐 [Ver trayectoria y modelos en vivo]({link})"
                        )
                        
                        enviar_telegram(mensaje)
                        vistos_huracanes.add(firma_alerta)
                        
        except Exception as e:
            print(f"Error en hilo de huracanes: {e}")
            
        time.sleep(600)  # Consulta cada 10 minutos (varias veces al día)

# --- 3. MONITOREO VOLCÁNICO (WEB SCRAPING DIRECTO A CENAPRED) ---
# --- 3. MONITOREO VOLCÁNICO (WEB SCRAPING OPTIMIZADO PARA LA MAQUETACIÓN ACTUAL) ---
def monitorear_volcanes():
    global vistos_volcanes
    # Apuntamos a la raíz para asegurar capturar la estructura principal
    url_principal = "https://www.gob.mx/cenapred"
    print("Iniciando monitoreo volcánico mediante scraping adaptativo...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    while True:
        try:
            res = requests.get(url_principal, headers=headers, timeout=15)
            
            if res.status_code == 200:
                html_content = res.text
                
                # Buscaremos bloques de artículos. Gob.mx suele envolver estas tarjetas en contenedores.
                # Esta nueva expresión regular busca CUALQUIER link que apunte a "articulos" 
                # (soportando opcionalmente si lleva '/es/', '/en/', etc.)
                patron_links = r'href="([^"]*cenapred/[^"]*articulos/[^"]+)"'
                enlaces_articulos = re.findall(patron_links, html_content)
                
                for link in enlaces_articulos:
                    # Asegurar que el link sea una URL absoluta completa
                    link_completo = link if link.startswith("http") else f"https://www.gob.mx{link}"
                    
                    # Para extraer el título de la tarjeta de forma segura, podemos buscar el texto 
                    # que está un poco antes o después de ese link en el HTML. 
                    # Pero para asegurar la alerta inmediata, usaremos una validación infalible:
                    # Si el link completo o el contexto cercano contiene "popocatepetl", es nuestra meta.
                    
                    # Vamos a aislar un "bloque" de texto alrededor del link para buscar palabras clave
                    posicion = html_content.find(link)
                    bloque_contexto = html_content[max(0, posicion-500):min(len(html_content), posicion+500)].lower()
                    
                    if "popocatépetl" in bloque_contexto or "popocatepetl" in bloque_contexto:
                        
                        if link_completo not in vistos_volcanes:
                            # Intentamos extraer una fecha o título dinámico del bloque si es posible, 
                            # si no, armamos el título limpio con la fecha de hoy.
                            hoy_str = datetime.now().strftime('%d/%m/%Y')
                            titulo_alerta = f"Monitoreo del volcán Popocatépetl - {hoy_str}"
                            
                            # Intentar buscar un h2 o h3 cercano en el bloque para heredar el título real
                            titulos_encontrados = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', html_content[max(0, posicion-600):posicion])
                            if titulos_encontrados:
                                titulo_alerta = re.sub(r'<[^>]+>', '', titulos_encontrados[-1]).strip()

                            mensaje = (
                                f"🌋 **ACTIVIDAD VOLCÁNICA (CENAPRED)**\n\n"
                                f"📢 **Reporte Actualizado:** {titulo_alerta}\n\n"
                                f"🌐 [Leer reporte completo en la web]({link_completo})"
                            )
                            
                            enviar_telegram(mensaje)
                            vistos_volcanes.add(link_completo)
                            print(f"Alerta enviada con éxito para el link: {link_completo}")
                            break # Detener para quedarse solo con el más reciente del tope
                else:
                    print("No se detectaron tarjetas activas del Popocatépetl en esta iteración.")
            else:
                print(f"CENAPRED respondió con código de error: {res.status_code}")
                
        except Exception as e:
            print(f"Error crítico en scraping adaptativo de volcanes: {e}")
            
        time.sleep(3600) # Sigue revisando cada hora de forma automática

@app.route('/')
def home():
    return " Centro de Monitoreo Multiamenaza (MX-GT) Activo y Corriendo"

if __name__ == "__main__":
    # Inicialización de hilos asíncronos en segundo plano
    threading.Thread(target=monitorear_sismos, daemon=True).start()
    threading.Thread(target=monitorear_huracanes, daemon=True).start()
    threading.Thread(target=monitorear_volcanes, daemon=True).start()
    
    # Puerto dinámico adaptable para servidores en la nube
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
