# -*- coding: utf-8 -*-
"""Precios de supermercado (Plaza Vea) via su API publica de catalogo.

Plaza Vea corre sobre VTEX, que expone el catalogo sin autenticacion:
  GET /api/catalog_system/pub/products/search/?ft=<texto>

Para que sirve: el SISAP da precios MAYORISTAS, que no son lo que pagas.
Con el super podemos estimar el precio de mercado, usando la regla observada
de que el supermercado esta ~20% por encima del mercado de barrio:

    mercado ~= precio_lista_super / 1.20

Usamos ListPrice (precio de lista) y no Price, porque Price incluye ofertas
y las ofertas no representan el precio normal.
"""

import json
import re
import statistics
import time
import urllib.parse
import urllib.request

URL = ("https://www.plazavea.com.pe/api/catalog_system/pub/products/search/"
       "?ft=%s&_from=0&_to=19")

# Cuanto mas caro esta el super respecto al mercado de barrio.
FACTOR_SUPER = 1.20

# Nombre en nuestro catalogo -> que buscar en el super
BUSQUEDA = {
    "Papa": "papa blanca x kg",
    "Cebolla": "cebolla roja x kg",
    "Tomate": "tomate italiano x kg",
    "Zanahoria": "zanahoria x kg",
    "Limon": "limon sutil",
    "Aji Fresco": "aji amarillo",
    "Ajo": "ajo x kg",
    "Camote": "camote x kg",
    "Yuca": "yuca x kg",
    "Zapallo": "zapallo macre x kg",
    "Espinaca": "espinaca",
    "Lechuga": "lechuga x kg",
    "Culantro": "culantro",
    "Apio": "apio x kg",
    "Beterraga": "beterraga x kg",
    "Vainita": "vainita",
    "Choclo": "choclo x kg",
    "Arveja Grano Verde": "arveja verde",
    "Frijol Grano Verde": "frijol verde",
    "Haba Grano Verde": "haba verde",
    "Arroz": "arroz extra bolsa 5kg",
    "Frijol Grano Seco": "frijol canario bolsa 500g",
    "Lenteja Grano Seco": "lenteja bolsa 500g",
    "Garbanzo Grano Seco": "garbanzo bolsa 500g",
    "Huevos": "huevo pardo",
    "Leche": "leche evaporada",
    "Aceite": "aceite vegetal botella 900ml",
    "Azucar Comercial": "azucar rubia bolsa 1kg",
    "Fideos": "fideos spaghetti bolsa 500g",
    "Pollo": "pollo entero fresco x kg",
    "Platano": "platano x kg",
    "Manzana": "manzana x kg",
    "Naranja": "naranja x kg",
    "Mandarina": "mandarina x kg",
    "Palta": "palta fuerte x kg",
    "Papaya": "papaya x kg",
    "Pina": "pina x kg",
    "Uva": "uva x kg",
    "Sandia": "sandia x kg",
    "Melon": "melon x kg",
    "Mango": "mango x kg",
    "Fresa": "fresa x kg",
    "Maracuya": "maracuya x kg",
    "Granadilla": "granadilla x kg",
    "Chirimoya": "chirimoya x kg",
    "Guanabana": "guanabana x kg",
    "Ciruela": "ciruela x kg",
    "Melocoton": "melocoton x kg",
    "Membrillo": "membrillo x kg",
    "Tuna": "tuna x kg",
    "Bayas": "arandanos x kg",
    "Cerezas": "cereza x kg",
    "Aji Seco": "aji panca",
    "Maiz Seco": "maiz mote bolsa",
    "Quinua": "quinua bolsa 500g",
    "Alcachofa": "alcachofa x kg",
    "Esparrago": "esparrago x kg",
    "Pimiento Fresco": "pimiento x kg",
    "Pepino": "pepino x kg",
    "Olluco": "olluco x kg",
    "Papa Seca": "papa seca bolsa",
    "Cafe": "cafe molido bolsa",
    "Harina": "harina sin preparar bolsa 1kg",
    "Pallar Grano Seco": "pallar bolsa 500g",
    "Tarhui": "tarwi bolsa",
}

