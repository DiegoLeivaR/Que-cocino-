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




class App(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

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
        if hay_key:
            print("IA conectada (config.json encontrado)")
        else:
            print("SIN IA: falta config.json. La app funciona igual,")
            print("        pero la foto no se va a analizar.")
        print("Ctrl+C para cortar.\n")
        if not en_hosting:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nCerrado.")
