---
name: actualizar-precios
description: Refresca los precios de QueCocino desde el SISAP y Plaza Vea, y revisa que los datos tengan sentido antes de darlos por buenos. Úsala cuando el usuario pida actualizar precios, diga que los precios están viejos, o cuando el margen mayorista-mercado se vea raro.
---

# Actualizar los precios de QueCocino

Los precios vienen de dos fuentes que fallan de maneras distintas. Correr el
script no basta: hay que revisar el resultado.

## Cómo correrlo

```powershell
cd "$env:USERPROFILE\Documents\QueCocino"
python actualizar.py
```

Tarda ~1 minuto: el SISAP son 3 llamadas y Plaza Vea son ~30, con pausa entre
cada una para no abusar del sitio.

## Qué revisar después (esto es lo importante)

Compara siempre contra `precios.json`. Estos son los síntomas conocidos:

**1. Productos sin precio de súper.** Mira cuántos quedaron con
`"fuente": "estimado"`. Si son más de 6 de 30, la búsqueda de Plaza Vea se
rompió — probablemente cambiaron los nombres de sus productos. Se arregla
ajustando `BUSQUEDA` en `plazavea.py`.

**2. Mercado más barato que mayorista.** No tiene sentido pagar menos en el
súper que al por mayor. Si aparece, es que la búsqueda emparejó otro producto.
El choclo ya tiene este problema pendiente.

**3. Márgenes disparatados.** El margen normal va de ×1 a ×3. Si algo sale
×5 o más, revisa ese producto a mano:

```powershell
python -c "import plazavea; print(plazavea.precio_super('Papa'))"
```

**4. El SISAP devolvió vacío.** Pasa los domingos y feriados. El código
retrocede hasta 5 días solo, pero si la fecha en `precios.json` quedó muy
vieja, avísale al usuario en vez de fingir que está fresco.

## Comprobación rápida

```powershell
python -c "
import io,json
d=json.load(io.open('precios.json',encoding='utf-8'))
p=d['productos']
est=[k for k,v in p.items() if v['fuente']=='estimado']
raros=[k for k,v in p.items() if v['mercado']<v['mayorista']]
altos=[k for k,v in p.items() if v['mercado']/v['mayorista']>5]
print('fecha:',d['fecha'],'| productos:',len(p))
print('sin precio de super (%d):'%len(est), ', '.join(est) or 'ninguno')
print('mercado<mayorista:', ', '.join(raros) or 'ninguno')
print('margen >x5:', ', '.join(altos) or 'ninguno')
"
```

## Cosas que NO hay que hacer

- **No inventes un margen.** Si un producto no tiene precio de súper, se usa el
  margen mediano observado. No lo estimes a ojo — ese error ya se cometió una
  vez (había un +45% inventado que resultó estar 4 veces por debajo de lo real
  en verduras).
- **No uses `Price` de Plaza Vea, usa `ListPrice`.** `Price` trae la oferta del
  día y las ofertas no representan el precio normal.
- **No toques `FACTOR_SUPER` (1.20) sin datos.** Ese número sale de la
  observación del usuario de que el súper está ~20% sobre el mercado. Solo se
  cambia si él midió en el mercado y salió otra cosa.

## Contexto

- `sisap.py` — mayorista, MIDAGRI. Solo `http://` (su TLS es viejo) y decodifica
  en latin-1 aunque diga UTF-8.
- `plazavea.py` — súper, API pública de VTEX. `FACTOR_SUPER = 1.20`.
- `actualizar.py` — junta ambas y escribe `precios.json` + `precios.js`.
