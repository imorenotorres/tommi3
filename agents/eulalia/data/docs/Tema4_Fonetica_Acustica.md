# Tema 4. Fonética acústica

## 4.1. Preparación: el programa Praat

Antes de estudiar la fonética acústica necesitas instalar y aprender a usar **Praat**, el programa de referencia para el análisis acústico del habla.

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">4.1.1. Instalar Praat</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

1. En [http://www.fon.hum.uva.nl/praat/](http://www.fon.hum.uva.nl/praat/), escoge tu sistema operativo y descarga el programa.
2. Ejecuta el archivo descargado. Elige la carpeta de instalación.
3. Al ejecutar Praat aparecerán dos ventanas: **Praat Object** y **Praat Picture**. Usaremos solo la primera.
4. Para abrir un archivo de sonido: en *Praat Object*, selecciona *Read from file* en el menú *Read*. Elige un archivo WAV y haz clic en *Edit*.
5. Para oír el archivo, haz clic en el tabulador. Para oír solo una parte, selecciona con el ratón y haz clic en el tabulador.
6. Para **grabar**: selecciona *New → Record Mono Sound*. Haz clic en *Record* para empezar y *Stop* para parar. Pon un nombre y haz clic en *Save to list*. Luego selecciona el sonido y haz clic en *Write to wav file*.

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">4.1.2. Anotar archivos de sonido (TextGrid)</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

Las anotaciones permiten marcar trozos de un archivo de sonido para identificar qué sonidos o palabras aparecen en cada segmento.

1. Abre tu archivo de sonido en Praat.
2. Haz clic en el nombre del archivo y selecciona *Annotate → To TextGrid*. En "All tier names" indica "Sílabas" o "Fonemas" (o ambos).
3. Selecciona el sonido y su TextGrid correspondiente y pulsa *View & Edit*.
4. Para anotar un sonido:
   - Busca el punto de inicio → haz clic en el oscilograma → pulsa **Intro** (aparece una marca azul)
   - Busca el punto final → haz clic → pulsa **Intro**
   - Haz clic en la zona amarilla inferior y escribe tu anotación
5. Para guardar: selecciona *File → Save TextGrid as text file*.

</div>
</details>

---

## 4.2. El sonido

### 4.2.1. Propiedades físicas del sonido

Un sonido es una **perturbación del aire** que se propaga en forma de ondas sonoras. La forma de los recorridos de las partículas puede representarse en el tiempo, como muestra este gráfico:

![Onda sonora: amplitud, ciclo, fase de compresión y rarefacción](/static/eulalia/tema4/img/onda_sonora.png)

El movimiento se describe por dos propiedades:

- **Amplitud** (desplazamiento vertical): cuánto sube y baja la onda. Determina la intensidad.
- **Frecuencia** (tiempo por ciclo): cuántos ciclos completa por segundo, medido en **Hertzios** (Hz). Determina el tono.

Lo que hemos visto hasta ahora es una onda simple. Pero en la práctica lo que oímos es una combinación de múltiples ondas: las **ondas complejas**.

### 4.2.2. Ondas complejas

Para entender las ondas complejas hay que considerar tres aspectos: su producción, sus características y su percepción.

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">La fuente del sonido</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

Para producir un sonido audible se necesita una **fuente** que genere ondas. Hay dos tipos:

- **Fuentes periódicas** (vibratorias): como las cuerdas vocales o las cuerdas de una guitarra. Generan sonidos armónicos.

![Fuentes vibratorias: las cuerdas vocales (izquierda) y las cuerdas de una guitarra (derecha)](/static/eulalia/tema4/img/fuentes_vibratorias.png)

- **Fuentes no periódicas** (ruidosas): como estrechamientos en un tubo sin vibración. Generan ruido.

![Fuentes no vibratorias: la tráquea sin vibración de cuerdas vocales (izquierda) y un silbato (derecha)](/static/eulalia/tema4/img/fuentes_no_vibratorias.png)

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">Armónicos y frecuencia fundamental</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

Cuando una fuente periódica vibra, genera múltiples ondas simultáneas:

- La onda de más baja frecuencia es el **tono fundamental** (F0), cuya frecuencia coincide con la de vibración de la fuente.
- Las demás ondas son **armónicos**: su frecuencia es 2×, 3×, 4×... la fundamental.
- Ejemplo: si F0 = 100 Hz, los armónicos están a 200, 300, 400 Hz, etc.

Los armónicos se representan gráficamente como líneas verticales de igual altura:

![Representación visual de los armónicos](/static/eulalia/tema4/img/armonicos.png)

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">Resonancia</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

El sonido generado por la fuente tiene dos limitaciones: es muy suave y siempre igual. La **resonancia** es el mecanismo que permite:

- **Aumentar la potencia** del sonido para que sea audible.
- **Modificar el timbre** para que tenga propiedades acústicas diferenciales (distinguir vocales, consonantes, etc.).

En el ser humano, las cavidades supraglóticas actúan como resonadores. A diferencia de la caja de una guitarra (fija), el ser humano puede cambiar dinámicamente su resonador moviendo la lengua, los labios y el velo del paladar.

![Fuente (cuerdas vocales) → resonador (cavidades supraglóticas) → espectro resultante](/static/eulalia/tema4/img/fuente_resonador_voz.png)

![El mismo proceso en una guitarra: fuente (cuerdas) → resonador (caja) → espectro](/static/eulalia/tema4/img/fuente_resonador_guitarra.png)

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">Características de las ondas complejas</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

Las ondas complejas son el resultado de combinar varias ondas simples. La amplitud de la onda compleja en cada punto es la suma de las amplitudes de las ondas simples que la componen.

![Combinación de ondas simples (100, 200 y 300 Hz) formando una onda compleja](/static/eulalia/tema4/img/ondas_complejas.png)

Las ondas complejas se representan en programas como Praat mediante **oscilogramas**. Estos no permiten conocer las ondas simples que las forman, pero sí comprobar si una onda ha sido generada por una fuente periódica o por una fuente ruidosa.

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">La percepción de ondas complejas</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

Por el aire circula una sola onda compleja. Para reconocer los sonidos lingüísticos, el sistema auditivo debe descomponer esta onda en sus componentes simples.

Esta descomposición se realiza en la **cóclea**: diferentes zonas de la membrana basilar son sensibles a diferentes frecuencias. Las zonas cercanas al ápice responden a frecuencias bajas; las cercanas a la base, a frecuencias altas.

El oído funciona como un **banco de filtros solapados**: si dos frecuencias caen dentro del mismo filtro, una puede enmascarar a la otra.

</div>
</details>

### 4.2.3. Representación gráfica del sonido

Hay dos formas principales de representar el sonido:

**Oscilograma**: representa el tiempo en el eje horizontal y la amplitud en el eje vertical. Permite ver si una onda es periódica (sonido sonoro) o no periódica (ruido).

![Oscilograma de una señal de habla en Praat](/static/eulalia/tema4/img/oscilograma.png)

**Espectrograma**: representa el tiempo en el eje X, la frecuencia en el eje Y, y la intensidad como variaciones de gris (más oscuro = más energía). Existen dos tipos:

- **Banda ancha** (window length = 0.005 s): buena resolución temporal, se ven los formantes.

![Espectrograma de banda ancha: se distinguen los formantes](/static/eulalia/tema4/img/espectrograma_ancha.png)

- **Banda estrecha** (window length = 0.03 s): buena resolución frecuencial, se ven los armónicos individuales.

![Espectrograma de banda estrecha: se distinguen los armónicos](/static/eulalia/tema4/img/espectrograma_estrecha.png)

*En Praat: Spectrum → Spectrogram settings → Window Length.*

### 4.2.4. Propiedades lingüísticas del sonido

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">Sonoridad</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

Los sonidos generados por una fuente periódica son **sonoros** (armónicos, regulares): vocales, /b,d,g/, nasales, líquidas. Los generados por una fuente no periódica son **sordos** (ruidosos): fricativas sordas, africada.

*En Praat*: la línea azul en la parte baja del espectrograma indica sonoridad. En el oscilograma, una señal periódica (que se repite cíclicamente) indica sonido sonoro.

![Señal sonora periódica: la señal se repite en el oscilograma y la línea azul aparece en el espectrograma](/static/eulalia/tema4/img/sonoridad_praat.png)

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">Tono (F0)</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

El tono es la impresión auditiva que produce la frecuencia de vibración. A mayor frecuencia, más agudo. A menor frecuencia, más grave.

*En Praat*: la línea azul indica la F0. Para ver el valor: *Pitch → Show pitch*. Haz clic en un punto y selecciona *Pitch → Get pitch*.

![F0 en Praat: la línea azul indica la frecuencia fundamental. El valor aparece a la derecha del espectrograma](/static/eulalia/tema4/img/f0_praat.png)

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">Intensidad</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

La intensidad depende de la amplitud de la onda. Se mide en **decibelios** (dB).

*En Praat*: la línea verde indica la intensidad. *Intensity → Show intensity*. Para medir: *Intensity → Get intensity*.

![Intensidad en Praat: la línea verde indica la intensidad. El valor aparece en verde a la izquierda](/static/eulalia/tema4/img/intensidad_praat.png)

</div>
</details>

<details style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;">
<summary style="padding:10px 16px;cursor:pointer;font-weight:700;font-size:14px;color:#1e293b;background:#f8fafc;border-radius:8px;">Duración</summary>
<div style="padding:12px 16px;font-size:13px;line-height:1.8;">

La duración permite distinguir sonidos y diferenciar contextos. Por ejemplo, las vocales tónicas suelen ser más largas que las átonas.

*En Praat*: selecciona con el cursor el sonido que quieras medir. La duración aparece en la parte inferior.

![Duración en Praat: se selecciona un fragmento y la duración aparece en la parte inferior](/static/eulalia/tema4/img/duracion_praat.png)

</div>
</details>

---

## 4.3. Prosodia

Los rasgos prosódicos (o suprasegmentales) son propiedades del habla que afectan a unidades mayores que el fonema: sílabas, palabras, enunciados. Los tres correlatos acústicos relevantes son: F0, intensidad y duración.

### 4.3.1. El acento

El acento pone en relieve una sílaba con respecto a las demás. Puede lograrse por tres medios:

- **Acento de intensidad**: aumento de la amplitud en la sílaba acentuada.
- **Acento tónico** (musical): aumento del tono.
- **Acento de cantidad**: aumento de la duración.

En español, en **palabras aisladas** los tres correlatos (tono, intensidad, duración) marcan el acento. Observa cómo en las tres formas de "cantara" la sílaba acentuada tiene siempre más intensidad, tono y duración:

![Acento en cantará, cantara y cántara: la sílaba acentuada tiene más intensidad, tono y duración](/static/eulalia/tema4/img/acento_cantara.png)

En **contexto** (dentro de una frase), la intensidad y la duración son más relevantes que el tono. En el siguiente ejemplo ("mi lápiz no tiene punta"), la mayor intensidad corresponde a la vocal tónica, pero la mayor F0 corresponde a la sílaba siguiente:

![Acento en frase: la intensidad marca la sílaba tónica, pero la F0 se desplaza](/static/eulalia/tema4/img/acento_milapis.png)

En **acento enfático**, el tono vuelve a ser muy relevante. Observa cómo el máximo de F0 coincide con la partícula "NO" enfatizada:

![Acento enfático en "Alberto NO quiere comprar": el máximo de F0 coincide con NO](/static/eulalia/tema4/img/acento_enfatico.png)

### 4.3.2. La entonación

La entonación es la curva melódica con la que se pronuncia un enunciado. Se divide en tres partes:

- **Rama inicial**: desde el inicio hasta el primer pico de entonación.
- **Cuerpo**: desde el primer pico hasta la última vocal tónica. En español hay un descenso progresivo (declinación).
- **Rama final**: desde la última vocal tónica hasta el final. Es la parte más importante fonológicamente.

| Modalidad | Características |
|-----------|----------------|
| Enunciativa | Descenso suave en el cuerpo, caída final |
| Exclamativa | Picos muy marcados en el cuerpo |
| Interrogativa | Subida marcada en la rama final (≥20%) |

El siguiente gráfico muestra la línea melódica de una misma oración en tres modalidades. Observa las diferencias en el cuerpo (picos marcados en la exclamativa) y en la rama final (subida en la interrogativa):

![Entonación enunciativa, exclamativa e interrogativa de "María se fue"](/static/eulalia/tema4/img/entonacion_tipos.png)

---

## 4.4. Las vocales

### 4.4.1. Los formantes

Acústicamente, las vocales se caracterizan por una **configuración formántica** específica. Los formantes (F1, F2, F3...) son frecuencias de resonancia del tracto vocal. En español, con los dos primeros formantes (F1 y F2) se pueden diferenciar las cinco vocales.

Valores de referencia (voz masculina, Martínez Celdrán, 1998):

| | /i/ | /e/ | /a/ | /o/ | /u/ |
|---|---|---|---|---|---|
| **F1** (Hz) | 313 | 457 | 699 | 495 | 349 |
| **F2** (Hz) | 2200 | 1926 | 1471 | 1070 | 877 |

Los valores se representan en una **carta de formantes** (F1 en ordenadas, F2 en abscisas), que forma el **triángulo vocálico**:

![Carta de formantes o triángulo vocálico: F1 en el eje Y, F2 en el eje X](/static/eulalia/tema4/img/carta_formantes.png)

*En Praat*: los puntos rojos del espectrograma indican formantes. *Formant → Show formants*. Para medir: *Formant → Get first formant*.

### 4.4.2. Relación entre rasgos articulatorios y acústicos

Existe una correspondencia directa entre formantes y articulación:

- **F1 ↔ Modo de articulación** (altura de la lengua): cuanto más elevada la lengua, menor F1. Las vocales cerradas (/i/, /u/) tienen F1 bajo; la abierta (/a/) tiene F1 alto.

![Vocales ordenadas por F1: /i/, /u/ (F1 bajo, lengua alta) → /e/, /o/ → /a/ (F1 alto, lengua baja)](/static/eulalia/tema4/img/vocales_F1.png)

- **F2 ↔ Lugar de articulación** (posición anteroposterior): cuanto más anterior la lengua, mayor F2. /i/ tiene F2 alto (anterior); /u/ tiene F2 bajo (posterior).

![Vocales ordenadas por F2: /i/ (F2 alto, anterior) → /e/ → /a/ → /o/ → /u/ (F2 bajo, posterior)](/static/eulalia/tema4/img/vocales_F2.png)

### 4.4.3. Vocales en contexto: diptongos e hiatos

En producción aislada, los formantes son estables (líneas rectas en el espectrograma). En contexto, cambian conforme la lengua se mueve (**transiciones formánticas**).

![Transiciones formánticas: escala musical con "do re..." (formantes curvados) vs con /a/ (formantes rectos)](/static/eulalia/tema4/img/transiciones_formanticas.png)

| | Rasgos articulatorios | Rasgos acústicos |
|---|---|---|
| **Hiato** | Las vocales mantienen sus propiedades | Formantes estables, salto brusco entre vocales |
| **Diptongo** | Solo el núcleo mantiene sus propiedades; la vocal adyacente adopta rasgos consonánticos | Cambio suave, la vocal no nuclear se ve como transición |

![Diferencia acústica entre diptongo e hiato: en el diptongo el F2 cambia suavemente; en el hiato hay un salto brusco](/static/eulalia/tema4/img/diptongo_hiato.png)

---

## 4.5. Las consonantes

Las consonantes se diferencian de las vocales por la presencia de **obstáculos** en las cavidades supraglóticas, lo que reduce la energía y crea zonas sin resonancia.

| | Propiedades articulatorias | Propiedades acústicas |
|---|---|---|
| **Sonidos vocálicos** | Ausencia de obstáculos | Estructura formántica, mayor intensidad |
| **Sonidos consonánticos** | Obstáculos en cavidades | Menos energía, zonas de no resonancia |

### 4.5.1. Oclusivas

**Rasgos acústicos de las oclusivas:**

Las oclusivas se caracterizan por un **silencio** (cierre completo) seguido de una **explosión** (liberación). En el espectrograma:

- **Fase de silencio**: zona en blanco (sin energía).
- **Barra de explosión**: línea vertical de energía breve.
- **VOT** (Voice Onset Time): tiempo entre la explosión y el inicio de la sonoridad. Las oclusivas sordas tienen VOT mayor que las sonoras.

Compara una oclusiva (/p/ en "apa") con una fricativa (/s/ en "asa"). Observa el silencio previo a la explosión en la oclusiva y el ruido continuo en la fricativa:

![Espectrograma de "apa" (oclusiva: silencio + explosión) vs "asa" (fricativa: ruido continuo)](/static/eulalia/tema4/img/oclusiva_vs_fricativa.png)

Las oclusivas sordas (/p, t, k/) se diferencian entre sí por la zona de frecuencia de la explosión:
- /p/ (bilabial): explosión débil en frecuencias bajas
- /t/ (dental): explosión fuerte en frecuencias altas
- /k/ (velar): explosión concentrada en frecuencias medias

El VOT varía según la sonoridad y el lugar de articulación. En las sordas, el VOT es positivo (la sonoridad empieza después de la explosión):

![VOT de oclusivas sordas: el VOT marca la distancia entre la explosión y el inicio de la sonoridad](/static/eulalia/tema4/img/vot_sordas.png)

| Alófono | VOT (ms) |
|---------|----------|
| [p] | 6,5 |
| [t] | 10,4 |
| [k] | 25,7 |
| [b] | -69,8 |
| [d] | -77,7 |
| [g] | -58 |

Las **aproximantes** [β̞, ð̞, ɣ̞] (alófonos de /b, d, g/) muestran formantes debilitados pero sin interrupción — no hay silencio ni explosión. Compara la curva de intensidad entre una oclusiva y una aproximante:

![Oclusiva vs aproximante: la oclusiva muestra caída de intensidad (cierre); la aproximante no](/static/eulalia/tema4/img/oclusiva_vs_aproximante.png)

### 4.5.2. Fricativas

Las fricativas se producen con un estrechamiento que genera **turbulencia** (ruido). En el espectrograma se ven como una zona de ruido (energía dispersa, no armónica).

Se diferencian entre sí por la zona de frecuencia del ruido y su intensidad:

![Espectrograma de las cuatro fricativas sordas: /θ/, /s/, /x/, /f/](/static/eulalia/tema4/img/fricativas_espectrograma.png)

| Fricativa | Zona de ruido | Intensidad del pico |
|-----------|--------------|---------------------|
| /f/ (labiodental) | 2000-5000 Hz | 4 dB (muy débil) |
| /θ/ (interdental) | 3000-5000 Hz | 13 dB |
| /s/ (alveolar) | 3000-3680 Hz | 26 dB (la más intensa) |
| /x/ (velar) | 1000-3700 Hz | 20 dB |

**Variantes dialectales de la /s/**: la realización de /s/ varía considerablemente según el dialecto (seseo, ceceo, aspiración).

### 4.5.3. Africada

La africada /ʧ/ combina una fase oclusiva (silencio + explosión) seguida de una fase fricativa (ruido). En el espectrograma se ve como una secuencia de silencio → explosión → ruido de fricción.

![Espectrograma de la africada en "hacha": se observa la fase de silencio seguida de la fase de fricción](/static/eulalia/tema4/img/africada_hacha.png)

### 4.5.4. Nasales

Las nasales tienen una estructura formántica similar a las vocales, pero con **menor intensidad** (porque parte de la energía sale por la nariz). En el espectrograma:

- Formantes visibles pero débiles
- Un formante nasal bajo (alrededor de 250-300 Hz) muy marcado
- Antiformantes (zonas de cancelación de energía)

![Espectrograma de "ana": la nasal muestra formantes débiles y menor amplitud en el oscilograma](/static/eulalia/tema4/img/nasal_ana.png)

Las nasales se diferencian entre sí por las transiciones formánticas hacia y desde las vocales adyacentes, más que por su espectro propio. Observa en "la mañana" cómo el primer formante coincide en las tres nasales, pero el recorrido del segundo formante depende de qué consonante tiene antes y después:

![Espectrograma de "la mañana": se ven las tres nasales con transiciones formánticas diferentes](/static/eulalia/tema4/img/nasales_lamañana.png)

Valores de los formantes nasales (Quilis, 1981):

| Formante | [m] | [n] | [ɲ] |
|----------|-----|-----|-----|
| N1 | 270 Hz | 361 Hz | 292 Hz |
| N2 | 1020 Hz | 1400 Hz | 1630 Hz |
| N3 | 1990 Hz | 2372 Hz | 2420 Hz |

### 4.5.5. Líquidas (laterales y vibrantes)

Las líquidas tienen rasgos tanto vocálicos como consonánticos:

**Lateral /l/**: muestra formantes (como las vocales) pero con menor intensidad. En el espectrograma se ve como una vocal débil.

**Vibrante simple /ɾ/**: se ve como una breve interrupción de los formantes (un cierre muy corto seguido de una apertura).

**Vibrante múltiple /r/**: se ve como una secuencia de interrupciones rápidas de los formantes (2-3 cierres y aperturas). La vibrante múltiple es una repetición del patrón de la vibrante simple:

![Espectrograma de "pera" (vibrante simple) vs "perra" (vibrante múltiple)](/static/eulalia/tema4/img/vibrantes_pera_perra.png)

**Yeísmo**: en las variedades yeístas (la mayoría del español actual), no existe el fonema /ʎ/ (lateral palatal). La grafía "ll" se pronuncia como /ʝ/ (fricativa palatal), que acústicamente muestra ruido fricativo en frecuencias medias-altas.

### 4.5.6. Interpretación de espectrogramas: guía rápida

| Lo que ves en el espectrograma | Tipo de sonido |
|-------------------------------|----------------|
| Formantes claros y regulares | Vocal |
| Formantes débiles pero visibles | Nasal o lateral |
| Silencio + explosión | Oclusiva |
| Ruido continuo (sin estructura armónica) | Fricativa |
| Silencio + explosión + ruido | Africada |
| Formantes debilitados sin interrupción | Aproximante |
| Breve interrupción de formantes | Vibrante simple |
| Interrupciones múltiples rápidas | Vibrante múltiple |
| Línea azul en la parte baja | Sonido sonoro (F0 visible) |
| Sin línea azul | Sonido sordo |
