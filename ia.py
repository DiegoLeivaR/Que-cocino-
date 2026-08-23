# -*- coding: utf-8 -*-
"""Conexion con el modelo de IA (vision + texto).

Soporta Gemini (recomendado: tiene tier gratis con vision) y OpenAI.
La API key se lee de config.json y NUNCA sale hacia el navegador.
"""

import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "config.json")


def _cfg():
    """Lee la config. Primero busca variables de entorno, luego config.json.

    Las variables de entorno ganan porque es lo que se usa al desplegar en un
    servidor de verdad, donde no quieres archivos con claves adentro.
    """
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if env_key:
        gemini = bool(os.environ.get("GEMINI_API_KEY"))
        return {
            "proveedor": "gemini" if gemini else "openai",
            "api_key": env_key,
            "modelo": os.environ.get(
                "IA_MODELO", "gemini-3.6-flash" if gemini else "gpt-4.1-mini"
            ),
            "modelo_rapido": os.environ.get(
                "IA_MODELO_RAPIDO",
                "gemini-3.5-flash-lite" if gemini else "gpt-4.1-mini"
            ),
        }

    if not os.path.exists(CONFIG):
        raise RuntimeError(
            "Falta config.json. Corre:  python configurar.py"
        )
    with io.open(CONFIG, encoding="utf-8") as f:
        c = json.load(f)
    if not c.get("api_key") or "PEGA" in c["api_key"]:
        raise RuntimeError("Falta poner tu api_key. Corre:  python configurar.py")
    return c


def _post(url, cuerpo, headers, intentos=3):
    """POST con reintentos.

    En el tier gratis es normal chocar con 429 (pasaste la cuota del minuto)
    y 503 (el modelo esta saturado). Los dos se arreglan solos esperando un
    poco, asi que reintentamos antes de darnos por vencidos.
    """
    datos = json.dumps(cuerpo).encode("utf-8")
    for intento in range(intentos):
        req = urllib.request.Request(url, data=datos, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:600]
            recuperable = e.code in (429, 500, 503)
            if recuperable and intento < intentos - 1:
                if e.code == 429:
                    # La cuota gratis es POR MINUTO, asi que esperar 2 segundos
                    # no sirve de nada. La API dice cuanto esperar; le hacemos
                    # caso, y si no lo dice asumimos medio minuto.
                    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', detalle)
                    espera = min(float(m.group(1)) + 1, 65) if m else 30
                else:
                    espera = 2 ** intento
                print("  aviso: error %s, espero %.0fs y reintento"
                      % (e.code, espera))
                time.sleep(espera)
                continue
            if e.code == 429:
                raise RuntimeError(
                    "Se agotó la cuota del minuto. Espera unos segundos "
                    "y dale de nuevo.")
            if e.code == 503:
                raise RuntimeError(
                    "El modelo está con mucha demanda ahorita. "
                    "Dale de nuevo en un ratito.")
            # Al usuario no le sirve el volcado crudo de la API
            print("  !! HTTP %s: %s" % (e.code, detalle))
            raise RuntimeError("Algo falló del lado del modelo (error %s). "
                               "Vuelve a intentar." % e.code)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # "The read operation timed out" era esto, y salia crudo en pantalla
            if intento < intentos - 1:
                time.sleep(2 ** intento)
                continue
            print("  !! red: %r" % e)
            raise RuntimeError("El modelo se demoró demasiado en contestar. "
                               "Vuelve a intentar.")


def modelos_disponibles():
    """Lista los modelos que tu API key puede usar (solo Gemini).

    Sirve porque los nombres de modelo cambian seguido: si el configurado
    ya no existe, aca ves cual si.
    """
    c = _cfg()
    if c.get("proveedor", "gemini") != "gemini":
        return []
    url = ("https://generativelanguage.googleapis.com/v1beta/models?key=%s"
           % c["api_key"])
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    return [
        m["name"].split("/")[-1]
        for m in d.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]


