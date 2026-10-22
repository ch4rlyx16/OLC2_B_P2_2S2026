// ============================================================================
//  runtime.s -- Rutinas de apoyo de OxigenNative
//  io.s es del laboratorio y no se toca; esto es lo nuestro.
//
//    alloc          x0 = bytes     -> x0 = direccion reservada
//    to_upper       x1 = cadena    -> x0 = cadena nueva en MAYUSCULAS
//    to_lower       x1 = cadena    -> x0 = cadena nueva en minusculas
//    array_reverse  x1 = puntero   -> x0 = el mismo puntero, invertido
// ============================================================================

.bss
.align 4
monton:         .skip 65536

.data
.align 3
monton_libre:   .quad monton

.text
.global alloc
.global to_upper
.global to_lower
.global array_reverse

// ---------------------------------------------------------------------------
//  alloc(x0 = bytes) -> x0 = direccion
//  Reserva avanzando un puntero. Nunca libera: los programas son cortos.
// ---------------------------------------------------------------------------
alloc:
    adrp    x9, monton_libre
    add     x9, x9, :lo12:monton_libre
    ldr     x10, [x9]
    add     x11, x10, x0
    add     x11, x11, #15
    and     x11, x11, #-16
    str     x11, [x9]
    mov     x0, x10
    ret

// ---------------------------------------------------------------------------
//  to_upper(x1 = cadena terminada en 0) -> x0 = cadena nueva
// ---------------------------------------------------------------------------
to_upper:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    str     x19, [sp, #-16]!
    mov     x19, x1

    bl      strlen
    add     x0, x2, #1
    bl      alloc

    mov     x9, x19
    mov     x10, x0
up_loop:
    ldrb    w11, [x9], #1
    cmp     w11, #97
    b.lt    up_guarda
    cmp     w11, #122
    b.gt    up_guarda
    sub     w11, w11, #32
up_guarda:
    strb    w11, [x10], #1
    cbnz    w11, up_loop

    ldr     x19, [sp], #16
    ldp     x29, x30, [sp], #16
    ret

// ---------------------------------------------------------------------------
//  to_lower(x1 = cadena terminada en 0) -> x0 = cadena nueva
// ---------------------------------------------------------------------------
to_lower:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    str     x19, [sp, #-16]!
    mov     x19, x1

    bl      strlen
    add     x0, x2, #1
    bl      alloc

    mov     x9, x19
    mov     x10, x0
low_loop:
    ldrb    w11, [x9], #1
    cmp     w11, #65
    b.lt    low_guarda
    cmp     w11, #90
    b.gt    low_guarda
    add     w11, w11, #32
low_guarda:
    strb    w11, [x10], #1
    cbnz    w11, low_loop

    ldr     x19, [sp], #16
    ldp     x29, x30, [sp], #16
    ret

// ---------------------------------------------------------------------------
//  array_reverse(x1 = puntero al elemento 0) -> x0 = el mismo puntero
//  La longitud vive en la cabecera, en [x1, #-8].
// ---------------------------------------------------------------------------
array_reverse:
    mov     x0, x1
    ldr     x2, [x1, #-8]
    cmp     x2, #2
    b.lt    rev_fin
    mov     x3, x1
    sub     x4, x2, #1
    add     x4, x1, x4, lsl #3
rev_loop:
    cmp     x3, x4
    b.hs    rev_fin
    ldr     x5, [x3]
    ldr     x6, [x4]
    str     x6, [x3]
    str     x5, [x4]
    add     x3, x3, #8
    sub     x4, x4, #8
    b       rev_loop
rev_fin:
    ret
