"""
Cliente para el SISAP de MIDAGRI (precios mayoristas de Lima).

Descubierto por ingenieria inversa del portal publico:
  POST http://sistemas.midagri.gob.pe/sisap/portal2/mayorista/resumenes/filtrar

Notas importantes:
  - El servidor NO soporta HTTPS moderno (TLS viejo) -> hay que usar http://
  - La pagina declara UTF-8 pero en realidad devuelve latin-1
  - La respuesta es una tabla HTML, no JSON
"""

import re
import html
import json
import urllib.parse
import urllib.request
from datetime import date, timedelta

URL = "http://sistemas.midagri.gob.pe/sisap/portal2/mayorista/resumenes/filtrar"

MERCADOS = {
    "15011501": "Gran Mercado Mayorista de Lima (Santa Anita)",
    "15011503": "Mercado Modelo de Frutas",
    "15013405": "Mercado Cooperativo Platanos",
    "15013704": "Mercado Productores Santa Anita",
    "15011506": "Mercado Mayorista Cereales, Legumbres y Oleaginosas",
    "15011502": "Mercado Mayorista Nro 2 - Frutas",
    "15010106": "Mercado Mayorista de Aves Vivas",
}

# codigo SISAP -> nombre. Solo la canasta que nos interesa.
PRODUCTOS = {
    # verduras y tuberculos
    "0104": "Papa",        "1014": "Papa seca",   "0101": "Camote",
    "0105": "Yuca",        "0102": "Olluco",      "0107": "Mashua",
    "0106": "Maca",        "0212": "Cebolla",     "0228": "Tomate",
    "0230": "Zanahoria",   "0231": "Zapallo",     "0209": "Beterraga",
    "0217": "Espinaca",    "0220": "Lechuga",     "0215": "Culantro",
    "0207": "Apio",        "0229": "Vainita",     "0403": "Choclo",
    "0206": "Alcachofa",   "0216": "Esparrago",   "0224": "Pimiento fresco",
    "0218": "Hortalizas chinas",
    "0202": "Aji fresco",  "0203": "Aji seco",    "0204": "Ajo",
    "0630": "Pepino",
    # frutas
    "0611": "Limon",       "0629": "Platano",     "0617": "Manzana",
    "0622": "Naranja",     "0614": "Mandarina",   "0626": "Palta",
    "0627": "Papaya",      "0628": "Pina",        "0637": "Uva",
    "0633": "Sandia",      "0619": "Melon",       "0615": "Mango",
    "0607": "Fresa",       "0618": "Maracuya",    "0608": "Granadilla",
    "0603": "Chirimoya",   "0609": "Guanabana",   "0604": "Ciruela",
    "0620": "Melocoton",   "0621": "Membrillo",   "0636": "Tuna",
    "0640": "Bayas",       "0641": "Cerezas",
    # granos y legumbres
    "0301": "Arveja grano verde",   "0302": "Frijol grano verde",
    "0303": "Haba grano verde",     "0305": "Pallar grano verde",
    "0501": "Frijol grano seco",    "0502": "Garbanzo grano seco",
    "0504": "Lenteja grano seco",   "0506": "Pallar grano seco",
    "0306": "Tarhui",      "0405": "Quinua",      "0404": "Maiz seco",
    # abarrotes
    "0401": "Arroz",       "1010": "Fideos",      "1011": "Harina",
    "1001": "Aceite",      "1005": "Azucar",      "1105": "Huevos",
    "1104": "Leche",       "0902": "Cafe",        "1018": "Aceituna botija",
    # proteina
    "1301": "Pollo",
}

# En que mercado se consulta cada producto.
# El pollo vive en el mercado de aves vivas; los abarrotes en Productores Santa Anita.
_ABARROTES = ("0401", "1105", "1001", "1005", "1010", "1104", "0501",
              "0504", "0502", "0506", "1011", "1014", "0404", "0405",
              "0902", "1018", "0306")
_FRUTAS = ("0603", "0604", "0607", "0608", "0609", "0614", "0615", "0617",
           "0618", "0619", "0620", "0621", "0622", "0626", "0627", "0628",
           "0633", "0636", "0637", "0640", "0641", "0629")
MERCADO_DE = {"1301": "15010106"}
MERCADO_DE.update({c: "15011502" for c in _FRUTAS})  # Mayorista Nro 2 - Frutas
MERCADO_DE.update({c: "15013704" for c in _ABARROTES})
MERCADO_DEFECTO = "15011501"


def _fetch(mercado, codigos, fecha):
    """Hace un POST al SISAP y devuelve el HTML crudo (ya decodificado)."""
    campos = [
        ("periodicidad", "dia"),
        ("fecha", fecha),
        ("mercado", mercado),
        ("variables[]", "precio_prom"),
        ("__ajax_carga_final", "consulta"),
    ]
    campos += [("productos[]", c) for c in codigos]

    datos = urllib.parse.urlencode(campos).encode("ascii")
    req = urllib.request.Request(
        URL,
        data=datos,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "http://sistemas.midagri.gob.pe/sisap/portal2/mayorista/",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("latin-1")


def _parsear(html_txt):
    """Convierte la tabla HTML del SISAP en [{producto, variedad, precio}, ...].

    La primera fila de cada producto trae 3 celdas (con rowspan) y las
    siguientes solo 2, porque el nombre del producto esta fusionado.
    """
    filas = []
    producto_actual = None

    for tr in re.findall(r"<tr class=contenido>(.*?)</tr>", html_txt, re.S):
        celdas = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        ]
        if len(celdas) == 3:
            producto_actual, variedad, precio = celdas
        elif len(celdas) == 2 and producto_actual:
            variedad, precio = celdas
        else:
            continue

        try:
            valor = float(precio.replace(",", ""))
        except ValueError:
            continue

        filas.append(
            {"producto": producto_actual, "variedad": variedad, "precio_kg": valor}
        )

    return filas


def precios(fecha=None, codigos=None):
    """Devuelve los precios mayoristas de la fecha dada (dd/mm/aaaa).

    Si no hay datos ese dia (feriado/domingo) retrocede hasta 5 dias.
    """
    codigos = codigos or list(PRODUCTOS.keys())

    # agrupar por mercado para hacer una sola llamada por mercado
    por_mercado = {}
    for c in codigos:
        por_mercado.setdefault(MERCADO_DE.get(c, MERCADO_DEFECTO), []).append(c)

    dia = (
        date.today()
        if fecha is None
        else date(*[int(x) for x in reversed(fecha.split("/"))])
    )

    for intento in range(6):
        f = (dia - timedelta(days=intento)).strftime("%d/%m/%Y")
        resultado = []
        for mercado, cods in por_mercado.items():
            try:
                resultado += _parsear(_fetch(mercado, cods, f))
            except Exception as e:
                print("  aviso: fallo mercado %s (%s)" % (mercado, e))
        if resultado:
            return {"fecha": f, "items": resultado}

    return {"fecha": None, "items": []}


if __name__ == "__main__":
    d = precios()
    print("Precios mayoristas del", d["fecha"], "-", len(d["items"]), "variedades\n")
    for it in d["items"]:
        print("  %-22s %-28s S/ %6.2f" % (it["producto"], it["variedad"], it["precio_kg"]))
    with open("precios.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print("\nGuardado en precios.json")
