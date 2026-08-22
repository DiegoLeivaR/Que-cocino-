# -*- coding: utf-8 -*-
"""Servidor de la app: sirve los archivos y hace de intermediario con la IA.

Uso:  python servidor.py
Cortar con Ctrl+C.

Por que un servidor y no abrir el HTML directo:
  1. La API key se queda aca. El navegador nunca la ve, asi que nadie que
     abra la pagina te la puede robar.
  2. Los navegadores bloquean cargar archivos vecinos desde file://
"""

import http.server
import io
import json
import os
import socket
import socketserver
import threading
import time
import webbrowser

import ia
import plazavea

# Los servicios de hosting asignan el puerto por variable de entorno.
# En tu maquina no existe esa variable y usa 8765.
PUERTO = int(os.environ.get("PORT", 8765))
AQUI = os.path.dirname(os.path.abspath(__file__))
os.chdir(AQUI)


def _precios():
    with io.open("precios.json", encoding="utf-8") as f:
        return json.load(f)["productos"]


def catalogo():
    """Nombres de producto que tienen precio; la IA solo puede responder estos."""
    return sorted(_precios().keys())


def precios_mercado():
    """Precio por kilo estimado de mercado de barrio, por producto."""
    return {k: v["mercado"] for k, v in _precios().items()}


