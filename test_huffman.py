"""Pruebas de src/huffman_gui.py (solo la lógica; no abre la ventana).

Ejecutar desde la raíz del repositorio:
    python -m unittest discover -s tests -v
"""
import importlib.util
import os
import random
import sys
import tempfile
import types
import unittest
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cargar_modulo():
    """Importa huffman_gui. Si Tkinter no está instalado, lo reemplaza por un objeto vacío
    (la lógica de Huffman no lo necesita)."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        for nombre in ("tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox"):
            sys.modules[nombre] = types.ModuleType(nombre)
        sys.modules["tkinter"].Tk = object
        sys.modules["tkinter"].ttk = sys.modules["tkinter.ttk"]
        sys.modules["tkinter"].filedialog = sys.modules["tkinter.filedialog"]
        sys.modules["tkinter"].messagebox = sys.modules["tkinter.messagebox"]
    ruta = os.path.join(RAIZ, "src", "huffman_gui.py")
    spec = importlib.util.spec_from_file_location("huffman_gui", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


hg = cargar_modulo()


def referencia(datos):
    """Implementación independiente de las reglas del profesor, para comparar."""
    class N:
        def __init__(s, w, sim=None, l=None, r=None):
            s.w, s.sim, s.l, s.r = w, sim, l, r

    c = Counter(datos)
    lst = [N(f, s) for s, f in sorted(c.items(), key=lambda x: (x[1], x[0]))]
    while len(lst) > 1:
        a, b = lst.pop(0), lst.pop(0)
        p = N(a.w + b.w, None, a, b)
        i = 0
        while i < len(lst) and lst[i].w <= p.w:
            i += 1
        lst.insert(i, p)
    raiz, codigos, tree = lst[0], {}, []

    def bajar(n, pre):
        if n.sim is not None:
            codigos[n.sim] = pre or "0"
        else:
            bajar(n.l, pre + "0")
            bajar(n.r, pre + "1")

    def guardar(n):
        if n.sim is not None:
            tree.extend([1, n.sim])
        else:
            tree.extend([0, 0])
            guardar(n.l)
            guardar(n.r)

    bajar(raiz, "")
    guardar(raiz)
    nt = (len(tree) - 2) // 4
    bits = "".join(codigos[b] for b in datos)
    bs = len(bits) % 8 or 8
    bits += "0" * (-len(bits) % 8)
    zip_ = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    return bytes([nt]) + bytes(tree) + bytes([bs]) + zip_


def partes(archivo):
    nt = archivo[0]
    largo_tree = 4 * nt + 2
    return nt, list(archivo[1:1 + largo_tree]), archivo[1 + largo_tree], list(archivo[2 + largo_tree:])


class EjemplosDelTablero(unittest.TestCase):
    """Los ejemplos del tablero del profesor y los resueltos en las guías."""

    CASOS = {
        "anita patina": (5, [0, 0, 0, 0, 1, 116, 0, 0, 1, 32, 1, 112, 0, 0, 1, 97, 0, 0, 1, 105, 1, 110], 6,
                         [190, 36, 227, 120]),
        "banana": (2, [0, 0, 1, 97, 0, 0, 1, 98, 1, 110], 1, [155, 0]),
        "abracadabra": (4, [0, 0, 1, 97, 0, 0, 0, 0, 1, 99, 1, 100, 0, 0, 1, 98, 1, 114], 7, [110, 138, 220]),
        "mississippi": (3, [0, 0, 1, 115, 0, 0, 0, 0, 1, 109, 1, 112, 1, 105], 5, [153, 157, 184]),
        "casa": (2, [0, 0, 1, 97, 0, 0, 1, 99, 1, 115], 6, [152]),
        "hola mundo": (8, [0, 0, 0, 0, 0, 0, 1, 100, 1, 104, 0, 0, 1, 108, 1, 109, 0, 0, 0, 0, 1, 110, 1, 117, 0, 0,
                           1, 111, 0, 0, 1, 32, 1, 97], 8, [57, 127, 59, 6]),
    }

    def test_archivo_comprimido(self):
        for texto, esperado in self.CASOS.items():
            with self.subTest(texto=texto):
                archivo, _ = hg.comprimir(texto.encode())
                self.assertEqual(partes(archivo), esperado)

    def test_ida_y_vuelta(self):
        for texto in self.CASOS:
            with self.subTest(texto=texto):
                archivo, _ = hg.comprimir(texto.encode())
                original, _ = hg.descomprimir(archivo)
                self.assertEqual(original, texto.encode())

    def test_codigos_de_anita_patina(self):
        raiz = hg.construir_arbol(Counter(b"anita patina"))
        codigos = hg.generar_codigos(raiz)
        esperado = {97: "10", 110: "111", 105: "110", 116: "00", 32: "010", 112: "011"}
        self.assertEqual(codigos, esperado)

    def test_factor_de_anita_patina(self):
        archivo, detalle = hg.comprimir(b"anita patina")
        _, _, _, zip_ = partes(archivo)
        self.assertEqual(len(zip_), 4)                       # 30 bits -> 4 bytes
        self.assertIn("Total = 30 bits", detalle)
        self.assertIn("4/12 bytes = 33.3 %", detalle)
        self.assertEqual(len(archivo), 28)                   # 1 + 22 + 1 + 4


class Invariantes(unittest.TestCase):
    """Las sumas de control de la guía 02."""

    def test_sumas_de_control(self):
        random.seed(3)
        for _ in range(300):
            k, n = random.randint(2, 40), random.randint(2, 300)
            datos = bytes(random.choices(range(k), k=n))
            frec = Counter(datos)
            raiz = hg.construir_arbol(frec)
            codigos = hg.generar_codigos(raiz)
            self.assertEqual(raiz.frecuencia, len(datos))                       # raíz = largo del texto
            self.assertEqual(hg.contar_internos(raiz), len(frec) - 1)           # NT = hojas - 1
            bits = sum(frec[s] * len(c) for s, c in codigos.items())

            def pesos_internos(nodo):
                if nodo.es_hoja():
                    return 0
                return nodo.frecuencia + pesos_internos(nodo.izq) + pesos_internos(nodo.der)
            self.assertEqual(pesos_internos(raiz), bits)                        # suma de internos = bits

    def test_ningun_codigo_es_prefijo_de_otro(self):
        random.seed(4)
        for _ in range(100):
            datos = bytes(random.choices(range(30), weights=[random.random() ** 4 for _ in range(30)], k=200))
            codigos = list(hg.generar_codigos(hg.construir_arbol(Counter(datos))).values())
            for a in codigos:
                for b in codigos:
                    if a is not b:
                        self.assertFalse(b.startswith(a) and a != b)


class IdaYVuelta(unittest.TestCase):
    def comprobar(self, datos):
        archivo, _ = hg.comprimir(datos)
        original, _ = hg.descomprimir(archivo)
        self.assertEqual(original, datos)
        nt, tree, bs, zip_ = partes(archivo)
        self.assertTrue(1 <= bs <= 8)
        frec = Counter(datos)
        codigos = hg.generar_codigos(hg.construir_arbol(frec))
        bits_totales = sum(frec[s] * len(c) for s, c in codigos.items())
        self.assertEqual((len(zip_) - 1) * 8 + bs, bits_totales)

    def test_casos_limite(self):
        casos = {
            "un solo byte": b"a",
            "un solo símbolo x1000": b"z" * 1000,
            "un solo símbolo x8": b"q" * 8,
            "dos símbolos": b"ab" * 500,
            "ceros": bytes(5000),
            "los 256 valores": bytes(range(256)) * 3,
            "256 valores, uno de cada uno": bytes(range(256)),
            "ñ y tildes": "La niña comió piñón. ¿Qué día es? áéíóú".encode(),
            "con \\r\\n": b"linea1\r\nlinea2\r\n",
            "anita patina con salto": b"anita patina\n",
        }
        for nombre, datos in casos.items():
            with self.subTest(nombre):
                self.comprobar(datos)

    def test_arbol_muy_profundo(self):
        fib = [1, 1]
        while len(fib) < 30:
            fib.append(fib[-1] + fib[-2])
        datos = b"".join(bytes([i]) * f for i, f in enumerate(fib[:24]))
        self.comprobar(datos)

    def test_textos_cortos(self):
        random.seed(5)
        for n in range(1, 60):
            self.comprobar(bytes(random.choice(b"abcdefgh") for _ in range(n)))

    def test_aleatorios_contra_la_referencia(self):
        random.seed(7)
        for _ in range(500):
            k, n = random.randint(1, 256), random.randint(1, 400)
            pesos = [random.random() ** random.choice((1, 3, 8)) for _ in range(k)]
            datos = bytes(random.choices(range(k), weights=pesos, k=n))
            archivo, _ = hg.comprimir(datos)
            self.assertEqual(archivo, referencia(datos))
            self.assertEqual(hg.descomprimir(archivo)[0], datos)

    def test_varias_tandas(self):
        """Más de 65.536 bytes: los bits sobrantes se arrastran entre tandas."""
        random.seed(8)
        datos = bytes(random.choices(range(20), weights=[random.random() ** 3 for _ in range(20)], k=300_000))
        archivo, _ = hg.comprimir(datos)
        self.assertEqual(archivo, referencia(datos))
        self.assertEqual(hg.descomprimir(archivo)[0], datos)

    def test_archivo_vacio(self):
        with self.assertRaises(ValueError):
            hg.comprimir(b"")


class GuiaDelCodigo(unittest.TestCase):
    """Comprueba lo que explica docs/04-guia-del-codigo.md."""

    def test_entrada_de_la_tabla_de_banana(self):
        archivo, _ = hg.comprimir(b"banana")
        self.assertEqual(list(archivo), [2, 0, 0, 1, 97, 0, 0, 1, 98, 1, 110, 1, 155, 0])
        nt, raiz, bs, inicio = hg.leer_cabecera(archivo)
        self.assertEqual((nt, bs, inicio), (2, 1, 12))
        tabla, internos = hg.tabla_de_decodificacion(raiz)
        self.assertEqual(len(internos), 2)
        self.assertEqual(tabla[0 + 155], (0, b"banan"))

    def test_leer_arbol_devuelve_la_posicion_siguiente(self):
        datos = bytes([0, 0, 1, 97, 0, 0, 1, 98, 1, 110, 1])
        raiz, pos = hg.leer_arbol(datos, 0)
        self.assertEqual(pos, 10)
        self.assertEqual(hg.contar_internos(raiz), 2)

    def test_variante_con_nodo_interno_de_un_byte(self):
        # Mismo árbol de "banana" con el nodo interno escrito como un solo 0
        archivo = bytes([2, 0, 1, 97, 0, 1, 98, 1, 110, 1, 155, 0])
        self.assertEqual(hg.descomprimir(archivo)[0], b"banana")

    def test_un_solo_simbolo(self):
        archivo, _ = hg.comprimir(b"aaaa")
        self.assertEqual(list(archivo), [0, 1, 97, 4, 0])     # NT=0, hoja a, BS=4, ZIP=0000 + relleno
        self.assertEqual(hg.descomprimir(archivo)[0], b"aaaa")

    def test_nombre_original(self):
        self.assertEqual(hg.nombre_original("doc.doc.zip", b"x"), "doc.doc")
        self.assertEqual(hg.nombre_original("mensaje.zip", b"hola"), "mensaje.txt")
        self.assertEqual(hg.nombre_original("foto.png.zip", b"x"), "foto.png")

    def test_detectar_extension(self):
        self.assertEqual(hg.detectar_extension(b"%PDF-1.7"), "pdf")
        self.assertEqual(hg.detectar_extension(b"\x89PNG\r\n"), "png")
        self.assertEqual(hg.detectar_extension("texto ñ".encode()), "txt")
        self.assertEqual(hg.detectar_extension(b"\xff\xfe\xfd\x80"), "bin")


class Archivos(unittest.TestCase):
    def test_comprimir_y_descomprimir_archivos(self):
        random.seed(11)
        originales = {
            "nota.txt": "anita patina\n".encode(),
            "datos.bin": bytes(random.getrandbits(8) for _ in range(20000)),
            "imagen.png": b"\x89PNG\r\n\x1a\n" + bytes(random.getrandbits(8) for _ in range(2000)),
            "doc.tar.gz": bytes(random.getrandbits(8) for _ in range(500)),
        }
        with tempfile.TemporaryDirectory() as t:
            for nombre, datos in originales.items():
                with self.subTest(nombre):
                    ruta = os.path.join(t, nombre)
                    with open(ruta, "wb") as f:
                        f.write(datos)
                    comprimido = ruta + ".zip"
                    hg.comprimir_archivo(ruta, comprimido)
                    self.assertTrue(hg.parece_huffman(comprimido))
                    self.assertFalse(hg.parece_huffman(ruta))
                    _, creados = hg.descomprimir_archivo(comprimido, os.path.join(t, "salida_" + nombre))
                    self.assertEqual([os.path.basename(c) for c in creados], [nombre])
                    with open(creados[0], "rb") as f:
                        self.assertEqual(f.read(), datos)

    def test_sin_falsos_positivos_en_archivos_aleatorios(self):
        random.seed(13)
        with tempfile.TemporaryDirectory() as t:
            ruta = os.path.join(t, "r.bin")
            falsos = 0
            for _ in range(3000):
                with open(ruta, "wb") as f:
                    f.write(bytes(random.getrandbits(8) for _ in range(random.randint(2, 120))))
                falsos += hg.parece_huffman(ruta)
            self.assertEqual(falsos, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