# Maximo creible por kilo. Si un candidato lo pasa, es que la busqueda trajo
# otra cosa (buscando "vainita" salieron antipulgas para perros a S/145).
TECHO = {
    "Papa": 12, "Cebolla": 12, "Tomate": 14, "Zanahoria": 12, "Limon": 16,
    "Aji Fresco": 25, "Ajo": 35, "Camote": 12, "Yuca": 14, "Zapallo": 12,
    "Espinaca": 18, "Lechuga": 15, "Culantro": 30, "Apio": 15, "Beterraga": 12,
    "Vainita": 18, "Choclo": 14, "Arveja Grano Verde": 18,
    "Frijol Grano Verde": 18, "Haba Grano Verde": 16,
    "Arroz": 12, "Frijol Grano Seco": 20, "Lenteja Grano Seco": 20,
    "Garbanzo Grano Seco": 22, "Huevos": 16, "Leche": 16, "Aceite": 22,
    "Azucar Comercial": 10, "Fideos": 16, "Pollo": 22, "Manzana": 16,
    # frutas frescas: el kilo casi nunca pasa de 12
    "Platano": 9, "Naranja": 9, "Mandarina": 10, "Papaya": 9, "Sandia": 7,
    "Melon": 9, "Pina": 9, "Palta": 20, "Uva": 20, "Mango": 12, "Fresa": 20,
    "Maracuya": 14, "Granadilla": 20, "Chirimoya": 20, "Guanabana": 20,
    "Ciruela": 16, "Melocoton": 16, "Membrillo": 14, "Tuna": 14,
    "Bayas": 45, "Cerezas": 60,
    "Aji Seco": 40, "Maiz Seco": 14, "Quinua": 22, "Alcachofa": 16,
    "Esparrago": 24, "Pimiento Fresco": 16, "Pepino": 12, "Olluco": 12,
    "Papa Seca": 26, "Cafe": 90, "Harina": 10, "Pallar Grano Seco": 22,
    "Tarhui": 22, "Hortalizas Chinas": 16, "Aceituna Botija": 40,
    "Pallar Grano Verde": 18,
}

# Si un producto no esta arriba, este es el limite: casi ningun alimento
# crudo cuesta mas de S/20 el kilo, y lo que pasa de ahi suele ser un
# resultado mal emparejado de la busqueda.
TECHO_DEFECTO = 20

# Palabras que delatan que NO es el ingrediente crudo que buscamos
BASURA = (
    "alimento para", "mascota", "gato", "perro", "jugo", "nectar", "congelad",
    "bastones", "canasta", "deco", "snack", "galleta", "chips", "pure",
    "conserva", "enlatad", "shampoo", "jabon", "papel", "peluche", "juguete",
    "salsa", "crema de", "sopa instant", "saborizante", "gaseosa", "cerveza",
)


