"""
OxigenScript — Recolector de errores
"""


class Error:
    """Un error individual"""

    def __init__(self, tipo, descripcion, linea, columna, fragmento=''):
        self.tipo = tipo                  # 'Léxico' | 'Sintáctico' | 'Semántico'
        self.descripcion = descripcion
        self.linea = linea
        self.columna = columna
        self.fragmento = fragmento        # el lexema donde se detectó

    def __str__(self):
        # Formato
        #   [Tipo de Error] Línea <línea>, Columna <columna>
        return (f"[Error {self.tipo}] Línea {self.linea}, Columna {self.columna}\n"
                f"{self.descripcion}")

    def como_dict(self):
        """Pasamos a json"""
        return {
            'tipo': self.tipo,
            'descripcion': self.descripcion,
            'linea': self.linea,
            'columna': self.columna,
            'fragmento': self.fragmento,
        }


class ListaErrores:
    """Colector compartido por todas las fases"""

    def __init__(self):
        self._lista = []

    def limpiar(self):
        self._lista = []

    def agregar(self, tipo, descripcion, linea, columna, fragmento=''):
        self._lista.append(Error(tipo, descripcion, linea, columna, fragmento))

    # Atajos para no repetir el string del tipo en cada llamada.
    def lexico(self, descripcion, linea, columna, fragmento=''):
        self.agregar('Léxico', descripcion, linea, columna, fragmento)

    def sintactico(self, descripcion, linea, columna, fragmento=''):
        self.agregar('Sintáctico', descripcion, linea, columna, fragmento)

    def semantico(self, descripcion, linea, columna, fragmento=''):
        self.agregar('Semántico', descripcion, linea, columna, fragmento)

    def hay_errores(self):
        return len(self._lista) > 0

    def ordenados(self):
        """Los errores salen en orden de aparición en el archivo.
        """
        return sorted(self._lista, key=lambda e: (e.linea, e.columna))

    def __len__(self):
        return len(self._lista)

    def __iter__(self):
        return iter(self.ordenados())


#intancia compartida
errores = ListaErrores()
