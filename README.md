# ¿Qué Cocino Hoy? — Prototipo

Recetas peruanas costeadas con **precios mayoristas reales** del SISAP (MIDAGRI).

## Cómo correrlo

```powershell
cd "$env:USERPROFILE\Documents\QueCocino"
python servidor.py
```

Se abre solo en el navegador. Para cortar: `Ctrl+C`.

Para bajar los precios del día:

```powershell
python actualizar.py
```

No hace falta instalar nada — solo Python, que ya tienes.

## Probarlo en el celular

La app **no puede vivir en GitHub Pages**. Pages sirve archivos estáticos, y
acá el `servidor.py` es imprescindible: guarda la API key, habla con Gemini y
consulta Plaza Vea. Si subes solo el HTML, la página carga y cada botón
responde 404.

### Opción rápida: la misma red wifi

Es lo que ya funciona, sin desplegar nada. Levanta el servidor en tu compu:

```powershell
python servidor.py
```

Al arrancar te imprime dos direcciones. Escribe **la segunda** en el navegador
del celular:

```
App corriendo en:    http://127.0.0.1:8765/index.html
Desde tu celular  :  http://192.168.18.3:8765/index.html
```

Requisitos: celular y computadora en el mismo wifi, y la compu prendida con el
servidor corriendo.

Dos advertencias reales:

- **Tu IP cambia.** El router reparte direcciones y mañana puede tocarte otra.
  Si deja de entrar, mira la dirección que imprime el servidor de nuevo.
- **Mientras corre, cualquiera en tu red puede abrirla** y gastar tu cuota de
  Gemini. En tu casa no importa; en el wifi de la universidad, sí. Córtalo con
  `Ctrl+C` al terminar.

### Opción completa: desplegarlo en Render

Para entrar desde cualquier lado hace falta un hosting que **ejecute Python**.

**Por qué Render y no Vercel/Netlify:** sus funciones serverless cortan a los
10 segundos y la llamada de visión tarda entre 13 y 23. Te cortaría siempre.

Pasos:

