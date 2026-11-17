"""
Compresor / Descompresor Huffman con interfaz gráfica (Tkinter).

FORMATO DEL ARCHIVO COMPRIMIDO (el del cuaderno):   NT | Tree | BS | Zip

    NT    1 byte   -> número de nodos internos del árbol
    Tree           -> árbol en preorden, 2 bytes por nodo:
                          nodo interno = 0 0
                          hoja         = 1 ASCII
                      (ocupa 4*NT + 2 bytes)
    BS    1 byte   -> bits significativos (válidos) del último byte del Zip (1..8)
    Zip            -> los códigos de Huffman unidos y agrupados de 8 en 8 bits

COMPRIMIR: cada archivo se guarda como  nombre.ext.zip  con ese formato.

DESCOMPRIMIR acepta:
    - Archivos Huffman con cualquier extensión (.zip, .pkz, .huf, ...).
      También lee la variante en la que el nodo interno es un solo 0.
    - Comprimidos normales: .zip, .tar, .gz, .tgz, .bz2, .xz, .lzma (sin instalar nada)
      y .rar, .7z, .cab, .iso, .arj, .lzh, ... si el computador tiene 7-Zip
      (gratis, https://www.7-zip.org), WinRAR, bsdtar o The Unarchiver.

Ejecutar:   python huffman_gui.py
"""

import os
import sys
import bz2
import gzip
import lzma
import shutil
import tarfile
import tempfile
import zipfile
import subprocess
import threading
from collections import Counter
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ======================================================================
#                          ALGORITMO DE HUFFMAN
# ======================================================================
class Nodo:
    def __init__(self, frecuencia, simbolo=None, izq=None, der=None):
        self.frecuencia = frecuencia
        self.simbolo = simbolo      # byte (0..255) si es hoja, None si es interno
        self.izq = izq
        self.der = der

    def es_hoja(self):
        return self.simbolo is not None


def construir_arbol(frecuencias):
    """Une siempre los dos nodos de menor frecuencia hasta que queda uno."""
    lista = [Nodo(f, s) for s, f in sorted(frecuencias.items(), key=lambda x: (x[1], x[0]))]
    while len(lista) > 1:
        a = lista.pop(0)            # el menor   -> rama 0 (izquierda)
        b = lista.pop(0)            # el segundo -> rama 1 (derecha)
        nuevo = Nodo(a.frecuencia + b.frecuencia, izq=a, der=b)
        pos = 0
        while pos < len(lista) and lista[pos].frecuencia <= nuevo.frecuencia:
            pos += 1
        lista.insert(pos, nuevo)
    return lista[0]


def generar_codigos(nodo, prefijo="", codigos=None):
    if codigos is None:
        codigos = {}
    if nodo.es_hoja():
        codigos[nodo.simbolo] = prefijo or "0"     # un solo símbolo -> código "0"
    else:
        generar_codigos(nodo.izq, prefijo + "0", codigos)
        generar_codigos(nodo.der, prefijo + "1", codigos)
    return codigos


def serializar_arbol(nodo, salida):
    """Tree en preorden: nodo interno = 0 0, hoja = 1 ASCII."""
    if nodo.es_hoja():
        salida += [1, nodo.simbolo]
    else:
        salida += [0, 0]
        serializar_arbol(nodo.izq, salida)
        serializar_arbol(nodo.der, salida)


def leer_arbol(datos, pos, doble=True):
    """Reconstruye el árbol desde el Tree. Devuelve (nodo, siguiente_posición).
    doble=True  -> nodo interno = 0 0 (formato del cuaderno)
    doble=False -> nodo interno = 0   (variante de un solo byte)"""
    marca = datos[pos]
    if marca == 1:                                  # hoja: el siguiente byte es el ASCII
        return Nodo(0, simbolo=datos[pos + 1]), pos + 2
    if marca != 0 or (doble and datos[pos + 1] != 0):
        raise ValueError("marca de árbol inválida")
    izq, pos = leer_arbol(datos, pos + (2 if doble else 1), doble)   # primero la izquierda
    der, pos = leer_arbol(datos, pos, doble)                         # luego la derecha
    return Nodo(0, izq=izq, der=der), pos


def contar_internos(nodo):
    if nodo.es_hoja():
        return 0
    return 1 + contar_internos(nodo.izq) + contar_internos(nodo.der)


