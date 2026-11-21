[English](README.md) | **Español**

# Taquilla en España 2020–2026: cuándo estrenar, en cuántos cines y qué estrenar

*Google Data Analytics – Caso práctico 3 (caso propio). Herramientas: Python (pdfplumber, pandas), SQL (DuckDB), Power BI.*

## 1. Objetivo de negocio (Preguntar)

**Cliente:** una distribuidora de cine independiente española que planifica sus estrenos de los dos próximos años.

**Objetivo de negocio:** *identificar qué ventanas de estreno, qué amplitud de estreno y qué origen (español o extranjero) dan los mejores resultados en taquilla en España tras la COVID, y comparar los resultados de las distribuidoras independientes con los de las majors de Hollywood, para que el cliente decida cuándo, en cuántos cines y qué estrenar.*

| | |
|---|---|
| **Partes interesadas** | Dirección y equipo de adquisiciones de la distribuidora (qué comprar), equipo de marketing y programación (cuándo y en cuántos cines estrenar) |
| **Público** | Directivos sin perfil técnico: una presentación de 30 minutos apoyada en un informe interactivo de Power BI |
| **Métricas clave** | Recaudación del fin de semana (EUR), espectadores, precio medio de la entrada, recaudación del primer fin de semana, recaudación total, *legs* o recorrido (recaudación total ÷ primer fin de semana), tasa de éxito (porcentaje de películas que superan 1 M EUR), caída semanal, cuota de recaudación por origen y por tipo de distribuidora |
| **Preguntas** | 1) ¿Qué tamaño tiene el mercado y se ha recuperado? 2) ¿Cuándo conviene estrenar? 3) ¿Es el cine español una buena apuesta y cómo se comparan los estrenos españoles y extranjeros? 4) ¿Cómo se comparan las independientes con las majors? 5) ¿En cuántos cines conviene estrenar? |

## 2. Fuentes de datos (Preparar)