def ip_local():
    """IP de esta maquina en la red wifi, para entrar desde el celular."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()




# PIN de acceso. Vacio = sin candado (asi corre en tu casa).
# En un hosting publico se pone la variable ACCESO_PIN y sin ese PIN nadie
# puede usar la IA: es lo unico que separa tu cuota de todo internet.
PIN = os.environ.get("ACCESO_PIN", "").strip()

_intentos = {}  # ip -> [momentos de peticion], para frenar abusos


def _muy_seguido(ip, limite=30, ventana=600):
    """True si esa IP paso el limite de peticiones en los ultimos 10 minutos."""
    ahora = time.time()
    marcas = [t for t in _intentos.get(ip, []) if ahora - t < ventana]
    marcas.append(ahora)
    _intentos[ip] = marcas
    return len(marcas) > limite


class App(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        # Sin esto el navegador se queda con el index.html viejo y editas sin
        # ver ningun cambio. Es un servidor de desarrollo: cachear no aporta.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        http.server.SimpleHTTPRequestHandler.end_headers(self)

    def _responder(self, codigo, obj):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_POST(self):
        if not self.path.startswith("/api/"):
            return self.send_error(404)

        # /api/entrar solo dice si el PIN es correcto; no gasta cuota de IA
        if self.path == "/api/entrar":
            largo = int(self.headers.get("Content-Length", 0))
            try:
                pin = json.loads(self.rfile.read(largo).decode("utf-8")).get("pin", "")
            except Exception:
                pin = ""
            return self._responder(200, {"ok": (not PIN) or pin == PIN,
                                         "hace_falta": bool(PIN)})

        if PIN and self.headers.get("X-Pin", "") != PIN:
            return self._responder(401, {"error": "PIN incorrecto o vencido."})

        ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0]
        if _muy_seguido(ip):
            return self._responder(429, {
                "error": "Demasiadas peticiones seguidas. Espera unos minutos."})

        largo = int(self.headers.get("Content-Length", 0))
        try:
            datos = json.loads(self.rfile.read(largo).decode("utf-8"))
        except Exception:
            return self._responder(400, {"error": "JSON invalido"})

        try:
            if self.path == "/api/ver":
                print("  -> analizando foto...")
                r = ia.ver_ingredientes(
                    datos["imagen"], catalogo(), datos.get("mime", "image/jpeg")
                )
                print("     reconocido:", ", ".join(r["reconocidos"]) or "nada")

                # Lo que la IA vio pero el SISAP no cotiza: le buscamos precio
                # real en el super en vez de dejar que el modelo lo invente.
                extras = []
                for nombre in r["otros"][:6]:
                    mercado, sup = plazavea.precio_libre(nombre)
                    if mercado:
                        extras.append({"nombre": nombre, "mercado": mercado,
                                       "super": sup})
                if extras:
                    print("     precios extra:", ", ".join(
                        "%s S/%.2f" % (e["nombre"], e["mercado"]) for e in extras))
                r["extras"] = extras
                return self._responder(200, r)

            if self.path == "/api/recetas":
                print("  -> pensando recetas (%s, hasta S/%s)..."
                      % (datos.get("dificultad"), datos.get("presupuesto")))
                precios = precios_mercado()
                # los extras vienen de la foto (queso, pan...) con precio real
                for k, v in (datos.get("extras") or {}).items():
                    precios[k] = float(v)
                r = ia.sugerir_recetas(
                    datos.get("tengo", []), datos.get("dificultad", "media"),
                    datos.get("presupuesto", 30), precios,
                )
                print("     %s" % ", ".join(x["nombre"] for x in r))
                return self._responder(200, {"recetas": r})

            if self.path == "/api/explicar":
                print("  -> explicando %s..." % datos.get("receta"))
                txt = ia.explicar_receta(
                    datos["receta"], datos.get("tengo", []), datos.get("falta", []),
                    datos.get("presupuesto", "?"), datos.get("dificultad", "?"),
                )
                return self._responder(200, {"texto": txt})

            return self._responder(404, {"error": "ruta desconocida"})

        except Exception as e:
            print("  !! error:", e)
            return self._responder(500, {"error": str(e)})


socketserver.TCPServer.allow_reuse_address = True


class Servidor(socketserver.ThreadingTCPServer):
    daemon_threads = True


def refrescar_cada_dia():
    """Vuelve a bajar los precios una vez al dia.

    En tu maquina corres actualizar.py cuando quieres. En un hosting no hay
    nadie que lo haga, y unos precios de hace tres semanas son peores que no
    tener precios: se ven igual de confiables pero ya no lo son.
    """
    import actualizar
    while True:
        time.sleep(24 * 3600)
        try:
            r = actualizar.generar(hablar=False)
            print("  precios actualizados: %s (%d productos)"
                  % (r["fecha"], r["productos"]))
        except Exception as e:
            print("  no pude actualizar precios:", e)


if __name__ == "__main__":
    if not os.path.exists("precios.json"):
        raise SystemExit("Falta precios.json. Corre primero:  python actualizar.py")

    # Si ya hay un servidor viejo en el puerto, avisamos en vez de arrancar
    # otro al lado: los dos quedarian escuchando y el navegador hablaria con
    # el viejo, sirviendo codigo desactualizado sin ninguna senal de error.
    en_hosting = bool(os.environ.get("PORT"))

    _sonda = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _sonda.settimeout(1)
    _ocupado = (not en_hosting) and _sonda.connect_ex(("127.0.0.1", PUERTO)) == 0
    _sonda.close()
    if _ocupado:
        raise SystemExit(
            "Ya hay algo corriendo en el puerto %d.\n"
            "Es casi seguro otra ventana de este mismo servidor: cierrala con\n"
            "Ctrl+C y vuelve a intentar." % PUERTO)

    hay_key = os.path.exists("config.json")
    with Servidor(("0.0.0.0", PUERTO), App) as httpd:
        url = "http://127.0.0.1:%d/index.html" % PUERTO
        ip = ip_local()
        print("App corriendo en:", url)
        if ip:
            print("Desde tu celular  :  http://%s:%d/index.html" % (ip, PUERTO))
            print("  (mismo wifi. Mientras corre, cualquiera en tu red puede")
            print("   abrirla y gastar tu cuota de IA. Cortala cuando termines.)")
        print("Acceso con PIN:" , "SI" if PIN else "no (abierto a tu red)")
        if hay_key:
            print("IA conectada (config.json encontrado)")
        else:
            print("SIN IA: falta config.json. La app funciona igual,")
            print("        pero la foto no se va a analizar.")
        print("Ctrl+C para cortar.\n")
        if en_hosting:
            threading.Thread(target=refrescar_cada_dia, daemon=True).start()
        else:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nCerrado.")