def leer_cabecera(datos, tamano_total=None, doble=True):
    """Lee NT | Tree | BS. Devuelve (nt, raiz, bs, inicio_del_zip) o lanza ValueError."""
    tamano_total = len(datos) if tamano_total is None else tamano_total
    try:
        nt = datos[0]
        raiz, pos = leer_arbol(datos, 1, doble)
        bs = datos[pos]
    except (IndexError, RecursionError):
        raise ValueError("cabecera incompleta")
    if contar_internos(raiz) != nt or not 1 <= bs <= 8 or tamano_total <= pos + 1:
        raise ValueError("cabecera inválida")
    return nt, raiz, bs, pos + 1


def comprimir(datos):
    """Devuelve (bytes_comprimidos, texto_con_el_detalle_del_cálculo)."""
    if not datos:
        raise ValueError("El archivo está vacío: no hay nada que comprimir.")

    frecuencias = Counter(datos)
    raiz = construir_arbol(frecuencias)
    codigos = generar_codigos(raiz)

    # Unir los códigos y agrupar de 8 en 8 bits. Se hace por bloques para que
    # funcione rápido y sin gastar mucha memoria con archivos grandes.
    tabla = [codigos.get(i, "") for i in range(256)]
    partes, resto, BLOQUE = [], "", 1 << 16
    for i in range(0, len(datos), BLOQUE):
        bits = resto + "".join(map(tabla.__getitem__, datos[i:i + BLOQUE]))
        completos = len(bits) // 8 * 8
        if completos:
            partes.append(int(bits[:completos], 2).to_bytes(completos // 8, "big"))
        resto = bits[completos:]
    bs = len(resto) or 8                            # bits válidos del último byte
    if resto:
        partes.append(bytes([int(resto.ljust(8, "0"), 2)]))   # relleno con ceros
    zip_bytes = b"".join(partes)

    tree = []
    serializar_arbol(raiz, tree)
    nt = contar_internos(raiz)
    resultado = bytes([nt]) + bytes(tree) + bytes([bs]) + zip_bytes

    detalle = texto_compresion(datos, frecuencias, codigos, zip_bytes, nt, raiz, bs, resultado)
    return resultado, detalle


def tabla_de_decodificacion(raiz):
    """Para cada nodo interno y cada byte posible (0..255) calcula, recorriendo
    los 8 bits en el árbol, a qué nodo se llega y qué letras salen. Así se
    descomprime byte por byte en vez de bit por bit (mucho más rápido)."""
    internos = []

    def numerar(n):
        if not n.es_hoja():
            n.id = len(internos)
            internos.append(n)
            numerar(n.izq)
            numerar(n.der)
    numerar(raiz)

    tabla = []
    for inicio in internos:
        for byte in range(256):
            nodo, salida = inicio, bytearray()
            for k in range(7, -1, -1):
                nodo = nodo.der if (byte >> k) & 1 else nodo.izq
                if nodo.es_hoja():
                    salida.append(nodo.simbolo)
                    nodo = raiz
            tabla.append((nodo.id * 256, bytes(salida)))
    return tabla, internos


def decodificar(raiz, zip_bytes, bs):
    """Recorre el árbol con los bits del Zip. Devuelve (datos, terminó_bien)."""
    total_bits = (len(zip_bytes) - 1) * 8 + bs
    if raiz.es_hoja():                              # un solo símbolo en todo el archivo
        return bytes([raiz.simbolo]) * total_bits, True

    tabla, internos = tabla_de_decodificacion(raiz)
    partes, estado = [], 0                          # estado 0 = raíz
    for byte in zip_bytes[:-1]:                     # bytes completos
        estado, letras = tabla[estado + byte]
        partes.append(letras)
    nodo, ultimo = internos[estado // 256], zip_bytes[-1]
    for k in range(7, 7 - bs, -1):                  # último byte: solo los BS bits válidos
        nodo = nodo.der if (ultimo >> k) & 1 else nodo.izq
        if nodo.es_hoja():
            partes.append(bytes([nodo.simbolo]))
            nodo = raiz
    return b"".join(partes), nodo is raiz


def descomprimir(datos):
    """Devuelve (bytes_originales, texto_con_el_detalle_del_cálculo)."""
    intentos = []
    for doble in (True, False):                     # primero 0 0 (cuaderno), luego 0
        try:
            intentos.append((doble,) + leer_cabecera(datos, doble=doble))
        except ValueError:
            pass
    if not intentos:
        raise ValueError("El archivo no tiene el formato Huffman NT | Tree | BS | Zip.")

    primero = None
    for doble, nt, raiz, bs, inicio in intentos:
        salida, bien = decodificar(raiz, datos[inicio:], bs)
        if primero is None:
            primero = (doble, nt, raiz, bs, inicio, salida, bien)
        if bien:
            break
    else:
        doble, nt, raiz, bs, inicio, salida, bien = primero

    detalle = texto_descompresion(nt, raiz, bs, datos[inicio:], salida, doble, bien)
    return salida, detalle


# ----------------------------------------------------------------------
# cálculo 
# ----------------------------------------------------------------------
def legible(b):
    especiales = {32: "esp", 10: "\\n", 13: "\\r", 9: "\\t"}
    if b in especiales:
        return especiales[b]
    return chr(b) if 32 < b < 127 else f"#{b}"


def texto_tree(raiz, maximo=24):
    fichas = []

    def recorrer(n):
        if len(fichas) > maximo:
            return
        if n.es_hoja():
            fichas.append(f"1 {n.simbolo}")
        else:
            fichas.append("00")
            recorrer(n.izq)
            recorrer(n.der)
    recorrer(raiz)
    texto = " ".join(fichas[:maximo])
    return texto + (" ..." if len(fichas) > maximo else "")


def texto_codigos(codigos):
    lineas = [f"{'Letra':>7} {'ASCII':>6}  Código"]
    for s, c in sorted(codigos.items(), key=lambda x: (len(x[1]), x[1])):
        lineas.append(f"{legible(s):>7} {s:>6}  {c}")
    return lineas


def texto_compresion(datos, frecuencias, codigos, zip_bytes, nt, raiz, bs, resultado):
    L = [f"Tamaño original: {len(datos)} bytes x 8 = {len(datos) * 8} bits", "",
         "TABLA DE FRECUENCIAS",
         f"{'Letra':>7} {'TF':>9} {'ASCII':>6} {'Código':>14} {'Bits':>10}"]
    total = 0
    for s, f in sorted(frecuencias.items(), key=lambda x: (-x[1], x[0])):
        b = f * len(codigos[s])
        total += b
        L.append(f"{legible(s):>7} {f:>9} {s:>6} {codigos[s]:>14} {b:>10}")
    L += [f"Total = {total} bits", ""]
    if len(datos) <= 40:
        L += ["SECUENCIA: " + " ".join(codigos[b] for b in datos), ""]
    L.append("ZIP" + (" (primeros 10 bytes)" if len(zip_bytes) > 10 else ""))
    for i, valor in enumerate(zip_bytes[:10]):
        L.append(f"   byte {i + 1}: {valor:08b} = {valor}")
    largo_tree = 4 * nt + 2
    L += ["",
          f"NT   = {nt}",
          f"Tree = {texto_tree(raiz)}   ({largo_tree} bytes = 4·NT + 2)",
          f"BS   = {bs}",
          f"Archivo = 1 + {largo_tree} + 1 + {len(zip_bytes)} = {len(resultado)} bytes", "",
          f"Zip:             {len(zip_bytes)}/{len(datos)} bytes = {len(zip_bytes) / len(datos) * 100:.1f} %",
          f"Archivo completo: {len(resultado)}/{len(datos)} bytes = {len(resultado) / len(datos) * 100:.1f} %"]
    return "\n".join(L) + "\n"


def texto_descompresion(nt, raiz, bs, zip_bytes, salida, doble, bien):
    total_bits = (len(zip_bytes) - 1) * 8 + bs
    L = [f"NT   = {nt}   (nodos internos)",
         f"Tree = {texto_tree(raiz)}",
         f"       (nodo interno = {'0 0' if doble else '0'}, hoja = 1 ASCII)",
         f"BS   = {bs}   (bits válidos del último byte)",
         f"Zip  = {len(zip_bytes)} bytes -> {len(zip_bytes)} x 8 - {8 - bs} = {total_bits} bits", "",
         "CÓDIGOS QUE SALEN DEL ÁRBOL (izquierda = 0, derecha = 1)"]
    L += ["   " + x for x in texto_codigos(generar_codigos(raiz))]
    L += ["", f"Resultado: {len(salida)} bytes recuperados"]
    if len(salida) <= 80 and all(32 <= b < 127 for b in salida):
        L.append(f'Mensaje: "{salida.decode()}"')
    if not bien:
        L.append("Aviso: sobraron bits al final que no forman ninguna letra (revisar BS o Zip).")
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------
# Averiguar la extensión por los primeros bytes (si el nombre no la tiene)
# ----------------------------------------------------------------------
def detectar_extension(d):
    if d.startswith(b"PK\x03\x04"):
        cabeza = d[:4000]
        for clave, ext in ((b"word/", "docx"), (b"xl/", "xlsx"), (b"ppt/", "pptx")):
            if clave in cabeza:
                return ext
        return "zip"
    firmas = [(b"%PDF", "pdf"), (b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpg"), (b"GIF8", "gif"),
              (b"\xd0\xcf\x11\xe0", "doc"), (b"ID3", "mp3"), (b"\xff\xfb", "mp3"), (b"OggS", "ogg"),
              (b"Rar!", "rar"), (b"7z\xbc\xaf", "7z"), (b"\x1f\x8b", "gz"), (b"MZ", "exe"),
              (b"\x1a\x45\xdf\xa3", "mkv"), (b"BM", "bmp"), (b"{\\rtf", "rtf")]
    for firma, ext in firmas:
        if d.startswith(firma):
            return ext
    if d.startswith(b"RIFF") and d[8:12] in (b"WAVE", b"AVI ", b"WEBP"):
        return {b"WAVE": "wav", b"AVI ": "avi", b"WEBP": "webp"}[d[8:12]]
    if d[4:8] == b"ftyp":
        return "mp4"
    try:
        d[:4000].decode("utf-8")
        return "txt"
    except UnicodeDecodeError:
        return "bin"


# ======================================================================
#                    COMPRIMIR / DESCOMPRIMIR ARCHIVOS
# ======================================================================
EXT_HUFFMAN = (".zip", ".pkz", ".huf")


def nombre_original(nombre, datos):
    """doc.doc.zip -> doc.doc ;  mensaje.zip -> mensaje.txt (extensión por su contenido)"""
    if nombre.lower().endswith(EXT_HUFFMAN):
        nombre = nombre[:-4]
    if "." not in nombre:
        nombre += "." + detectar_extension(datos)
    return nombre or "archivo"


def comprimir_archivo(ruta, ruta_zip):
    """Comprime un archivo con Huffman y lo guarda como .zip. Devuelve (detalle, original, final)."""
    with open(ruta, "rb") as f:
        datos = f.read()
    comprimido, detalle = comprimir(datos)
    with open(ruta_zip, "wb") as f:
        f.write(comprimido)
    return detalle, len(datos), len(comprimido)


def parece_huffman(ruta):
    """¿El archivo tiene la forma NT | Tree | BS | Zip? (sin importar la extensión)"""
    try:
        tamano = os.path.getsize(ruta)
        with open(ruta, "rb") as f:
            cabecera = f.read(2048)                 # el Tree ocupa como máximo 1022 bytes
    except OSError:
        return False
    for doble in (True, False):
        try:
            leer_cabecera(cabecera, tamano, doble)
            return True
        except ValueError:
            pass
    return False


EXTENSIONES = ("*.zip *.pkz *.huf *.rar *.7z *.zipx *.tar *.gz *.tgz *.bz2 *.tbz2 *.xz *.txz "
               "*.lzma *.cab *.iso *.arj *.lzh *.lha *.z *.wim *.jar")

FIRMA_GZ, FIRMA_BZ2, FIRMA_XZ = b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00"
FIRMA_7Z, FIRMA_RAR = b"7z\xbc\xaf\x27\x1c", b"Rar!\x1a\x07"


def ruta_segura(base, nombre):
    """Evita que un archivo comprimido escriba fuera de la carpeta (rutas con '..')."""
    partes = [p.replace(":", "_") for p in nombre.replace("\\", "/").split("/")
              if p not in ("", ".", "..")]
    return os.path.join(base, *partes) if partes else None


def quitar_extension(nombre):
    for ext in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if nombre.lower().endswith(ext):
            return nombre[:-len(ext)]
    return os.path.splitext(nombre)[0]


def buscar_programa(nombres, rutas_windows=()):
    for n in nombres:
        encontrado = shutil.which(n)
        if encontrado:
            return encontrado
    for carpeta in {os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                    os.environ.get("ProgramW6432"), r"C:\Program Files", r"C:\Program Files (x86)"}:
        for r in rutas_windows:
            if carpeta and os.path.isfile(os.path.join(carpeta, r)):
                return os.path.join(carpeta, r)
    return None


def programas_externos(es_rar):
    """Programas instalados que pueden extraer: 7-Zip, UnRAR (WinRAR), The Unarchiver, bsdtar."""
    lista = []
    exe = buscar_programa(("7z", "7zz", "7za"), (r"7-Zip\7z.exe",))
    if exe:
        lista.append(("7-Zip", lambda a, d, exe=exe: [exe, "x", "-y", f"-o{d}", a]))
    if es_rar:
        exe = buscar_programa(("unrar", "UnRAR"), (r"WinRAR\UnRAR.exe",))
        if exe:
            lista.append(("UnRAR", lambda a, d, exe=exe: [exe, "x", "-y", "-o+", a, d + os.sep]))
    exe = buscar_programa(("unar",))
    if exe:
        lista.append(("The Unarchiver", lambda a, d, exe=exe: [exe, "-f", "-o", d, a]))
    exe = buscar_programa(("bsdtar",)) or (shutil.which("tar") if sys.platform in ("win32", "darwin") else None)
    if exe:
        lista.append(("tar", lambda a, d, exe=exe: [exe, "-xf", a, "-C", d]))
    return lista


def extraer_con_programa(ruta, destino, es_rar, formato=None):
    programas = programas_externos(es_rar)
    sin_ventana = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for nombre, comando in programas:
        try:
            r = subprocess.run(comando(ruta, destino), capture_output=True, creationflags=sin_ventana)
        except OSError:
            continue
        if r.returncode == 0 and any(os.scandir(destino)):
            return f"extraído con {nombre}"
        for x in os.scandir(destino):                    # limpiar intento fallido
            shutil.rmtree(x.path) if x.is_dir() else os.remove(x.path)
    if programas and formato:
        raise ValueError(f"No se pudo abrir el archivo {formato}. Puede estar dañado "
                         "o protegido con contraseña.")
    if programas:
        raise ValueError("No se reconoce el formato del archivo: no es Huffman (NT | Tree | BS | Zip) "
                         "ni un comprimido conocido, o está dañado.")
    raise ValueError(f"Para abrir {formato or 'este tipo de archivo'} se necesita un programa extra.\n\n"
                     "Instala 7-Zip (gratis): https://www.7-zip.org\n"
                     "y vuelve a intentarlo. No hace falta cambiar nada en este programa.")


def extraer_contenedor(ruta, destino):
    """Extrae un comprimido normal (zip, tar, gz, 7z, rar, ...) en 'destino'."""
    with open(ruta, "rb") as f:
        cabecera = f.read(8)
    nombre = os.path.basename(ruta)

    if zipfile.is_zipfile(ruta):
        with zipfile.ZipFile(ruta) as z:
            for info in z.infolist():
                salida = ruta_segura(destino, info.filename)
                if info.is_dir() or not salida:
                    continue
                os.makedirs(os.path.dirname(salida), exist_ok=True)
                with z.open(info) as origen, open(salida, "wb") as f:
                    shutil.copyfileobj(origen, f)
        return "ZIP estándar"

    if tarfile.is_tarfile(ruta):
        with tarfile.open(ruta) as t:
            for m in t.getmembers():
                salida = ruta_segura(destino, m.name)
                if not m.isfile() or not salida:
                    continue
                os.makedirs(os.path.dirname(salida), exist_ok=True)
                with t.extractfile(m) as origen, open(salida, "wb") as f:
                    shutil.copyfileobj(origen, f)
        return "TAR"

    simples = {FIRMA_GZ: (gzip.open, "GZIP"), FIRMA_BZ2: (bz2.open, "BZIP2"), FIRMA_XZ: (lzma.open, "XZ")}
    for firma, (abrir, formato) in simples.items():
        if cabecera.startswith(firma):
            interno = quitar_extension(nombre)
            if interno == nombre:
                interno += ".salida"
            with abrir(ruta, "rb") as origen, open(os.path.join(destino, interno), "wb") as f:
                shutil.copyfileobj(origen, f)
            return formato

    if cabecera.startswith(FIRMA_7Z):
        try:
            import py7zr                                       # opcional: pip install py7zr
            with py7zr.SevenZipFile(ruta) as z:
                z.extractall(destino)
            return "7Z"
        except ImportError:
            return "7Z, " + extraer_con_programa(ruta, destino, es_rar=False, formato=".7z")

    if cabecera.startswith(FIRMA_RAR):
        return "RAR, " + extraer_con_programa(ruta, destino, es_rar=True, formato=".rar")

    return extraer_con_programa(ruta, destino, es_rar=False)


def descomprimir_archivo(ruta, carpeta):
    """Descomprime un archivo. Devuelve (detalle, lista_de_archivos_creados)."""
    os.makedirs(carpeta, exist_ok=True)

    # 1. Archivo Huffman directo (NT | Tree | BS | Zip), con cualquier extensión
    if parece_huffman(ruta):
        with open(ruta, "rb") as f:
            datos, detalle = descomprimir(f.read())
        destino = os.path.join(carpeta, nombre_original(os.path.basename(ruta), datos))
        with open(destino, "wb") as f:
            f.write(datos)
        return ("Formato detectado: Huffman (NT | Tree | BS | Zip)\n"
                f"{os.path.basename(ruta)}  →  {os.path.basename(destino)}\n\n{detalle}"), [destino]

    # 2. Comprimido normal: se extrae y, si adentro hay archivos Huffman, se descomprimen
    partes, creados, copiados = [], [], []
    with tempfile.TemporaryDirectory() as temporal:
        formato = extraer_contenedor(ruta, temporal)
        for raiz, _, archivos in os.walk(temporal):
            for a in sorted(archivos):
                origen = os.path.join(raiz, a)
                relativo = os.path.relpath(origen, temporal)
                if a.lower().endswith(EXT_HUFFMAN) and parece_huffman(origen):
                    with open(origen, "rb") as f:
                        datos, detalle = descomprimir(f.read())
                    destino = os.path.join(carpeta, os.path.dirname(relativo), nombre_original(a, datos))
                    os.makedirs(os.path.dirname(destino), exist_ok=True)
                    with open(destino, "wb") as f:
                        f.write(datos)
                    creados.append(destino)
                    partes.append(f"══════ {relativo}  →  {os.path.basename(destino)}  (Huffman) ══════\n{detalle}")
                else:
                    destino = os.path.join(carpeta, relativo)
                    os.makedirs(os.path.dirname(destino), exist_ok=True)
                    shutil.copy2(origen, destino)
                    creados.append(destino)
                    copiados.append(relativo)

    texto = (f"Formato detectado: {formato}\n"
             f"Archivos Huffman: {len(creados) - len(copiados)}   ·   Otros archivos: {len(copiados)}\n\n")
    if copiados:
        partes.append("══════ Archivos extraídos tal cual ══════\n" +
                      "\n".join("   " + c for c in copiados[:200]) +
                      (f"\n   ... y {len(copiados) - 200} más" if len(copiados) > 200 else "") + "\n")
    if not creados:
        partes.append("El archivo comprimido estaba vacío.\n")
    return texto + "\n".join(partes), creados


# ======================================================================
#                           INTERFAZ GRÁFICA
# ======================================================================
def tamano(n):
    return f"{n:,} bytes".replace(",", ".")


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Compresor Huffman")
        self.geometry("800x640")
        self.minsize(600, 470)

        self.modo = tk.StringVar(value="comprimir")
        self.archivos = []
        self.texto_entrada = tk.StringVar()
        self.ruta_salida = tk.StringVar()

        estilo = ttk.Style(self)
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"))
        estilo.configure("Accion.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        marco = ttk.Frame(self, padding=16)
        marco.pack(fill="both", expand=True)
        marco.columnconfigure(1, weight=1)

        ttk.Label(marco, text="Compresor de archivos Huffman",
                  style="Titulo.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(marco, text="Formato:  NT | Tree | BS | Zip", foreground="#555").grid(
            row=1, column=0, columnspan=3, sticky="w")

        opciones = ttk.LabelFrame(marco, text=" 1. ¿Qué quieres hacer? ", padding=10)
        opciones.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        ttk.Radiobutton(opciones, text="Comprimir (a .zip)", value="comprimir",
                        variable=self.modo, command=self.cambiar_modo).pack(side="left", padx=(0, 24))
        ttk.Radiobutton(opciones, text="Descomprimir (.zip, .pkz, .rar, .7z, ...)", value="descomprimir",
                        variable=self.modo, command=self.cambiar_modo).pack(side="left")

        self.lbl_entrada = ttk.Label(marco)
        self.lbl_entrada.grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(marco, textvariable=self.texto_entrada, state="readonly").grid(
            row=3, column=1, sticky="ew", padx=6)
        ttk.Button(marco, text="Buscar...", command=self.buscar_entrada).grid(row=3, column=2)

        self.lbl_salida = ttk.Label(marco)
        self.lbl_salida.grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(marco, textvariable=self.ruta_salida).grid(row=4, column=1, sticky="ew", padx=6)
        ttk.Button(marco, text="Cambiar...", command=self.buscar_salida).grid(row=4, column=2)

        self.btn_accion = ttk.Button(marco, style="Accion.TButton", command=self.ejecutar)
        self.btn_accion.grid(row=5, column=0, columnspan=3, sticky="ew", pady=12)

        self.lbl_resumen = ttk.Label(marco, font=("Segoe UI", 10, "bold"))
        self.lbl_resumen.grid(row=6, column=0, columnspan=3, sticky="w")

        cuadro = ttk.Frame(marco)
        cuadro.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        marco.rowconfigure(7, weight=1)
        self.texto = tk.Text(cuadro, font=("Consolas", 10), wrap="none",
                             bg="#f7f7f7", relief="solid", borderwidth=1)
        barra_y = ttk.Scrollbar(cuadro, orient="vertical", command=self.texto.yview)
        barra_x = ttk.Scrollbar(cuadro, orient="horizontal", command=self.texto.xview)
        self.texto.configure(yscrollcommand=barra_y.set, xscrollcommand=barra_x.set)
        self.texto.grid(row=0, column=0, sticky="nsew")
        barra_y.grid(row=0, column=1, sticky="ns")
        barra_x.grid(row=1, column=0, sticky="ew")
        cuadro.rowconfigure(0, weight=1)
        cuadro.columnconfigure(0, weight=1)

        self.cambiar_modo()

    # --------------------------------------------------------------
    def comprimiendo(self):
        return self.modo.get() == "comprimir"

    def salida_es_carpeta(self):
        return not self.comprimiendo() or len(self.archivos) > 1

    def actualizar_etiquetas(self):
        if self.comprimiendo():
            self.lbl_entrada.configure(text="2. Archivo(s) a comprimir:")
            self.btn_accion.configure(text="Comprimir")
        else:
            self.lbl_entrada.configure(text="2. Archivo(s) comprimido(s):")
            self.btn_accion.configure(text="Descomprimir")
        self.lbl_salida.configure(text="3. Guardar en la carpeta:" if self.salida_es_carpeta()
                                  else "3. Guardar como:")

    def cambiar_modo(self):
        self.archivos = []
        self.texto_entrada.set("")
        self.ruta_salida.set("")
        self.actualizar_etiquetas()
        self.lbl_resumen.configure(text="Selecciona con «Buscar...» para empezar.")
        self.escribir("")

    def buscar_entrada(self):
        if self.comprimiendo():
            rutas = filedialog.askopenfilenames(title="Escoge uno o varios archivos a comprimir")
        else:
            rutas = filedialog.askopenfilenames(
                title="Escoge uno o varios archivos a descomprimir",
                filetypes=[("Archivos comprimidos", EXTENSIONES), ("Todos los archivos", "*.*")])
        if not rutas:
            return
        self.archivos = list(rutas)
        if len(rutas) == 1:
            self.texto_entrada.set(rutas[0])
        else:
            self.texto_entrada.set(f"{len(rutas)} archivos: " + ", ".join(os.path.basename(r) for r in rutas))

        carpeta = os.path.dirname(rutas[0])
        if self.comprimiendo():
            self.ruta_salida.set(rutas[0] + ".zip" if len(rutas) == 1 else carpeta)   # doc.doc -> doc.doc.zip
        elif len(rutas) == 1:
            self.ruta_salida.set(quitar_extension(rutas[0]) + "_descomprimido")
        else:
            self.ruta_salida.set(os.path.join(carpeta, "descomprimidos"))
        self.actualizar_etiquetas()

    def buscar_salida(self):
        actual = self.ruta_salida.get()
        if self.salida_es_carpeta():
            ruta = filedialog.askdirectory(title="Carpeta de destino")
        else:
            ruta = filedialog.asksaveasfilename(
                title="Guardar como", defaultextension=".zip", filetypes=[("Archivo ZIP", "*.zip")],
                initialdir=os.path.dirname(actual) if actual else None,
                initialfile=os.path.basename(actual) if actual else "")
        if ruta:
            self.ruta_salida.set(ruta)

    def escribir(self, contenido):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", contenido)
        self.texto.configure(state="disabled")

    def ejecutar(self):
        salida = self.ruta_salida.get().strip()
        if not self.archivos:
            messagebox.showwarning("Falta el archivo", "Primero usa «Buscar...» para escoger el archivo.")
            return
        if not salida:
            messagebox.showwarning("Falta el destino", "Indica dónde guardar el resultado.")
            return

        archivos, comprimiendo = list(self.archivos), self.comprimiendo()

        # Destinos de la compresión: un .zip por archivo
        if comprimiendo:
            if len(archivos) == 1:
                if not salida.lower().endswith(".zip"):
                    salida += ".zip"
                    self.ruta_salida.set(salida)
                destinos = [salida]
            else:
                if os.path.isfile(salida):
                    messagebox.showerror("Destino inválido", "El destino debe ser una carpeta.")
                    return
                destinos = [os.path.join(salida, os.path.basename(a) + ".zip") for a in archivos]
            if any(os.path.abspath(a) == os.path.abspath(d) for a, d in zip(archivos, destinos)):
                messagebox.showerror("Mismo archivo", "El .zip no puede reemplazar al archivo original.")
                return
            existentes = [d for d in destinos if os.path.exists(d)]
            if existentes and not messagebox.askyesno(
                    "Reemplazar", f"Ya existe(n) {len(existentes)} archivo(s), por ejemplo:\n"
                                  f"{existentes[0]}\n\n¿Quieres reemplazarlos?"):
                return
        else:
            if os.path.isfile(salida):
                messagebox.showerror("Destino inválido", "El destino debe ser una carpeta, no un archivo.")
                return
            if os.path.isdir(salida) and os.listdir(salida) and not messagebox.askyesno(
                    "Carpeta con archivos", f"La carpeta ya tiene archivos:\n{salida}\n\n"
                    "Los que tengan el mismo nombre se reemplazarán. ¿Continuar?"):
                return

        # El trabajo va en un hilo aparte para que la ventana no se congele
        self.btn_accion.configure(state="disabled")
        self.configure(cursor="watch")
        self.lbl_resumen.configure(text="Trabajando... (con archivos grandes puede tardar un poco)")
        self.escribir("")
        resultado = {}

        def trabajo():
            actual = archivos[0]
            try:
                textos = []
                if comprimiendo:
                    total_o = total_c = 0
                    for actual, destino in zip(archivos, destinos):
                        detalle, o, c = comprimir_archivo(actual, destino)
                        total_o, total_c = total_o + o, total_c + c
                        textos.append(f"══════ {os.path.basename(actual)}  →  "
                                      f"{os.path.basename(destino)} ══════\n{detalle}")
                    resumen = (f"Comprimido: {len(archivos)} archivo(s), {tamano(total_o)}  →  "
                               f"{tamano(total_c)} ({total_c / total_o * 100:.1f} %)")
                else:
                    creados = []
                    for actual in archivos:
                        detalle, nuevos = descomprimir_archivo(actual, salida)
                        textos.append(f"########## {os.path.basename(actual)} ##########\n{detalle}")
                        creados += nuevos
                    resumen = (f"Descomprimido: {len(archivos)} archivo(s)  →  "
                               f"{len(creados)} archivo(s) en {os.path.basename(salida)}")
                    textos.append("Archivos creados:\n" + "\n".join("   " + c for c in creados[:50]) +
                                  (f"\n   ... y {len(creados) - 50} más" if len(creados) > 50 else ""))
                resultado["ok"] = (resumen, "\n".join(textos) + "\n")
            except Exception as error:
                resultado["error"] = f"{os.path.basename(actual)}:\n\n{error}"

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()

        def revisar():
            if hilo.is_alive():
                self.after(150, revisar)
                return
            self.btn_accion.configure(state="normal")
            self.configure(cursor="")
            if "error" in resultado:
                self.lbl_resumen.configure(text="Ocurrió un error.")
                messagebox.showerror("Error", resultado["error"])
                return
            resumen, detalle = resultado["ok"]
            self.lbl_resumen.configure(text=resumen)
            self.escribir(detalle)
            messagebox.showinfo("Listo", f"{resumen}\n\nUbicación:\n{salida}")

        revisar()


if __name__ == "__main__":
    Aplicacion().mainloop()
