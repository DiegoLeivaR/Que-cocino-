# -*- coding: utf-8 -*-
"""Guarda tu API key en config.json sin que tengas que editar JSON a mano.

Uso:  python configurar.py

La clave se escribe directo al archivo. No se muestra en pantalla ni queda
en el historial de la terminal.
"""

import getpass
import io
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "config.json")

PROVEEDORES = {
    "1": ("gemini", "gemini-3.6-flash", "Gemini  (gratis, recomendado)"),
    "2": ("openai", "gpt-4.1-mini", "OpenAI  (de pago)"),
}

print("Configurar la IA de 'Que Cocino Hoy'\n")

if os.path.exists(CONFIG):
    if input("Ya existe config.json. Lo reemplazo? (s/n): ").strip().lower() != "s":
        raise SystemExit("Cancelado, no toque nada.")

print("Proveedor:")
for k, (_, _, desc) in PROVEEDORES.items():
    print("  %s) %s" % (k, desc))
op = input("\nElige [1]: ").strip() or "1"
proveedor, modelo_def, _ = PROVEEDORES.get(op, PROVEEDORES["1"])

if proveedor == "gemini":
    print("\nSaca tu clave gratis en: https://aistudio.google.com/apikey")
else:
    print("\nSaca tu clave en: https://platform.openai.com/api-keys")

# getpass no muestra lo que escribes, como cuando pones una contrasena
clave = getpass.getpass("\nPega tu API key (no se va a ver al escribir): ").strip()

if not clave:
    raise SystemExit("No pegaste nada. Cancelado.")

modelo = input("Modelo [%s]: " % modelo_def).strip() or modelo_def

with io.open(CONFIG, "w", encoding="utf-8") as f:
    json.dump({"proveedor": proveedor, "api_key": clave, "modelo": modelo,
           "modelo_rapido": "gemini-3.5-flash-lite" if proveedor == "gemini"
                            else "gpt-4.1-mini"},
              f, ensure_ascii=False, indent=1)

print("\nGuardado en config.json  (clave de %d caracteres)" % len(clave))
print("Ese archivo esta en .gitignore, asi que no se sube a GitHub.\n")
print("Ahora prueba que funcione:   python ia.py")
