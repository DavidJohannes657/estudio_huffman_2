# 01 · Fundamentos y reglas del profesor

[← Volver al índice](../README.md) · Siguiente: [02 Cómo se suman los árboles](02-suma-de-arboles.md)

Aquí está todo lo que hay que saber **antes** de hacer un ejercicio: qué es Huffman, cómo se representan los bytes y, sobre todo, **las reglas exactas que definió el profesor** (que son distintas de otras guías de internet).

## Contenido

1. [Qué es Huffman](#1-qué-es-huffman)
2. [Vocabulario](#2-vocabulario)
3. [Bytes y ASCII](#3-bytes-y-ascii)
4. [Las 12 reglas del profesor](#4-las-12-reglas-del-profesor)
5. [Convenciones que puede cambiar el enunciado](#5-convenciones-que-puede-cambiar-el-enunciado)
6. [El factor de compresión](#6-el-factor-de-compresión)
7. [Lo que confirma el cuaderno y lo que no define](#7-lo-que-confirma-el-cuaderno-y-lo-que-no-define)

---

## 1. Qué es Huffman

Huffman es un algoritmo de compresión **sin pérdida**: con el archivo comprimido se recupera **exactamente** el original, byte por byte.

La idea es dar **códigos cortos** a los caracteres que más se repiten y **códigos largos** a los que menos. En un archivo normal todos los caracteres ocupan 8 bits. Con Huffman, la `a` de "anita patina" ocupa 2 bits (`10`) y la `p` ocupa 3 (`011`).

Tres propiedades importantes:

- **Sin pérdida.** Al descomprimir sale el mismo texto.
- **Longitud variable.** Cada carácter tiene un código de largo distinto.
- **Código prefijo.** Ningún código es el comienzo de otro (porque todos los caracteres son hojas del árbol). Gracias a eso se puede decodificar **sin separadores**: se lee bit a bit hasta llegar a una hoja.

> **No confundir:** el **ASCII** es el código original del carácter (un número de 0 a 255 que ocupa 8 bits). El **código de Huffman (CH)** es el código nuevo, de longitud variable, que se guarda en el archivo comprimido. Son dos cosas distintas.

## 2. Vocabulario

| Término | Significado |
| --- | --- |
| **TF** (o **FR**) | Frecuencia: cuántas veces aparece un carácter en el texto. |
| **ASCII** (o **AS**) | Número que identifica al carácter (97 = `a`, 32 = espacio). |
| **CH** | Código de Huffman del carácter: el camino de 0 y 1 desde la raíz hasta su hoja. |
| **Bits** | Bits que aporta un carácter al texto comprimido: `TF × largo de su CH`. |
| **lst** | La lista ordenada de menor a mayor de la que se sacan los dos primeros en cada paso. |
| **Hoja** | Nodo con un carácter. No tiene hijos. |
| **Nodo interno** | Nodo que une dos hijos. No guarda carácter, solo el peso total. |
| **Peso** | En una hoja es la frecuencia; en un nodo interno es la suma de los pesos de sus hijos. |
| **Raíz** | Último nodo que queda. Su peso es el largo total del texto. |
| **NT** (en el tablero **NF**) | Campo del archivo: cantidad de **nodos internos** (hojas − 1). |
| **Tree** | Campo del archivo: el árbol guardado en preorden. |
| **BS** | Campo del archivo: **bits válidos** del último byte del ZIP (de 1 a 8). |
| **ZIP** | Campo del archivo: los bits comprimidos agrupados en bytes. |

## 3. Bytes y ASCII

### 3.1 El byte

Un **byte** son 8 bits. Sus posiciones se numeran de 7 a 0, de izquierda a derecha, y cada una vale una potencia de 2:

| Posición | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Valor | 128 | 64 | 32 | 16 | 8 | 4 | 2 | 1 |

### 3.2 Con signo y sin signo

| Tipo | Rango | Dónde se usa |
| --- | --- | --- |
| **Sin signo** | 0 … 255 | Es el valor que se escribe en el tablero (190, 227, …). |
| **Con signo** | −128 … 0 … 127 | Así lo ven algunos lenguajes (por ejemplo Java). |

Si un byte vale más de 127, con signo aparece **negativo**: 190 se ve como −66 y 227 como −29. Para volver al valor sin signo se suma 256 (o en Java se hace `b & 0xFF`). Python ya trabaja sin signo (0 a 255).

### 3.3 Decimal a binario (restas sucesivas)

1. Recorre las posiciones de mayor a menor (128, 64, 32, …).
2. Si el valor **cabe** en la posición, escribe 1 y réstalo; si no cabe, escribe 0.
3. Completa siempre hasta 8 dígitos.

Ejemplo con **97** (la letra `a`): 97 − 64 = 33; 33 − 32 = 1; 1 − 1 = 0. Quedan encendidas 64, 32 y 1, así que 97 = `01100001`.

### 3.4 Binario a decimal

Suma el valor de cada posición que tenga 1. Ejemplo: `10111110` = 128 + 32 + 16 + 8 + 4 + 2 = **190**.

### 3.5 Tabla ASCII de los caracteres de las clases

| Carácter | Decimal | Binario de 8 bits |
| --- | --- | --- |
| espacio | 32 | `00100000` |
| a | 97 | `01100001` |
| b | 98 | `01100010` |
| d | 100 | `01100100` |
| i | 105 | `01101001` |
| l | 108 | `01101100` |
| n | 110 | `01101110` |
| p | 112 | `01110000` |
| s | 115 | `01110011` |
| t | 116 | `01110100` |

Para deducir otros: los dígitos van de 48 (`0`) a 57 (`9`), las mayúsculas de 65 (`A`) a 90 (`Z`), las minúsculas de 97 (`a`) a 122 (`z`) y el espacio es 32. Las letras consecutivas suben de uno en uno. **Mayúscula y minúscula son caracteres distintos** (`A` = 65, `a` = 97).

### 3.6 Tildes y la ñ

La `ñ` y las vocales con tilde **no** están en el ASCII de 7 bits. Si el archivo está en UTF-8, la `ñ` ocupa **dos bytes** (195 y 177) y el programa los trata como **dos símbolos distintos**. En los ejercicios de examen, el enunciado suele darles un solo valor de AS (como `ñ = 104` en el Test III).

## 4. Las 12 reglas del profesor

Salen del tablero (ejemplo "anita patina") y del código del cuaderno. **Son las que mandan en el examen.**

| # | Regla | Qué hace el profesor |
| --- | --- | --- |
| 1 | **Orden de la lista** | De menor a mayor frecuencia. Si hay empate, de menor a mayor ASCII. |
| 2 | **Qué se une** | Siempre los **dos primeros** de la lista. |
| 3 | **Izquierda y derecha** | El **primero** va a la izquierda (rama 0) y el **segundo** a la derecha (rama 1). |
| 4 | **Peso del nodo nuevo** | La **suma** de los pesos de sus dos hijos. |
| 5 | **Reinserción** | El nodo nuevo se coloca **después de todos los nodos que pesen lo mismo** (y de los que pesen menos). |
| 6 | **Código de un carácter** | El camino de la raíz a su hoja: 0 si baja a la izquierda, 1 si baja a la derecha. |
| 7 | **Factor de compresión** | Se pasa a bytes y se divide: bytes comprimidos ÷ bytes originales. |
| 8 | **Relleno** | Ceros al **final** del último byte, nunca entre códigos. |
| 9 | **BS** | Cuántos bits **válidos** tiene el último byte (de 1 a 8). |
| 10 | **NT (NF)** | Cantidad de nodos internos del árbol (hojas − 1). |
| 11 | **Árbol guardado** | En **preorden** y sin pesos. Nodo interno = `0 0`; hoja = `1` + su ASCII. |
| 12 | **Archivo total** | `NT`, `Tree`, `BS`, `ZIP`, en ese orden. |

La explicación de la regla 5 (la más importante) está en [02 Cómo se suman los árboles](02-suma-de-arboles.md).

## 5. Convenciones que puede cambiar el enunciado

| Convención | Tablero / cuaderno | Test III |
| --- | --- | --- |
| Rama izquierda | **0** | **1** |
| Rama derecha | **1** | **0** |
| Desempate | ASCII real | Columna **AS** que da el enunciado |

El árbol se arma **igual**: el primero de la lista va a la izquierda y el segundo a la derecha. Lo único que cambia es **el bit que se escribe en cada rama**. Por eso, con la convención invertida **cada código es el original con todos sus bits cambiados**: `a = 10` pasa a `01`, `n = 111` pasa a `000`.

- BS, NT y el factor **no cambian** (los códigos tienen el mismo largo).
- El **ZIP sí cambia**, porque los bits son otros.
- El **Tree no cambia**: se guarda en preorden (nodo, izquierda, derecha) y no incluye los bits de las ramas.

**Lee siempre la frase del enunciado antes de empezar**: el Test III dice "1: por las ramas izquierdas y 0: por las ramas derechas".

## 6. El factor de compresión

Es la relación entre los bytes comprimidos y los bytes originales, **ambos pasados a bytes redondeando hacia arriba**:

```
bytes originales  = número de caracteres
bytes comprimidos = ceil(bits totales / 8)
factor            = bytes comprimidos / bytes originales   (en %)
```

Con "anita patina": 30 bits = 3 bytes y sobran 6 bits, que ocupan un byte más → **4 bytes**. Factor = 4 ÷ 12 = **33,3 %**. Cuanto más bajo, mejor comprime.

En el tablero se escribe así: `30/8 = 3 bytes` y `30 % 8 = 6 bits`; luego se unen "3 bytes" con "6 bits" y resultan **4 bytes**.

El programa muestra dos factores:

- **Zip** = bytes del ZIP ÷ bytes originales (`4/12 = 33,3 %`). Es el del examen.
- **Archivo completo** = bytes de todo el archivo (con NT, Tree y BS) ÷ originales (`28/12 = 233,3 %`). En textos pequeños el árbol pesa más que el ahorro; en archivos grandes el árbol es despreciable.

## 7. Lo que confirma el cuaderno y lo que no define

El código del cuaderno (`huffman_gui.py`, formato `NT | Tree | BS | Zip`) fija estos detalles, que quedan **confirmados**:

- **NT** es 1 byte con el número de **nodos internos**.
- El **Tree** usa **2 bytes por nodo**: `0 0` para un nodo interno y `1 ASCII` para una hoja. Ocupa `4·NT + 2` bytes.
- **BS** es 1 byte con un valor de **1 a 8** (si el último byte está completo, vale 8).
- El árbol se recorre **primero la izquierda y luego la derecha** (preorden).

Puntos que el cuaderno **no define** y el programa resuelve por decisión propia:

| Caso | Qué hace el programa |
| --- | --- |
| Texto con **un solo carácter distinto** (por ejemplo `aaaa`) | El árbol es una sola hoja (NT = 0) y su código es `0`. |
| **Archivo vacío** | Muestra un error: no hay nada que comprimir. |
| **Salto de línea final** de un `.txt` | Cuenta como un carácter más (con su ASCII, 10 o 13 y 10). |

---

[← Volver al índice](../README.md) · Siguiente: [02 Cómo se suman los árboles](02-suma-de-arboles.md)
