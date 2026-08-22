# -*- coding: utf-8 -*-
"""Carga precios reales de mercado y mide que tan lejos estabamos.

Uso:
  1. Escribe las respuestas en  precios-reales.txt,  una por linea:

        papa 3.50 kilo
        culantro 1.00 atado
        pollo 12 kilo

     El nombre puede ir con o sin tildes. La unidad es opcional
     (si no la pones, se asume kilo).

  2. Corre:  python calibrar.py

Lo que hace: compara con lo que la app muestra hoy, calcula el margen real
mayorista -> mercado, y guarda precios-reales.json. A partir de ahi
actualizar.py usa esos precios como verdad, por encima de cualquier estimado.
"""

import io
import json
import os
import re
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(AQUI, "precios-reales.txt")
SALIDA = os.path.join(AQUI, "precios-reales.json")

_TILDES = str.maketrans("áéíóúüñ", "aeiouun")


def norm(t):
    return t.lower().strip().translate(_TILDES)


def parsear(linea):
    """'papa amarilla 3.50 kilo' -> ('papa amarilla', 3.5, 'kilo')"""
    linea = linea.split("#")[0].strip()
    if not linea:
        return None
    m = re.match(r"^(.+?)\s+(?:s/\.?\s*)?(\d+(?:[.,]\d+)?)\s*(.*)$", linea, re.I)
    if not m:
        print("  no entendi esta linea, la salto:", linea)
        return None
    nombre = m.group(1).strip()
    precio = float(m.group(2).replace(",", "."))
    unidad = (m.group(3).strip().lower() or "kilo")
    return nombre, precio, unidad


def emparejar(nombre, catalogo):
    """Encuentra el producto del catalogo que corresponde al nombre escrito."""
    n = norm(nombre)
    for c in catalogo:                       # exacto
        if norm(c) == n:
            return c
    for c in catalogo:                       # 'papa' -> 'Papa'
        if norm(c).startswith(n) or n.startswith(norm(c)):
            return c
    for c in catalogo:                       # 'aji' -> 'Aji Fresco'
        if n in norm(c) or norm(c) in n:
            return c
    return None


def main():
    if not os.path.exists(ENTRADA):
        io.open(ENTRADA, "w", encoding="utf-8").write(
            "# Un producto por linea:  nombre  precio  unidad\n"
            "# La unidad es opcional; si no la pones se asume kilo.\n"
            "#\n"
            "# papa 3.50 kilo\n"
            "# culantro 1.00 atado\n"
        )
        raise SystemExit(
            "Cree %s.\nEscribe ahi los precios y vuelve a correr esto."
            % os.path.basename(ENTRADA))

    precios = json.load(io.open(os.path.join(AQUI, "precios.json"), encoding="utf-8"))
    P = precios["productos"]
    catalogo = list(P.keys())

    reales, sueltos = {}, []
    for linea in io.open(ENTRADA, encoding="utf-8"):
        d = parsear(linea)
        if not d:
            continue
        nombre, precio, unidad = d
        cat = emparejar(nombre, catalogo)
        if cat:
            reales[cat] = {"precio": precio, "unidad": unidad, "dicho": nombre}
        else:
            # no esta en el SISAP (carne, queso, pan...): igual lo guardamos
            sueltos.append({"nombre": nombre, "precio": precio, "unidad": unidad})

    if not reales and not sueltos:
        raise SystemExit("No habia ningun precio en el archivo.")

    print("PRECIOS REALES vs LO QUE MUESTRO\n")
    print("%-22s %9s %9s %9s  %s" % ("producto", "yo digo", "real", "error", "unidad"))
    print("-" * 68)

    errores, margenes = [], []
    por_kilo = {k: v for k, v in reales.items() if v["unidad"].startswith("kil")}

    for n, v in sorted(reales.items()):
        mio = P[n]["mercado"]
        real = v["precio"]
        if v["unidad"].startswith("kil"):
            err = (mio / real - 1) * 100
            errores.append(abs(err))
            margenes.append(real / P[n]["mayorista"])
            print("%-22s %9.2f %9.2f %8.0f%%  %s" % (n, mio, real, err, v["unidad"]))
        else:
            # no es por kilo: no se puede comparar sin saber cuanto pesa
            print("%-22s %9.2f %9.2f %9s  %s <- falta saber cuanto pesa"
                  % (n, mio, real, "?", v["unidad"]))

    if errores:
        print("\nQue tan lejos estaba")
        print("  error tipico:   %.0f%%" % statistics.median(errores))
        print("  el peor:        %.0f%%" % max(errores))
        print("  margen real mayorista -> mercado:  x%.2f  (yo usaba x%.2f)"
              % (statistics.median(margenes), precios["margen_tipico"]))

        # el supuesto del que cuelga todo: super = mercado x 1.20
        con_super = [(n, P[n]["super"], reales[n]["precio"])
                     for n in por_kilo if P[n].get("super")]
        if con_super:
            factores = [s / r for _, s, r in con_super]
            f = statistics.median(factores)
            print("\nEl supuesto del 20%%")
            print("  super / mercado real:  x%.2f  (yo asumia x1.20)" % f)
            if abs(f - 1.20) > 0.15:
                print("  -> hay que cambiar FACTOR_SUPER en plazavea.py a %.2f" % f)
            else:
                print("  -> el 1.20 se sostiene, no toques nada")

    if sueltos:
        print("\nProductos que no cotizo (los guardo igual)")
        for x in sueltos:
            print("  %-24s S/ %.2f por %s" % (x["nombre"], x["precio"], x["unidad"]))

    json.dump({"kilo": reales, "otros": sueltos},
              io.open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nGuardado en %s" % os.path.basename(SALIDA))
    print("Corre  python actualizar.py  para que la app los use.")


if __name__ == "__main__":
    main()
