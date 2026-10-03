class Generador:

    """Juntamos el texto del ensamblador que va produciendo el compilador """
    def __init__(self):
        self.instrucciones = []
        self.datos = []
        self.contador = 0
        self.cadenas = {}

    def emitir(self, instruccion, comentarios = ''):
        linea= '   ' + instruccion
        if comentarios: 
            linea = linea + '    //' + comentarios
        self.instrucciones.append(linea)

    def etiqueta(self, nombre):
        linea = nombre + ':'
        self.instrucciones.append(linea)

    def comentario(self, texto):
        self.instrucciones.append('    // ' + texto)

    def nueva_etiqueta(self, prefijo='L'):
        nombre = prefijo + str(self.contador)
        self.contador = self.contador + 1
        return nombre
    
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