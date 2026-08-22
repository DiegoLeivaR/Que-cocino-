# -*- coding: utf-8 -*-
"""Baja precios de las dos fuentes y arma el precios.js que usa la web.

  1. SISAP (MIDAGRI)  -> precio MAYORISTA real, diario. No es lo que pagas.
  2. Plaza Vea (VTEX) -> precio de LISTA del super, sin ofertas.

El precio que le mostramos al usuario es el de mercado de barrio, estimado
como  super / 1.20,  porque el super esta ~20% por encima del mercado.

Para los productos que el super no tiene, se usa el mayorista multiplicado
por el margen mediano observado en los que si tienen las dos fuentes.

Uso:  python actualizar.py
"""

import io
import json
import os
import statistics

import plazavea
import sisap

AQUI = os.path.dirname(os.path.abspath(__file__))


def generar(hablar=True):
    """Baja todo y escribe precios.json y precios.js. Devuelve el resumen."""
    def di(*a):
        if hablar:
            print(*a)

    di("1/2  Bajando precios mayoristas del SISAP...")
    d = sisap.precios()
    if not d["items"]:
        raise RuntimeError("No se pudo obtener el SISAP.")

    prods = {}
    for it in d["items"]:
        p = prods.setdefault(it["producto"], {"variedades": []})
        p["variedades"].append({"n": it["variedad"], "p": it["precio_kg"]})

    for nombre, p in prods.items():
        lista = [v["p"] for v in p["variedades"]]
        p["mayorista"] = round(min(lista), 2)
        p["cat"] = sisap.categoria_de(nombre)
        p["variedades"].sort(key=lambda v: v["p"])

    di("     %d productos, %d variedades (%s)\n"
       % (len(prods), len(d["items"]), d["fecha"]))

    di("2/2  Bajando precios de Plaza Vea...")
    supers = plazavea.todos(sorted(prods.keys())) if hablar else \
        {k: v for k, v in ((k, plazavea.precio_super(
            k, techo=plazavea.TECHO.get(k, plazavea.TECHO_DEFECTO)))
            for k in sorted(prods.keys())) if v}
    di("")

    # Margen real mayorista -> mercado, medido donde tenemos las dos fuentes.
    margenes = [(supers[n] / plazavea.FACTOR_SUPER) / p["mayorista"]
                for n, p in prods.items()
                if n in supers and p["mayorista"] > 0]
    margen_tipico = round(statistics.median(margenes), 2) if margenes else 2.0

    descartados = []
    for nombre, p in prods.items():
        estimado = round(p["mayorista"] * margen_tipico, 2)
        sup = supers.get(nombre)
        mercado = round(sup / plazavea.FACTOR_SUPER, 2) if sup else None

        # Nadie vende al publico mas barato que al por mayor. Si eso pasa, la
        # busqueda emparejo otra cosa (una unidad en vez de un kilo, por
        # ejemplo) y es mas honesto estimar que publicar un numero imposible.
        if mercado is not None and mercado < p["mayorista"]:
            descartados.append(nombre)
            mercado = None

        if mercado is not None:
            p["super"] = sup
            p["mercado"] = mercado
            p["fuente"] = "super"
        else:
            p["mercado"] = estimado
            p["fuente"] = "estimado"

    # Los precios que dio una persona que compra en el mercado mandan sobre
    # cualquier estimacion nuestra. Se cargan con calibrar.py.
    reales_path = os.path.join(AQUI, "precios-reales.json")
    n_reales = 0
    if os.path.exists(reales_path):
        with io.open(reales_path, encoding="utf-8") as f:
            reales = json.load(f).get("kilo", {})
        def poner(nombre, precio):
            """Un precio real de mercado entra si o si, exista o no en el SISAP."""
            if nombre in prods:
                prods[nombre]["mercado"] = round(float(precio), 2)
                prods[nombre]["fuente"] = "mercado"
            else:
                prods[nombre] = {
                    "variedades": [], "mayorista": round(precio / 1.5, 2),
                    "cat": "proteina" if any(w in nombre.lower() for w in
                            ("carne", "pescado", "pollo", "cerdo")) else "otros",
                    "mercado": round(float(precio), 2), "fuente": "mercado",
                }
            return 1

        for nombre, v in reales.items():
            if str(v.get("unidad", "")).startswith(("kil", "lit")):
                n_reales += poner(nombre, v["precio"])

        # Carne, queso, pescado: el SISAP no los cotiza, pero si alguien nos
        # dio el precio de mercado son tan reales como los demas. Entran al
        # catalogo para que las recetas puedan usarlos y costearlos.
        with io.open(reales_path, encoding="utf-8") as f:
            otros = json.load(f).get("otros", [])
        for x in otros:
            if not str(x.get("unidad", "")).startswith(("kil", "lit")):
                continue          # sin saber cuanto pesa un atado no sirve
            n_reales += poner(x["nombre"].strip().title(), x["precio"])

    salida = {
        "fecha": d["fecha"],
        "margen_tipico": margen_tipico,
        "factor_super": plazavea.FACTOR_SUPER,
        "productos": prods,
    }

    with io.open(os.path.join(AQUI, "precios.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)

    # precios.js se carga con <script src> y funciona sin servidor de archivos
    with io.open(os.path.join(AQUI, "precios.js"), "w", encoding="utf-8") as f:
        f.write("// Generado por actualizar.py - NO editar a mano\n")
        f.write("const PRECIOS = ")
        json.dump(salida, f, ensure_ascii=False, indent=1)
        f.write(";\n")

    con_super = sum(1 for p in prods.values() if p["fuente"] == "super")
    di("Resumen")
    di("  Fecha mayorista:    %s" % d["fecha"])
    di("  Productos:          %d  (%d con precio de super, %d estimados)"
       % (len(prods), con_super, len(prods) - con_super))
    di("  Margen mayorista -> mercado: x%.2f  (mediano observado)" % margen_tipico)
    if n_reales:
        di("  Precios verificados en el mercado (mandan sobre todo): %d" % n_reales)
    if descartados:
        di("  Descartados por dar menos que el mayorista: %s" % ", ".join(descartados))
    di("\nGenerados: precios.json y precios.js")

    return {"fecha": d["fecha"], "productos": len(prods), "con_super": con_super}


if __name__ == "__main__":
    generar()