def _buscar(texto):
    req = urllib.request.Request(
        URL % urllib.parse.quote(texto),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _sin_tildes(t):
    """'Azúcar' -> 'azucar'. Sin esto el filtro no matchea nada con tildes."""
    tabla = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return t.translate(tabla).lower()


def _kg_del_nombre(nombre):
    """Cuantos kg/litros trae el producto, para normalizar a precio por kilo."""
    n = _sin_tildes(nombre)

    # "Paquete 6un" / "Pack x4" multiplica el contenido; sin esto un six-pack
    # de leche de 390g se leia como 390g y el precio por kilo salia 6x inflado
    veces = 1
    m = re.search(r"(?:paquete|pack|x)\s*(\d{1,2})\s*(?:un|u|und|unid)\b", n)
    if m:
        veces = int(m.group(1))

    for patron, factor in ((r"(\d+(?:[.,]\d+)?)\s*(?:kg|kilo)", 1.0),
                           (r"(\d+(?:[.,]\d+)?)\s*(?:g|gr|ml)\b", 0.001),
                           (r"(\d+(?:[.,]\d+)?)\s*(?:lt|l)\b", 1.0)):
        m = re.search(patron, n)
        if m:
            return float(m.group(1).replace(",", ".")) * factor * veces
    return 1.0  # "x kg" y similares ya vienen por kilo


def precio_super(producto, consulta=None, techo=None):
    """Precio por kilo en el super, o None si no encuentra nada creible.

    `techo` es el maximo por kilo que tiene sentido para ese producto. Cuando
    la busqueda no encuentra nada, Plaza Vea devuelve resultados sin relacion
    (buscando "vainita" salian antipulgas para perros), y el techo los corta.
    """
    consulta = consulta or BUSQUEDA.get(producto, producto)
    clave = _sin_tildes(re.split(r"\s", consulta)[0])  # 'papa', 'azucar', ...

    crudos = None
    for intento in range(2):   # el sitio corta conexiones si le pides seguido
        try:
            crudos = _buscar(consulta)
            break
        except Exception:
            if intento == 0:
                time.sleep(1.5)
    if crudos is None:
        return None

    candidatos = []
    for p in crudos:
        nombre = p.get("productName", "")
        n = _sin_tildes(nombre)
        if clave not in n or any(b in n for b in BASURA):
            continue
        try:
            oferta = p["items"][0]["sellers"][0]["commertialOffer"]
        except (KeyError, IndexError):
            continue
        # ListPrice = precio normal; Price puede traer descuento del dia
        lista = oferta.get("ListPrice") or oferta.get("Price") or 0
        if not lista or not oferta.get("IsAvailable", True):
            continue
        por_kilo = lista / _kg_del_nombre(nombre)
        if 0.3 < por_kilo < (techo or 200):
            candidatos.append(por_kilo)

    # el techo ya descarta lo que no corresponde, asi que un solo
    # resultado creible alcanza (hay productos con un unico SKU)
    if not candidatos:
        return None
    return round(statistics.median(candidatos), 2)


def precio_libre(texto, techo=90):
    """Precio por kilo de un alimento cualquiera, buscandolo en vivo.

    Para lo que la IA reconoce en la foto pero no esta en el catalogo del
    SISAP: queso, pan, mantequilla, yogurt... En vez de que el modelo invente
    un precio, se lo preguntamos al super.

    Devuelve (precio_mercado, precio_super) o (None, None).
    """
    palabras = [p for p in _sin_tildes(texto).split() if len(p) > 2]
    if not palabras:
        return None, None
    clave = palabras[0]

    try:
        crudos = _buscar(texto)
    except Exception:
        return None, None

    candidatos = []
    for p in crudos:
        nombre = p.get("productName", "")
        n = _sin_tildes(nombre)
        if clave not in n or any(b in n for b in BASURA):
            continue
        try:
            oferta = p["items"][0]["sellers"][0]["commertialOffer"]
        except (KeyError, IndexError):
            continue
        lista = oferta.get("ListPrice") or oferta.get("Price") or 0
        if not lista or not oferta.get("IsAvailable", True):
            continue
        por_kilo = lista / _kg_del_nombre(nombre)
        if 0.5 < por_kilo < techo:
            candidatos.append(por_kilo)

    if not candidatos:
        return None, None
    sup = round(statistics.median(candidatos), 2)
    return round(sup / FACTOR_SUPER, 2), sup


def todos(productos, pausa=0.8):
    """Precio de super para varios productos. Con pausa para no abusar del sitio."""
    salida = {}
    for i, p in enumerate(productos):
        v = precio_super(p, techo=TECHO.get(p, TECHO_DEFECTO))
        if v:
            salida[p] = v
        print("   %-22s %s" % (p, ("S/ %.2f" % v) if v else "sin dato"))
        if i < len(productos) - 1:
            time.sleep(pausa)
    return salida


if __name__ == "__main__":
    print("Precios de Plaza Vea (lista, por kilo):\n")
    r = todos(sorted(BUSQUEDA.keys()))
    print("\nEncontrados %d de %d" % (len(r), len(BUSQUEDA)))