def _version(nombre):
    """Saca el numero de version del nombre: 'gemini-3.6-flash' -> 3.6

    Sirve para ordenar y quedarnos siempre con el mas nuevo.
    """
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", nombre)
    return float(m.group(1)) if m else 0.0


_cache_modelo = {}


def _elegir_modelo(c):
    """Devuelve el modelo a usar, sin pedir nada por red.

    Antes preguntaba la lista de modelos ANTES de cada llamada, lo que sumaba
    un viaje de ida y vuelta a cada foto. Ahora se intenta directo y solo si
    falla se busca reemplazo (ver _buscar_reemplazo).
    """
    pedido = c.get("modelo") or "gemini-3.6-flash"
    return _cache_modelo.get(pedido, pedido)


def _buscar_reemplazo(pedido):
    """Se llama solo cuando el modelo configurado fallo: busca el flash mas nuevo."""
    disponibles = modelos_disponibles()
    # Flash = barato y rapido. Fuera los de imagen, preview y experimentales.
    flash = [m for m in disponibles
             if "flash" in m and not any(
                 x in m for x in ("image", "lite", "preview", "exp",
                                  "thinking", "tts", "omni"))]
    # version mas alta primero; sin esto agarraba uno viejo y deprecado
    flash.sort(key=_version, reverse=True)
    if not flash:
        raise RuntimeError("Tu key no tiene ningun modelo flash disponible.")
    return flash[0]


