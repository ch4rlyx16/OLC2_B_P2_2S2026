class Generador:

    """Juntamos el texto del ensamblador que va produciendo el compilador """
    def __init__(self):
        self.funciones = {}
        self.retorno = None
        self.bucles = []
        self.instrucciones = []
        self.datos = []
        self.contador = 0
        self.cadenas = {}
        self.entorno = None
        self.simbolos = []

    def emitir(self, instruccion, comentarios = ''):
        linea= '   ' + instruccion
        if comentarios: 
            linea = linea + '    //' + comentarios
        self.instrucciones.append(linea)

    def acceso(self, instruccion, registro, offset, comentarios=''):
        """Emite un ldr/str contra [x29, #offset], aunque el offset sea grande.

        ARM64 solo admite desplazamientos de -256 a 255 en esta forma. Cuando
        el marco crece mas que eso (pasa con los arreglos) hay que calcular la
        direccion en un registro auxiliar primero.
        """
        if -256 <= offset <= 255:
            self.emitir(f'{instruccion} {registro}, [x29, #{offset}]',
                        comentarios)
        else:
            self.emitir(f'sub x9, x29, #{-offset}',
                        'marco grande: calcular la direccion aparte')
            self.emitir(f'{instruccion} {registro}, [x9]', comentarios)

    def etiqueta(self, nombre):
        linea = nombre + ':'
        self.instrucciones.append(linea)

    def comentario(self, texto):
        self.instrucciones.append('    // ' + texto)

    def marcador(self, comentarios=''):
        """Reserva un renglón vacío y devuelve su posición."""
        self.instrucciones.append('')
        if comentarios:
            self.instrucciones[-1] = '    // (pendiente) ' + comentarios
        return len(self.instrucciones) - 1

    def parchar(self, indice, instruccion, comentarios=''):
        """Rellena un renglón que se había dejado pendiente."""
        linea = '   ' + instruccion
        if comentarios:
            linea = linea + '    //' + comentarios
        self.instrucciones[indice] = linea

    def nueva_etiqueta(self, prefijo='L'):
        nombre = prefijo + str(self.contador)
        self.contador = self.contador + 1
        return nombre
    
    def bucle(self, nombre=None):
        """Devuelve el bucle al que apunta un break/continue, o None."""
        if nombre is None:
            return self.bucles[-1] if self.bucles else None
        for bucle in reversed(self.bucles):
            if bucle['nombre'] == nombre:
                return bucle
        return None
    
    def cadena(self, texto):
        if texto in self.cadenas:
            return self.cadenas[texto]

        nombre = 'str' + str(len(self.cadenas))
        self.datos.append(nombre + ':    .asciz "' + self._escapar(texto) + '"')
        self.cadenas[texto] = nombre
        return nombre

    def _escapar(self, texto):
        seguro = texto.replace('\\', '\\\\')
        seguro = seguro.replace('"', '\\"')
        seguro = seguro.replace('\n', '\\n')
        return seguro

    def codigo(self):
        partes = []

        if self.datos:
            partes.append('.data')
            partes.extend(self.datos)
            partes.append('')

        partes.append('.text')
        partes.append('.global _start')
        partes.append('')
        partes.extend(self.instrucciones)

        return '\n'.join(partes)