| Fuente | Contenido | Cobertura | Archivos |
|---|---|---|---|
| ICAA (Ministerio de Cultura): [Taquilla y espectadores](https://www.cultura.gob.es/cultura/areas/cine/datos/taquilla-espectadores.html), **Top 25** semanal | Puesto, título en español y original, distribuidora, semanas en cartel, cines, pantallas, recaudación y espectadores del fin de semana, variación %, recaudación y espectadores acumulados | 341 fines de semana, enero 2020 – 15 noviembre 2026 | 343 PDF |
| ICAA, **cine español en cartelera** semanal | Mismos campos, todas las películas españolas en cartel (no solo las del Top 25) | 337 fines de semana, 2020–2026 | 337 PDF |
| ICAA, **recaudación y espectadores anuales del cine español** | Cada película española por año natural, con fecha de estreno | 2016–2025 + 2026 hasta la fecha | 11 PDF |

* Las cifras las elabora Comscore (Rentrak) y las publica el ICAA. El propio ICAA advierte de que no son su estadística oficial.
* **ROCCC:** *Fiable*: medición estándar en la industria, publicada por un organismo público. *Original*: es una fuente primaria. *Completa*: cobertura semanal completa, aunque el Top 25 deja fuera la cola larga. *Actual*: llega a noviembre de 2026. *Citada*: cada fila conserva su archivo de origen.
* **Licencia y privacidad:** información pública del sector público, reutilizable citando la fuente (Ley 37/2007). No contiene datos personales.
* Los PDF originales están en `data/raw/icaa/` y no se modifican nunca. `manifest.csv` registra la URL y la hora de descarga de cada archivo.
* **Validación con una cifra oficial independiente:** la lista anual de 2023 da 81,5 M EUR y 13,2 M de espectadores para el cine español. La nota de prensa del Ministerio indica 82,4 M EUR y 13,4 M, una diferencia de alrededor del 1%.

**Limitaciones conocidas**
* El Top 25 no es todo el mercado. Su cuota es muy alta la mayoría de los fines de semana, pero los totales semanales no incluyen las películas de la cola larga.
* Las películas estrenadas antes de enero de 2020 que seguían en cartel (p. ej. *El rey león*) aparecen sin datos completos de estreno y se excluyen de las métricas de estrenos.
* No hay datos de género, presupuesto ni inversión en marketing (ver sección 6).
* Desde junio de 2026 la fuente dejó de publicar las **pantallas**, así que se usa el número de **cines** como medida de la amplitud del estreno.

## 3. Limpieza y transformación (Procesar)

Proceso reproducible: ejecutar en orden `py scripts/01_download_icaa.py` … `05_build_pbip.py`.

**Cómo ejecutarlo.** Los PDF originales (154 MB) no están en el repositorio; `01_download_icaa.py` los vuelve a descargar. Los CSV limpios de `data/clean/` sí están incluidos, así que el informe de Power BI funciona sin ejecutar el proceso.
1. `py -m pip install -r requirements.txt`
2. Ejecuta los scripts en orden. `05_build_pbip.py` escribe en el parámetro `DataFolder` tu ruta local.
3. Si solo abres el proyecto de Power BI, cambia `DataFolder` en *Transformar datos → Editar parámetros* a tu carpeta `data/clean/` (con la barra invertida final) y pulsa **Actualizar**.

| Paso | Script | Qué hace |
|---|---|---|
| Descarga | `01_download_icaa.py` | Recorre la página del ICAA y descarga 701 PDF con reintentos, una pausa entre peticiones y un registro de descargas (manifest) |
| Extracción | `02_extract_tables.py` | En los PDF solo la fila de cabecera tiene líneas. El script toma los límites de las columnas de la cabecera y asigna cada palabra a su fila y columna según sus coordenadas |
| Limpieza y modelo | `03_clean_model.py` | Limpia los datos y construye el modelo en estrella en `data/clean/` |
| Análisis | `04_analysis.py` + `sql/analysis.sql` | 17 consultas SQL en DuckDB, resultados en `analysis/*.csv` |
| Dashboard | `05_build_pbip.py` | Genera el proyecto de Power BI (`powerbi/`) |

**Problemas encontrados y cómo se resolvió cada uno** (los recuentos están en `data/clean/data_quality_report.md`):

1. **Las fechas no venían en los PDF.** Los archivos de 2020–21 no tenían año en el nombre (`top25-26-28-febrero.pdf`). El año se dedujo sabiendo que cada fin de semana empieza en viernes, lo que deja un único año posible entre 2020 y 2023. También se resolvieron los nombres con una sola fecha (`25enero` = sábado) y los que abarcan dos meses (`30-1-agosto`).
2. **Archivos mal etiquetados.** Dos nombres tenían el mes equivocado (`27-29-diciembre` es en realidad el 27–29 de noviembre de 2020). Se detectaron y corrigieron comparando las *semanas en cartel* de las películas con las de los fines de semana vecinos. Los enlaces mal etiquetados en la web del ICAA y las erratas como `espaniol` o `epaniol` se reclasificaron por el nombre del archivo.
3. **Errores en el origen.** Dos fines de semana tenían rota la columna de espectadores: 3–5 de febrero de 2023 (espectadores truncados) y 14–16 de junio de 2024 (valores repetidos desde la fila 7). Se detectaron por un precio implícito de la entrada imposible: fuera de 4–12 EUR para la mediana de un archivo o de 3–30 EUR para una fila. 28 filas se reconstruyeron con la diferencia de espectadores acumulados y 23 se estimaron con el precio mediano de la entrada de ese fin de semana. Todas quedan marcadas en `admissions_imputed`.
4. **Texto superpuesto en el PDF.** Desordenó 19 filas (6 películas con títulos originales muy largos). Se corrigieron con un mapeo manual.
5. **Nombres incoherentes.** Las 393 grafías de distribuidoras se redujeron a 318 nombres canónicos (`WBI`/`Warner Bros Int'l` → *Warner Bros*, `ACONTRA` → *A Contracorriente*…), y cada una se clasificó como *Major*, *Independiente* o *Autodistribución*. Los títulos se normalizaron (`Working Man, A` → `A Working Man`).
6. **Identidad de las películas.** Las filas semanales se agruparon en 2.250 estrenos cuando comparten el título original o el título en español (por ejemplo, "Inside Out 2" y "Del Revés 2 (Inside out 2)"). Después se separaron por fecha de estreno para que los reestrenos y los remakes queden aparte. Hay 92 reestrenos marcados.
7. **Origen español.** Una película es española si aparece ese mismo fin de semana en la lista del ICAA de cine español en cartel (553 películas) o en la lista anual (7 más).
8. Se descartaron las fotos parciales del año superadas por el archivo del año completo. Las pantallas que faltan quedan vacías (null), no a cero. No hay duplicados por fin de semana y puesto.

**Modelo en estrella:** `fact_weekend_top25` (8.525 filas) · `fact_weekend_spanish` (10.304) · `fact_annual_spanish` (4.832) · `dim_film` (2.250) · `dim_distributor` (318) · `dim_date` (2016–2026, con temporada, ventanas de Semana Santa y Navidad y periodo COVID).

## 4. Resumen del análisis (Analizar)

Las comparaciones se hacen sobre los **estrenos posteriores a la COVID (2022–2026)** que entraron en el Top 25, sin contar reestrenos (1.607 películas). Todas las cifras salen de `analysis/`.

**Mercado (q01, q07).** La recaudación del Top 25 se estancó en 276–286 M EUR entre 2023 y 2025. En 2026 ya suma **320 M EUR en 46 fines de semana**, el mejor año de la serie: la recaudación media por fin de semana sube un 31% respecto a 2025. Hasta 2026 el crecimiento venía del **precio, no del público**: la entrada media pasó de 7,04 EUR (2023) a 7,82 EUR (2026, +11%) mientras los espectadores se mantenían en 37–41 M. El mercado está muy concentrado: las 10 películas más taquilleras se llevan entre el **34% y el 47%** de la recaudación anual del Top 25, y el 20% de películas más taquilleras, entre el 83% y el 89%.

**Calendario (q02, q03, q10, q11).** La demanda alcanza su máximo en **julio** (7,0 M EUR por fin de semana) y **diciembre** (6,3 M); febrero y septiembre son los meses más flojos (4,8–4,9 M). Pero la oferta pesa tanto como la demanda:
* Las películas estrenadas en **diciembre** tienen la mejor recaudación total mediana (376k EUR), tasa de éxito (30%) y recorrido (3,4x). Les siguen octubre (294k) y febrero (330k).
* **Los estrenos de mayo a julio tienen las medianas más bajas** (53–87k EUR). La demanda del verano se la llevan los blockbusters de las majors.
* Los fines de semana con **9 o más estrenos** reducen el primer fin de semana mediano a 30–40k EUR, frente a 60–126k cuando hay 4–6 estrenos.

**Español frente a extranjero (q04, q09, q10).** Las películas españolas igualan a las extranjeras en primer fin de semana mediano (62k EUR en ambos casos) y en recaudación total mediana (165k frente a 151k). Aguantan algo mejor: recorrido de 2,44 frente a 2,35, y entre las semanas 5 y 8 caen un 31–37% frente a un 38–43%. En cambio, tienen menos éxitos: una tasa del 19% frente al 24%. La temporada de estreno cambia el panorama:
* **Los estrenos españoles de verano** destacan: mediana de 258k EUR y tasa de éxito del 28%, frente a 72k de las extranjeras de verano. Son comedias familiares como *Padre no hay más que uno*.
* **Los estrenos españoles de primavera** son el segmento más débil: mediana de 68k EUR y tasa de éxito del 8%.

La cuota española de la recaudación del Top 25 oscila entre el 15% y el 24% según unos pocos éxitos.

**Estrenos españoles y extranjeros en detalle (q15–q17).**
* **Volumen frente a dinero.** Las películas españolas son alrededor del 26–30% de los estrenos, pero entre 2023 y 2025 solo obtuvieron alrededor del 16–17% de la recaudación de los estrenos. En 2026 subió al 25% gracias a *La bola negra* y *Torrente, presidente*.
* **Con la misma amplitud de estreno.** Hasta 249 cines, las películas españolas recaudan lo mismo que las extranjeras o más (mediana de 276k frente a 248k EUR entre 150 y 249 cines). Por encima de 250 cines recaudan menos (2,98 M frente a 6,05 M EUR con 325 o más) y menos por cine, pero aguantan más (recorrido de 4,8x frente a 4,0x). Es decir, el cine español rinde menos sobre todo porque pocas películas se estrenan en muchos cines, no porque funcione peor con la misma amplitud.
* **Quién las distribuye.** Las majors distribuyen solo el 23% de las películas españolas (100 de 437), pero se llevan el 61% de su recaudación. Las independientes se llevan el 39% de la recaudación del cine español, frente al 13% de la del cine extranjero: el cine español es donde las independientes compiten de verdad.

**Distribuidoras (q05, q06).** Las majors se llevan entre el 76% y el 89% de la recaudación del Top 25, pero **la cuota de las independientes se ha duplicado, del 11% (2022) al 24% (2026)**. Entre las independientes hay grandes diferencias:
* **Elastica** (66,8 M EUR, tasa de éxito del 26%, recorrido 3,4) y **Beta Fiction** (tasa de éxito del 35%) hacen pocos estrenos, comerciales y en muchos cines.
* **A Contracorriente** (136 películas, tasa de éxito del 6,6%) y **Filmax** (83 películas, 2,4%) trabajan con mucho volumen de cine de autor y de género.

**Amplitud del estreno (q08).** Los resultados dan un salto a partir de unos **250 cines**:
* La tasa de éxito pasa del 11% (150–249 cines) al 53% (250–324) y al 96% (325 o más).
* La recaudación del primer fin de semana *por cine* se duplica en cada tramo: 563 EUR → 1.148 EUR → 3.301 EUR.
* El recorrido sube de 2,3x a 3,1x y luego a 4,1x.

*Advertencia:* es una correlación. Las distribuidoras estrenan en más cines las películas de las que ya esperan buenos resultados.

## 5. Visualizaciones (Compartir)

Proyecto de Power BI: `powerbi/SpainBoxOffice.pbip`. Ábrelo en Power BI Desktop y pulsa **Actualizar**. La ruta de los datos es el parámetro `DataFolder`, en *Transformar datos → Editar parámetros*.

| Página | Qué responde |
|---|---|
| 1. Market Overview | Indicadores clave, recaudación anual por origen, curva de recuperación mensual, majors frente a independientes, concentración y precio de la entrada |
| 2. Release Timing | Demanda por mes del año, resultados por mes de estreno, tabla de ventanas de estreno y tasa de éxito por mes |
| 3. Spanish Cinema | Comparativa de cine español y extranjero, curvas de caída semanal, cine español 2016–2026 y películas más taquilleras |
| 3b. Spanish vs Foreign | Cuota de estrenos frente a cuota de recaudación por año, resultados con la misma amplitud de estreno, majors frente a independientes según el origen |
| 4. Distributors | Clasificación de distribuidoras, cuota por tipo y año, tasa de éxito por distribuidora |
| 5. Release Strategy | Amplitud del estreno frente a recaudación, tasa de éxito y recorrido por tramo de cines, dispersión por película |

El modelo tiene 26 medidas DAX, entre ellas tasa de éxito, cuota española de estrenos y de recaudación, recorrido mediano, caída semanal, concentración del top 10 y variación interanual. Tema visual: rojo y azul marino.

Los filtros de año de todas las páginas muestran solo años posteriores a 2019, sin quitar de los totales las películas de 2019 que seguían en cartel a principios de 2020.

## 6. Recomendaciones y próximos pasos (Actuar)

**Conclusiones principales para el cliente**
1. **Estrenar menos películas, pero en más cines.** Por debajo de unos 150 cines casi ninguna película llega a 1 M EUR. Conviene concentrar el marketing en títulos que puedan abrir en 250 cines o más, y estrenar el resto en circuito de autor con poco gasto en copias y publicidad.
2. **Estrenar cuando hay menos oferta.** Diciembre, octubre y febrero dan los mejores resultados por película. Hay que evitar mayo–julio salvo que sea una comedia familiar española, y los fines de semana con 9 o más estrenos.
3. **El cine español comercial es una apuesta competitiva.** Tiene la misma recaudación mediana que el extranjero, mejor recorrido y un nicho en verano que las majors no cubren. El modelo de Elastica y Beta Fiction (pocos títulos españoles, comerciales y en muchos cines) supera al de mucho volumen.
4. **Planificar el recorrido.** Las películas españolas aguantan mejor a partir de la cuarta semana. Conviene negociar mantener las pantallas en lugar de aceptar una caída rápida.
5. **El crecimiento basado en el precio es frágil.** Los espectadores no crecen, así que los estrenos-evento y la creación de público importan más que el precio de la entrada.

**Entregables adicionales para ampliar el análisis**
* Añadir **género, duración, reparto y dirección** (Wikidata o TMDB) para estudiar qué explica los éxitos.
* Añadir los **totales anuales oficiales del mercado** (estadística del ICAA) para medir la cobertura del Top 25.
* Añadir **presupuesto e inversión en marketing** (si el cliente los tiene) para medir la rentabilidad según la amplitud del estreno.
* Construir un **modelo predictivo** de la recaudación total a partir del primer fin de semana, la amplitud y la temporada.
* Añadir datos **por región y por cadena de cines**, y las ventanas de estreno en streaming, para optimizar la programación.

---
*Estructura de carpetas:* `data/raw` (PDF + manifest) · `data/interim` (extracción en bruto) · `data/clean` (modelo + informe de calidad) · `sql/` · `analysis/` · `scripts/` · `powerbi/`.