1. Sube el repo a GitHub (privado sirve igual).
2. En [render.com](https://render.com) → **New → Web Service** → conecta el repo.
   El `render.yaml` ya está, así que detecta la configuración solo.
3. En **Environment** agrega dos variables:

   | Variable | Valor |
   |---|---|
   | `GEMINI_API_KEY` | tu clave de AI Studio |
   | `ACCESO_PIN` | un PIN que te inventes, ej. `4821` |

`ia.py` lee `GEMINI_API_KEY` antes que `config.json`, así que la clave nunca
toca el repositorio.

**El plan gratis duerme** tras 15 minutos sin uso: el primer acceso tarda ~50
segundos en despertar. Para que esté siempre listo son unos $7 al mes.

### El PIN no es decoración

Sin `ACCESO_PIN`, tu URL pública deja que **cualquiera gaste tus 1500 requests
diarios**. Con la variable puesta:

- La app pide el PIN una vez y lo guarda en el navegador.
- Toda llamada a la IA sin el PIN correcto responde 401.
- Además hay un tope de 30 peticiones cada 10 minutos por IP.

En tu casa no pongas la variable y no verás ninguna pantalla de PIN.

### Los precios se refrescan solos en el hosting

Cuando corre desplegado, un hilo vuelve a bajar precios una vez al día. En tu
máquina no: ahí corres `actualizar.py` cuando quieras.

## Conectar la IA

Sin esto la app funciona igual, pero la foto no se analiza.

**1. Saca tu API key** (gratis, sin tarjeta) en https://aistudio.google.com/apikey

**2. Guárdala:**

```powershell
python configurar.py
```

Te pregunta el proveedor y te pide pegar la clave. **No se ve mientras la
escribes** (como una contraseña) y no queda en el historial de la terminal.

**3. Comprueba que sirve** y de paso mira qué modelos te habilita:

```powershell
python ia.py
```

### Alternativa: variable de entorno

Si prefieres no tener un archivo con la clave adentro — que es lo normal al
desplegar en un servidor de verdad — `ia.py` también lee de variables de
entorno, y esas ganan sobre `config.json`:

```powershell
$env:GEMINI_API_KEY = "tu-clave"
python servidor.py
```

### Los modelos se jubilan y el código se aguanta solo

Los nombres de modelo cambian cada pocos meses. Si el tuyo se jubila, `ia.py`
lo resuelve sin que toques nada:

1. Intenta con el modelo de `config.json`.
2. Si responde 404, lee la sugerencia que la propia API manda en el error
   ("Please update your code to use models/X") y reintenta con ese.
3. Si no sugiere nada, pide la lista de modelos y agarra el **flash de versión
   más alta** (descartando los de imagen, lite, preview y experimentales).
4. Se acuerda del reemplazo para el resto de la sesión.

Verificado: con `gemini-2.5-flash` (jubilado) se recupera solo y responde bien.

También reintenta hasta 3 veces con espera creciente ante errores 429 (pasaste
la cuota del minuto) y 503 (modelo saturado), que en el tier gratis son
normales.

### Si prefieres OpenAI

Cambia `"proveedor": "openai"` y pon un modelo con visión (por ejemplo
`gpt-4.1-mini`). Ojo: OpenAI cobra desde el primer request y pide tarjeta.
Gemini tiene tier gratis con visión incluida — por eso es el default.

### Por qué la key va en el servidor y no en el HTML

Si la key estuviera en el JavaScript, **cualquiera que abra la página podría
verla y gastarte la cuota**. Basta con abrir las herramientas de desarrollador.

Por eso el flujo es:

```
navegador  --(la foto)-->  servidor.py  --(foto + tu key)-->  Gemini
navegador  <--(ingredientes)--  servidor.py  <--(respuesta)--
```

La key vive en `config.json`, que está en `.gitignore`. **Nunca la subas a
GitHub, ni la pegues en un chat, ni la muestres en una captura de pantalla.**

Si se te escapa: entra a https://aistudio.google.com/apikey, dale **Borrar
clave** y saca una nueva. Es gratis y toma segundos. Una clave filtrada no se
"arregla" — se reemplaza.

## Qué hace la IA (tres llamadas)

1. **Foto → ingredientes.** La imagen va a 1568px y el prompt le pide un
   inventario completo: recorrer la foto por zonas, contar lo que está tapado
   o dentro de bolsas, y **ser generoso en vez de tímido** (es más fácil
   desmarcar de más que detectar de menos). Solo puede nombrar productos de
   la lista que tiene precio; el resto va a `otros`.
2. **`otros` → precio real.** Lo que ve pero el SISAP no cotiza (queso, pan,
   mantequilla) se busca **en vivo en Plaza Vea**, no se lo inventa el modelo.
   Aparecen como chips aparte, con su precio, y las recetas pueden usarlos.
3. **Qué tienes + dificultad + presupuesto → 4 recetas**, y luego
   **receta elegida → explicación** paso a paso.

### Por qué reconocía tan poco

Tres causas, las tres corregidas:

| Causa | Antes | Ahora |
|---|---|---|
| Catálogo corto | 30 productos | 63, con frutas |
| Modelo sin razonar | vía rápida | modelo que piensa |
| Prompt tímido | "no inventes" | "sé generoso, revisa si hallaste menos de 6" |
| Resolución | 1024px | 1568px |

### Dos modelos, a propósito

Los modelos nuevos "piensan" antes de responder. Para explicar un plato eso
vale oro; para armar una lista es plata tirada:

| Tarea | Modelo | Tiempo |
|---|---|---|
| Recetas | `modelo_rapido` (3.5-flash, sin pensar) | ~5 s |
| Visión | `modelo` (3.6-flash, pensando) | ~13 s |
| Explicación | `modelo` (3.6-flash, pensando) | ~15 s |

Con un solo modelo pensante, pedir recetas tardaba **50 segundos**. Pero al
revés también pasa: la visión con el modelo rápido reconocía la mitad de las
cosas, así que ahí sí vale la pena esperar. Los dos modelos se configuran en
`config.json`.

## Archivos

| Archivo | Qué hace |
|---|---|
| `sisap.py` | Cliente del SISAP. Toda la ingeniería inversa vive acá. |
| `actualizar.py` | Baja los precios de hoy y genera `precios.js` / `precios.json` |
| `plazavea.py` | Precios de supermercado vía la API pública de VTEX |
| `ia.py` | Conexión con Gemini/OpenAI (visión + texto) |
| `servidor.py` | Sirve la app y hace de intermediario con la IA |
| `recetas.js` | 12 recetas peruanas con cantidades reales en kg (4 porciones) |
| `index.html` | La app |
| `config.json` | Tu API key (lo creas tú; está en `.gitignore`) |

## Cómo se obtienen los precios

El SISAP no tiene API pública. Lo que hay es un formulario web, y por debajo llama a:

```
POST http://sistemas.midagri.gob.pe/sisap/portal2/mayorista/resumenes/filtrar
```

Parámetros que importan:

- `periodicidad=dia`
- `fecha=dd/mm/aaaa`
- `mercado=<código>`
- `productos[]=<código>` (se repite por cada producto)
- `variables[]=precio_prom` (o `precio_min`, `precio_max`, `volumen`)

Responde una tabla HTML, no JSON. `sisap.py` la parsea.

### Tres trampas del servidor

1. **No usa HTTPS moderno.** Su TLS es tan viejo que los clientes actuales lo rechazan. Hay que pegarle por `http://`.
2. **Miente sobre su encoding.** Declara UTF-8 pero devuelve **latin-1**. Si lo lees como UTF-8 revientan todos los acentos.
3. **Cada producto vive en un mercado distinto.** Verduras en el Gran Mercado Mayorista, pollo en el de Aves Vivas, abarrotes en Productores Santa Anita. `MERCADO_DE` en `sisap.py` hace ese ruteo.

Hay data diaria desde **1997**, así que se puede ver estacionalidad y tendencias, no solo el precio de hoy.

## De dónde sale cada precio

Hay tres capas y conviene no confundirlas:

| Capa | Qué es | Fuente |
|---|---|---|
| **Mayorista** | Lo que paga el que compra por sacos | SISAP (MIDAGRI), diario |
| **Mercado** | Lo que pagas tú en tu mercado — *esto es lo que muestra la app* | estimado |
| **Súper** | Precio de lista de Plaza Vea, sin ofertas | API de VTEX |

El estimado de mercado sale de la regla observada de que **el supermercado está
~20% por encima del mercado de barrio**:

    mercado = precio_lista_super / 1.20

### El hallazgo: el margen NO es parejo

Al principio la app usaba un margen fijo de +45% inventado a ojo. Cruzando las
dos fuentes reales quedó claro que eso no se sostiene:

| Producto | Mayorista | Mercado (est.) | Margen |
|---|---|---|---|
| Papa | 1.00 | 4.00 | +300% |
| Zanahoria | 1.04 | 2.74 | +164% |
| Cebolla | 1.48 | 3.25 | +120% |
| Pollo | 5.00 | 10.75 | +115% |
| Apio | 5.50 | 5.54 | +1% |

El margen mediano es **×2.10**, pero va desde casi nada hasta más de 300%. Un
solo número nunca iba a servir. Por eso ahora cada producto usa su propio
precio de súper, y el margen mediano solo se aplica a los pocos que el súper
no tiene (12 de 63).

### Lo que todavía hay que comprobar en el mercado

El 20% de diferencia súper–mercado es una observación tuya, no un dato medido.
Es el supuesto del que cuelga todo lo demás:

1. Ve a tu mercado y anota lo que te cobran por 10 productos.
2. Compara con la columna `super` de `precios.json`.
3. Si la diferencia real no es 20%, cambia `FACTOR_SUPER` en `plazavea.py`.

Ojo con dos cosas raras que ya se ven en los datos: el **choclo** sale más
barato en el súper que en el mayorista (algo está mal emparejado), y el
**pollo** mayorista es *pollo vivo*, que pesa ~30% más que el pollo pelado —
no son comparables directamente.

## Lo que el prototipo todavía NO hace

- **La visión no está probada con una foto real de cocina.** El pipeline sí
  está verificado de punta a punta con una imagen de prueba (reconoció los
  ingredientes y los mapeó al catálogo correctamente), pero con una refri de
  verdad —cosas en bolsas, al fondo del estante, mal iluminadas— puede fallar.
  Eso solo se sabe probando.
- **No hay carnes rojas.** El SISAP no cotiza res ni cerdo. Por eso el Lomo
  Saltado y la Carapulcra listan la carne como "extra" sin precio.
- **Solo Lima.** El SISAP tiene 27 ciudades más, pero el prototipo consulta los
  mercados mayoristas limeños.
- **Las unidades son aproximadas.** El SISAP cotiza por kilo; la gente compra por
  atado, manojo o unidad. Ese mapeo está hecho a ojo y hay que calibrarlo.

## Fuente

Datos: MIDAGRI–DGESEP–DEIA, Área de Comercio.
Portal: http://sistemas.midagri.gob.pe/sisap/portal2/mayorista/
