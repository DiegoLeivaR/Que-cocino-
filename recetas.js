// Recetas peruanas con cantidades REALES en kg para 4 porciones.
// El campo "ing" usa exactamente los nombres de producto del SISAP.
// "extra" son ingredientes que el SISAP no cotiza (carnes rojas, salsas, especias).
const RECETAS = [
 { nombre: "Lentejas con Arroz", dif: "facil", min: 35,
   ing: { "Lenteja Grano Seco":0.35, "Arroz":0.35, "Cebolla":0.15,
          "Zanahoria":0.10, "Ajo":0.02, "Aceite":0.04 },
   extra: [], 
   pasos: "Remoja las lentejas. Sofrie cebolla, ajo y zanahoria. Agrega lentejas y agua, cocina 35 min. Sirve con arroz graneado." },

 { nombre: "Sopa de Verduras", dif: "facil", min: 30,
   ing: { "Zapallo":0.30, "Zanahoria":0.20, "Apio":0.10, "Papa":0.30, "Fideos":0.15, "Ajo":0.02 },
   extra: [],
   pasos: "Hierve el zapallo con apio y ajo. Licua. Vuelve a la olla con papa en cubos y zanahoria. Agrega fideos al final." },

 { nombre: "Tallarin Saltado", dif: "facil", min: 25,
   ing: { "Fideos":0.40, "Pollo":0.40, "Cebolla":0.20, "Tomate":0.20, "Aceite":0.05, "Ajo":0.02 },
   extra: ["sillao"],
   pasos: "Cocina los fideos. Saltea el pollo a fuego fuerte, agrega cebolla y tomate en gajos, sillao y une con los fideos." },

 { nombre: "Arroz Chaufa", dif: "facil", min: 25,
   ing: { "Arroz":0.40, "Huevos":0.25, "Pollo":0.35, "Cebolla":0.10, "Aceite":0.05 },
   extra: ["sillao", "cebolla china"],
   pasos: "Usa arroz del dia anterior. Haz tortilla con los huevos y cortala. Saltea el pollo, une todo con sillao a fuego alto." },

 { nombre: "Papa a la Huancaina", dif: "facil", min: 30,
   ing: { "Papa":0.80, "Aji Fresco":0.05, "Lechuga":0.10, "Huevos":0.20, "Aceite":0.08, "Leche":0.10 },
   extra: ["queso fresco", "galleta de soda"],
   pasos: "Sancocha las papas. Licua aji, queso, leche, galleta y aceite hasta que espese. Sirve sobre la papa en rodajas." },

 { nombre: "Estofado de Pollo", dif: "media", min: 45,
   ing: { "Pollo":0.80, "Papa":0.50, "Zanahoria":0.20, "Arveja Grano Verde":0.15,
          "Tomate":0.20, "Cebolla":0.15, "Ajo":0.02, "Aceite":0.04 },
   extra: [],
   pasos: "Dora el pollo. Sofrie cebolla, ajo y tomate. Devuelve el pollo con papa, zanahoria y arveja. Cocina tapado 30 min." },

 { nombre: "Arroz con Pollo", dif: "media", min: 50,
   ing: { "Pollo":0.80, "Arroz":0.40, "Culantro":0.10, "Arveja Grano Verde":0.15,
          "Zanahoria":0.10, "Cebolla":0.15, "Ajo":0.02, "Aceite":0.05 },
   extra: [],
   pasos: "Licua el culantro. Dora el pollo, sofrie aderezo, agrega el culantro licuado y el arroz. Cocina 20 min tapado." },

 { nombre: "Causa Limena", dif: "media", min: 40,
   ing: { "Papa":1.00, "Limon":0.15, "Aji Fresco":0.04, "Pollo":0.30, "Aceite":0.05, "Huevos":0.15 },
   extra: ["mayonesa", "palta"],
   pasos: "Prensa la papa amarilla sancochada con aji, limon y aceite. Arma capas con relleno de pollo deshilachado y mayonesa." },

 { nombre: "Lomo Saltado", dif: "media", min: 30,
   ing: { "Papa":0.50, "Cebolla":0.20, "Tomate":0.25, "Aji Fresco":0.02,
          "Aceite":0.05, "Arroz":0.35 },
   extra: ["carne de res (lomo)", "sillao", "vinagre"],
   pasos: "Frie las papas. Saltea la carne a fuego muy fuerte, agrega cebolla y tomate en gajos, sillao y vinagre. Sirve con arroz." },

 { nombre: "Aji de Gallina", dif: "complicado", min: 60,
   ing: { "Pollo":0.60, "Aji Fresco":0.08, "Papa":0.50, "Leche":0.20,
          "Arroz":0.35, "Cebolla":0.15, "Ajo":0.02, "Huevos":0.15 },
   extra: ["pan de molde", "queso parmesano", "nueces", "aceitunas"],
   pasos: "Cocina y deshilacha el pollo. Licua aji amarillo con pan remojado en leche. Une con el pollo y espesa. Sirve con papa y arroz." },

 { nombre: "Carapulcra", dif: "complicado", min: 75,
   ing: { "Papa":0.60, "Aji Fresco":0.06, "Cebolla":0.20, "Ajo":0.03, "Aceite":0.05, "Arroz":0.35 },
   extra: ["papa seca", "carne de cerdo", "mani tostado"],
   pasos: "Tuesta la papa seca y remojala. Sofrie el aderezo con aji panca, agrega el cerdo, la papa seca y mani molido. Cocina 1 hora a fuego lento." },

 { nombre: "Seco de Pollo con Frijoles", dif: "complicado", min: 70,
   ing: { "Pollo":0.90, "Frijol Grano Seco":0.35, "Culantro":0.15, "Cebolla":0.20,
          "Ajo":0.03, "Arroz":0.35, "Zapallo":0.15, "Aceite":0.05 },
   extra: ["chicha de jora"],
   pasos: "Cocina los frijoles con zapallo. Dora el pollo, sofrie aderezo con culantro licuado y chicha. Cocina tapado 40 min." }
];
