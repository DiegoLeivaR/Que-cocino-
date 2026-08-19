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
import statistics

import plazavea
import sisap

print("1/2  Bajando precios mayoristas del SISAP...")
d = sisap.precios()
if not d["items"]:
    raise SystemExit("No se pudo obtener el SISAP. Revisa tu conexion.")

prods = {}
for it in d["items"]:
    p = prods.setdefault(it["producto"], {"variedades": []})
    p["variedades"].append({"n": it["variedad"], "p": it["precio_kg"]})

for nombre, p in prods.items():
    lista = [v["p"] for v in p["variedades"]]
    p["mayorista"] = round(min(lista), 2)
    p["variedades"].sort(key=lambda v: v["p"])

print("     %d productos, %d variedades (%s)\n" % (
    len(prods), len(d["items"]), d["fecha"]))

print("2/2  Bajando precios de Plaza Vea...")
supers = plazavea.todos(sorted(prods.keys()))
print()

# Margen real mayorista -> mercado, medido donde tenemos las dos fuentes.
margenes = []
for nombre, p in prods.items():
    if nombre in supers and p["mayorista"] > 0:
        margenes.append((supers[nombre] / plazavea.FACTOR_SUPER) / p["mayorista"])
margen_tipico = round(statistics.median(margenes), 2) if margenes else 2.0

descartados = []
for nombre, p in prods.items():
    estimado = round(p["mayorista"] * margen_tipico, 2)
    sup = supers.get(nombre)
    mercado = round(sup / plazavea.FACTOR_SUPER, 2) if sup else None

    # Nadie vende al publico mas barato que al por mayor. Si eso pasa, la
    # busqueda emparejo otra cosa (una unidad en vez de un kilo, por ejemplo)
    # y es mas honesto estimar que publicar un numero imposible.
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

salida = {
    "fecha": d["fecha"],
    "margen_tipico": margen_tipico,
    "factor_super": plazavea.FACTOR_SUPER,
    "productos": prods,
}

with io.open("precios.json", "w", encoding="utf-8") as f:
    json.dump(salida, f, ensure_ascii=False, indent=1)

# precios.js se carga con <script src> y funciona sin servidor de archivos
with io.open("precios.js", "w", encoding="utf-8") as f:
    f.write("// Generado por actualizar.py - NO editar a mano\n")
    f.write("const PRECIOS = ")
    json.dump(salida, f, ensure_ascii=False, indent=1)
    f.write(";\n")

con_super = sum(1 for p in prods.values() if p["fuente"] == "super")
print("Resumen")
print("  Fecha mayorista:    %s" % d["fecha"])
print("  Productos:          %d  (%d con precio de super, %d estimados)"
      % (len(prods), con_super, len(prods) - con_super))
print("  Margen mayorista -> mercado: x%.2f  (mediano observado)" % margen_tipico)
if descartados:
    print("  Descartados por dar menos que el mayorista: %s" % ", ".join(descartados))
print("\nGenerados: precios.json y precios.js")