def _llamar(prompt, imagen_b64=None, mime="image/jpeg", rapido=False,
            json_estricto=False):
    """Manda prompt (y opcionalmente una imagen) al modelo. Devuelve texto.

    `rapido=True` usa el modelo veloz y apaga el "pensamiento" del modelo.
    Es la diferencia entre 5 y 50 segundos: los modelos nuevos razonan antes
    de responder, lo cual sirve para explicar un plato pero es un desperdicio
    para armar una lista.
    """
    c = _cfg()
    proveedor = c.get("proveedor", "gemini")
    modelo = _elegir_modelo(c)
    if rapido and proveedor == "gemini":
        modelo = c.get("modelo_rapido") or "gemini-3.5-flash"

    if proveedor == "gemini":
        partes = [{"text": prompt}]
        if imagen_b64:
            partes.append({"inline_data": {"mime_type": mime, "data": imagen_b64}})

        def pedir(m, sin_pensar=rapido, intentos=3):
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "%s:generateContent?key=%s" % (m, c["api_key"]))
            cuerpo = {"contents": [{"parts": partes}]}
            cfg = {}
            if sin_pensar:
                cfg["thinkingConfig"] = {"thinkingBudget": 0}
            if json_estricto:
                # El modelo devuelve JSON valido garantizado. Sin esto mandaba
                # texto con comas de mas y el parseo reventaba a mitad de uso.
                cfg["responseMimeType"] = "application/json"
            if cfg:
                cuerpo["generationConfig"] = cfg
            try:
                return _post(url, cuerpo, {"Content-Type": "application/json"},
                             intentos=intentos)
            except RuntimeError as e:
                # hay modelos que solo funcionan pensando y rechazan apagarlo
                if cfg and "400" in str(e):
                    return _post(url, {"contents": [{"parts": partes}]},
                                 {"Content-Type": "application/json"},
                                 intentos=intentos)
                raise

        # Con el modelo bueno no insistimos: si no hay cuota, mas vale caer
        # rapido al de respaldo que hacer esperar un minuto para nada.
        try:
            d = pedir(modelo, intentos=(1 if not rapido else 3))
        except RuntimeError as e:
            texto = str(e)
            if "404" in texto:
                # Cuando un modelo se jubila, la API suele decir cual usar:
                # "Please update your code to use models/gemini-3.6-flash".
                # Le hacemos caso; si no, buscamos el flash mas nuevo.
                sug = re.search(r"use models/([A-Za-z0-9.\-]+)", texto)
                nuevo = sug.group(1) if sug else _buscar_reemplazo(modelo)
                print("  aviso: '%s' no sirve -> reintento con '%s'" % (modelo, nuevo))
                d = pedir(nuevo)
                _cache_modelo[modelo] = nuevo   # el resto de la sesion va directo
            elif "cuota" in texto.lower() and not rapido:
                # El modelo bueno se quedo sin cuota del minuto. Antes esto
                # dejaba al usuario sin nada despues de esperar un minuto.
                # Mejor una explicacion algo menos pulida que ninguna: el
                # modelo rapido tiene mucho mas margen en el tier gratis.
                respaldo = c.get("modelo_rapido") or "gemini-3.5-flash-lite"
                print("  aviso: '%s' sin cuota -> lo resuelvo con '%s'"
                      % (modelo, respaldo))
                d = pedir(respaldo, sin_pensar=True)
            else:
                raise

        try:
            return d["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError("Respuesta inesperada: %s" % json.dumps(d)[:300])

    # OpenAI
    contenido = [{"type": "text", "text": prompt}]
    if imagen_b64:
        contenido.append({
            "type": "image_url",
            "image_url": {"url": "data:%s;base64,%s" % (mime, imagen_b64)},
        })
    d = _post(
        "https://api.openai.com/v1/chat/completions",
        {"model": modelo, "messages": [{"role": "user", "content": contenido}]},
        {"Content-Type": "application/json",
         "Authorization": "Bearer " + c["api_key"]},
    )
    return d["choices"][0]["message"]["content"]


def _json_del_texto(txt):
    """Saca el JSON de la respuesta, aunque venga sucio.

    Los modelos a veces lo envuelven en ```json, y a veces dejan una coma
    colgando antes de cerrar. Un usuario no tiene por que ver un error de
    parseo por eso.
    """
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    txt = txt.replace("“", '"').replace("”", '"')
    ini = min([i for i in (txt.find("["), txt.find("{")) if i >= 0] or [0])
    crudo = txt[ini:]

    try:
        return json.loads(crudo)
    except json.JSONDecodeError:
        pass

    # coma colgando antes de cerrar
    try:
        return json.loads(re.sub(r",\s*(?=[}\]])", "", crudo))
    except json.JSONDecodeError:
        pass

    # Respuesta cortada a la mitad (el modelo llego a su limite de tokens).
    # Rescatamos los objetos que si vinieron completos en vez de perder todo.
    if crudo.lstrip().startswith("["):
        objetos, hondo, arranque = [], 0, None
        for i, ch in enumerate(crudo):
            if ch == "{":
                if hondo == 0:
                    arranque = i
                hondo += 1
            elif ch == "}":
                hondo -= 1
                if hondo == 0 and arranque is not None:
                    try:
                        objetos.append(json.loads(crudo[arranque:i + 1]))
                    except json.JSONDecodeError:
                        pass
                    arranque = None
        if objetos:
            print("  aviso: respuesta cortada, rescate %d de los platos"
                  % len(objetos))
            return objetos

    raise RuntimeError("El modelo devolvió algo que no pude leer. "
                       "Vuelve a intentar.")


def ver_ingredientes(imagen_b64, catalogo, mime="image/jpeg"):
    """Analiza la foto y devuelve que ingredientes reconocio.

    `catalogo` es la lista de productos que SI tienen precio. Obligamos al
    modelo a responder solo con esos nombres para que todo mapee a un precio.
    """
    prompt = (
        "Eres un asistente de cocina peruano con muy buen ojo. Esta foto es de "
        "una refrigeradora, una despensa, una mesa o una bolsa de mercado.\n\n"
        "Tu trabajo es hacer un INVENTARIO COMPLETO de todo alimento visible.\n\n"
        "COMO MIRAR (hazlo en este orden, sin saltarte nada):\n"
        "1. Recorre la imagen por zonas: cada repisa de arriba a abajo, los "
        "cajones, la puerta, y lo que este al fondo.\n"
        "2. Cuenta CADA alimento, incluso si esta parcialmente tapado, dentro "
        "de una bolsa, en un taper, en una malla o asomando detras de otra cosa.\n"
        "3. Un empaque cuenta: una bolsa de granos blancos es arroz, un cartón "
        "de huevos son huevos, una botella de aceite es aceite.\n"
        "4. Recien al final decide como llamar a cada cosa.\n\n"
        "SE GENEROSO, no timido. Si algo es muy probablemente cebolla, ponlo "
        "como cebolla. Es mejor marcar de mas (el usuario lo desmarca con un "
        "toque) que dejar la mitad de su refri sin detectar. Una foto normal de "
        "refrigeradora tiene entre 8 y 20 alimentos: si encontraste menos de 6, "
        "vuelve a mirar antes de responder.\n\n"
        "COMO NOMBRARLOS. En 'reconocidos' usa nombres EXACTOS de esta lista:\n"
        + ", ".join(catalogo) + "\n\n"
        "Empareja por lo que es, no por como se ve escrito: papa amarilla o "
        "huayro -> 'Papa'. Cebolla roja o china -> 'Cebolla'. Aji amarillo o "
        "rocoto -> 'Aji fresco'. Pechuga o pollo entero -> 'Pollo'.\n\n"
        "Todo alimento que NO encaje en esa lista va en 'otros' con su nombre "
        "comun en Peru (queso fresco, pan, mantequilla, yogurt, atun, sillao, "
        "gaseosa...). No dejes nada afuera: lo de 'otros' tambien nos sirve.\n\n"
        "Responde SOLO con JSON, sin texto alrededor:\n"
        '{"reconocidos": ["Papa", "Cebolla", "Huevos"], '
        '"otros": ["queso fresco", "pan de molde"], '
        '"comentario": "una frase corta y calida de lo que ves"}'
    )
    # sin rapido: el reconocimiento visual mejora bastante dejando que el
    # modelo razone antes de responder
    d = _json_del_texto(_llamar(prompt, imagen_b64, mime))
    validos = set(catalogo)
    return {
        "reconocidos": [x for x in d.get("reconocidos", []) if x in validos],
        "otros": d.get("otros", [])[:8],
        "comentario": d.get("comentario", ""),
    }


DIFICULTADES = {
    "facil": "facil: olla y sarten, hasta 30 min, tecnicas basicas",
    "media": "intermedia: aderezo bien hecho, licuadora, 30-50 min",
    "complicado": "elaborada: varias etapas o coccion larga, 50-90 min",
}


def sugerir_recetas(tengo, dificultad, presupuesto, precios, n=4, evitar=None):
    """Pide n recetas peruanas al modelo, ajustadas a lo que hay y al bolsillo.

    Le pasamos los precios reales para que respete el presupuesto, pero el
    costo final lo calcula la web con nuestros datos: el modelo propone, los
    precios del SISAP/Plaza Vea mandan.

    `evitar` son platos que ya se le mostraron al usuario. Cuando pide "otras",
    lo que quiere es variedad, no la misma lista de nuevo.
    """
    catalogo = sorted(precios.keys())
    lista_precios = "\n".join(
        "  %s: S/ %.2f por kg" % (k, precios[k]) for k in catalogo
    )
    tiene = ", ".join(tengo) if tengo else "nada en particular"
    evitar = [str(x) for x in (evitar or [])][-24:]

    prompt = (
        "Eres un cocinero peruano de casa, de esos que resuelven rico y barato.\n\n"
        "Propone %d platos PERUANOS caseros para 4 porciones.\n\n"
        "Lo que la persona ya tiene: %s\n"
        "Dificultad pedida: %s\n"
        "Puede gastar como maximo: S/ %s en lo que le falte comprar\n\n"
        "Precios reales por kilo (usalos para no pasarte del presupuesto):\n%s\n\n"
        "REGLAS:\n"
        "1. En 'ing' usa SOLO nombres EXACTOS de esa lista de precios, con la "
        "cantidad en KILOS (numero decimal) para 4 porciones.\n"
        "2. Prioriza platos que aprovechen lo que ya tiene.\n"
        "3. Cocina de casa: olla, sarten, horno comun. NADA de pachamanca, "
        "parrilla, horno de barro, ni cosas que pidan equipo especial o "
        "ingredientes raros o caros.\n"
        "4. Platos reales y comunes en Peru, economicos y del dia a dia.\n"
        "5. Si el plato necesita algo que no esta en la lista de precios "
        "(carne de res, sillao, queso, especias), ponlo en 'extra' como texto.\n"
        "6. Varia: no repitas la misma base en los %d platos.\n"
        "%s\n"
        "Responde SOLO con este JSON, sin texto alrededor:\n"
        '[{"nombre":"Arroz con Pollo","min":45,'
        '"ing":{"Pollo":0.8,"Arroz":0.4,"Culantro":0.1},'
        '"extra":["comino"],'
        '"pasos":"Una o dos frases de como se hace."}]'
        % (n, tiene, DIFICULTADES.get(dificultad, dificultad),
           presupuesto, lista_precios, n,
           ("7. YA LE PROPUSISTE ESTOS, no los repitas ni les cambies el "
            "nombre para colarlos: %s\n   Dale platos claramente distintos.\n"
            % ", ".join(evitar)) if evitar else "")
    )

    crudo = _json_del_texto(_llamar(prompt, rapido=True, json_estricto=True))
    if isinstance(crudo, dict):
        crudo = crudo.get("recetas") or crudo.get("platos") or [crudo]

    validos, salida = set(catalogo), []
    for r in crudo[:n]:
        # nos quedamos solo con ingredientes que sepamos costear
        ing = {k: float(v) for k, v in (r.get("ing") or {}).items()
               if k in validos and isinstance(v, (int, float)) and 0 < v < 5}
        if not ing:
            continue
        salida.append({
            "nombre": str(r.get("nombre", "Plato"))[:60],
            "min": int(r.get("min") or 30),
            "dif": dificultad,
            "ing": ing,
            "extra": [str(x)[:40] for x in (r.get("extra") or [])][:6],
            "pasos": str(r.get("pasos", ""))[:400],
        })
    return salida


def explicar_receta(receta, tengo, falta, presupuesto, dificultad):
    """Genera la explicacion paso a paso de la receta elegida."""
    lista_falta = ", ".join(
        "%s (%dg, S/%.2f)" % (f["ing"], f["kg"] * 1000, f["costo"]) for f in falta
    ) or "nada, tienes todo"

    prompt = (
        "Eres un cocinero peruano explicandole a alguien que cocina poco.\n\n"
        "Plato: %s (dificultad %s, para 4 porciones)\n"
        "Ya tiene en casa: %s\n"
        "Le falta comprar: %s\n"
        "Su presupuesto: S/ %s\n\n"
        "Escribe en espanol peruano, tuteando, calido y directo. Estructura:\n\n"
        "## Qué comprar\n"
        "Lista corta con un tip de mercado por producto (como escogerlo, "
        "cuando conviene comprarlo).\n\n"
        "## Preparación\n"
        "Pasos numerados, concretos, con tiempos. Nada de relleno.\n\n"
        "## El truco\n"
        "Un consejo que hace la diferencia en este plato.\n\n"
        "## Si te sobra\n"
        "Que hacer con lo que quede.\n\n"
        "Usa markdown simple. Maximo 400 palabras."
        % (receta, dificultad, ", ".join(tengo) or "casi nada",
           lista_falta, presupuesto)
    )
    return _llamar(prompt)


if __name__ == "__main__":
    print("Modelos disponibles con tu API key:\n")
    try:
        for m in modelos_disponibles():
            print("   ", m)
    except Exception as e:
        print("  Error:", e)
