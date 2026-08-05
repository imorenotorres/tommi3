"""
Banco de palabras para ejercicios de errores fonológicos.

Cada palabra se describe con propiedades que permiten seleccionar
ejercicios apropiados para practicar errores estructurales (sílaba/palabra)
o errores sistémicos (fonema) por separado.

Propiedades:
  - num_silabas: número de sílabas
  - num_codas: número de sílabas con coda
  - num_ataques_complejos: número de ataques con 2+ consonantes
  - num_afi_divergentes: número de consonantes cuyo símbolo AFI no
    coincide con la grafía española (g→/x/, h→/Ø/, j→/x/, ll→/ʝ/,
    ñ→/ɲ/, qu→/k/, r→/ɾ/ o /r/, rr→/r/, v→/b/, x→/ks/, y→/ʝ/, z→/θ/)
"""

from .silaba import parsear_silabas, Palabra


# Grafías españolas cuyo símbolo AFI difiere del carácter ortográfico
# El alumno debe saber que estas letras no se transcriben "como suenan"
_GRAFIAS_DIVERGENTES = {
    'g',   # g ante e/i = /x/, g ante a/o/u = /g/
    'h',   # muda
    'j',   # /x/
    'c',   # c ante e/i = /θ/, c ante a/o/u = /k/
    'z',   # /θ/
    'v',   # /b/
    'x',   # /ks/ o /s/
    'y',   # /ʝ/ (consonante) o /i/ (vocal)
    'ñ',   # /ɲ/
    'q',   # /k/ (en qu)
    'r',   # /ɾ/ o /r/ según posición
}

# Dígrafos cuyo AFI difiere
_DIGRAFOS_DIVERGENTES = {
    'll',  # /ʝ/
    'rr',  # /r/
    'ch',  # /tʃ/
    'gu',  # /g/ ante e/i (la u no suena)
    'qu',  # /k/
}


def _contar_afi_divergentes(ortografia: str) -> int:
    """
    Cuenta cuántas consonantes en la ortografía tienen un símbolo AFI
    que no coincide con la grafía española.
    """
    ort = ortografia.lower()
    count = 0
    i = 0
    ya_contados = set()

    while i < len(ort):
        # Comprobar dígrafos primero
        matched_digrafo = False
        if i + 1 < len(ort):
            digrafo = ort[i:i+2]
            if digrafo in _DIGRAFOS_DIVERGENTES:
                count += 1
                i += 2
                matched_digrafo = True

        if not matched_digrafo:
            if ort[i] in _GRAFIAS_DIVERGENTES:
                count += 1
            i += 1

    return count


def _analizar_palabra(ortografia: str, transcripcion: str) -> dict:
    """Analiza una palabra y devuelve sus propiedades."""
    palabra = parsear_silabas(transcripcion)

    num_codas = sum(1 for s in palabra.silabas if s.tiene_coda)
    num_ataques_complejos = sum(1 for s in palabra.silabas if s.ataque_complejo)
    num_afi = _contar_afi_divergentes(ortografia)

    return {
        'ortografia': ortografia,
        'transcripcion': transcripcion,
        'num_silabas': palabra.num_silabas,
        'num_codas': num_codas,
        'num_ataques_complejos': num_ataques_complejos,
        'num_afi_divergentes': num_afi,
    }


# ═══════════════════════════════════════════════════════════════════════
# BANCO DE PALABRAS
# ═══════════════════════════════════════════════════════════════════════

_PALABRAS_RAW = [
    # ── Bisílabas ──────────────────────────────────────────────────────
    ("casa", "ˈka.sa"),
    ("mesa", "ˈme.sa"),
    ("niña", "ˈni.ɲa"),
    ("boca", "ˈbo.ka"),
    ("dedo", "ˈde.do"),
    ("gato", "ˈga.to"),
    ("luna", "ˈlu.na"),
    ("pato", "ˈpa.to"),
    ("taza", "ˈta.θa"),
    ("vaso", "ˈba.so"),
    ("nube", "ˈnu.be"),
    ("peso", "ˈpe.so"),
    ("foca", "ˈfo.ka"),
    ("mano", "ˈma.no"),
    ("cama", "ˈka.ma"),
    ("chilla", "ˈtʃi.ʝa"),
    ("calle", "ˈka.ʝe"),
    ("mocho", "ˈmo.tʃo"),
    ("jefe", "ˈxe.fe"),
    ("rojo", "ˈro.xo"),
    ("carro", "ˈka.ro"),
    ("para", "ˈpa.ɾa"),
    ("cero", "ˈθe.ɾo"),
    ("llave", "ˈʝa.be"),
    ("pollo", "ˈpo.ʝo"),
    ("pan", "ˈpan"),
    ("sol", "ˈsol"),
    ("mar", "ˈmaɾ"),
    ("luz", "ˈluθ"),

    # ── Trisílabas ─────────────────────────────────────────────────────
    ("zapato", "θa.'pa.to"),
    ("maleta", "ma.'le.ta"),
    ("camisa", "ka.'mi.sa"),
    ("cabeza", "ka.'be.θa"),
    ("madera", "ma.'de.ɾa"),
    ("cocina", "ko.'θi.na"),
    ("cerebro", "θe.'ɾe.bɾo"),
    ("croqueta", "kɾo.'ke.ta"),
    ("machete", "ma.'tʃe.te"),
    ("cuchillo", "ku.'tʃi.ʝo"),
    ("gallina", "ga.'ʝi.na"),
    ("tobillo", "to.'bi.ʝo"),
    ("guitarra", "gi.'ta.ra"),
    ("cigarra", "θi.'ga.ra"),
    ("pizarra", "pi.'θa.ra"),
    ("jirafa", "xi.'ɾa.fa"),
    ("tijera", "ti.'xe.ɾa"),
    ("mochila", "mo.'tʃi.la"),
    ("montaña", "mon.'ta.ɲa"),
    ("cigüeña", "θi.'gue.ɲa"),
    ("árbol", "ˈaɾ.bol"),
    ("cartel", "kaɾ.'tel"),
    ("cantar", "kan.'taɾ"),
    ("comprar", "kom.'pɾaɾ"),

    # ── Tetrasílabas ───────────────────────────────────────────────────
    ("mariposa", "ma.ɾi.'po.sa"),
    ("magdalena", "mag.da.'le.na"),
    ("chocolate", "tʃo.ko.'la.te"),
    ("bicicleta", "bi.θi.'kle.ta"),
    ("elefante", "e.le.'fan.te"),
    ("zapatilla", "θa.pa.'ti.ʝa"),
    ("bestiario", "bes.'tia.ɾio"),
    ("estudiante", "es.tu.'dian.te"),

    # ── 5+ sílabas ────────────────────────────────────────────────────
    ("superficial", "su.peɾ.fi.'θial"),
    ("murciélago", "muɾ.'θie.la.go"),
    ("celebración", "θe.le.bɾa.'θion"),
    ("puertecilla", "pueɾ.te.'θi.ʝa"),
    ("refrigerador", "re.fɾi.xe.ɾa.'doɾ"),
    ("extraordinario", "es.tɾa.oɾ.di.'na.ɾio"),
    ("multiplicación", "mul.ti.pli.ka.'θion"),

    # ── Ataques complejos adicionales ──────────────────────────────────
    ("tren", "ˈtɾen"),
    ("plan", "ˈplan"),
    ("blusa", "ˈblu.sa"),
    ("grupo", "ˈgɾu.po"),
    ("crema", "ˈkɾe.ma"),
    ("plato", "ˈpla.to"),
    ("fresa", "ˈfɾe.sa"),
    ("primo", "ˈpɾi.mo"),
    ("brazo", "ˈbɾa.θo"),

    # ── Palabras complejas (varias propiedades simultáneas) ─────────────
    # Combinan: codas + ataques complejos + diptongos + AFI divergentes

    # Codas + ataques complejos
    ("cuadros", "ˈkua.dɾos"),              # diptongo + at.complejo + coda
    ("ciempiés", "θiem.'pies"),            # diptongo + coda + AFI(c→θ)
    ("construcción", "kons.tɾuk.'θion"),   # 2 codas + at.complejo + diptongo + AFI(c→θ, cc→kθ)
    ("instrumento", "ins.tɾu.'men.to"),    # 2 codas + at.complejo
    ("transportar", "tɾans.poɾ.'taɾ"),    # 2 codas + at.complejo
    ("destrozo", "des.'tɾo.θo"),           # coda + at.complejo + AFI(z→θ)
    ("exclamar", "es.kla.'maɾ"),          # 2 codas + at.complejo

    # Codas + diptongos + AFI divergentes
    ("representación", "re.pɾe.sen.ta.'θion"),  # coda + at.complejo + diptongo + AFI(c→θ)
    ("investigación", "im.bes.ti.ga.'θion"),    # 2 codas + diptongo + AFI(v→b, c→θ)
    ("circunstancia", "θiɾ.kuns.'tan.θia"),     # 3 codas + diptongo + AFI(c→θ)
    ("interpretación", "in.teɾ.pɾe.ta.'θion"),  # 2 codas + at.complejo + diptongo + AFI(c→θ)

    # Varias codas
    ("perspectiva", "peɾs.pek.'ti.ba"),    # 3 codas + AFI(v→b)
    ("obstáculo", "obs.'ta.ku.lo"),        # 2 codas
    ("inspector", "ins.pek.'toɾ"),         # 3 codas

    # Ataques complejos múltiples
    ("problema", "pɾo.'ble.ma"),           # 2 at.complejos
    ("proclamar", "pɾo.kla.'maɾ"),         # 2 at.complejos + coda
    ("estructura", "es.tɾuk.'tu.ɾa"),      # at.complejo + coda

    # Diptongos + AFI divergentes
    ("huevo", "ˈue.bo"),                   # diptongo + AFI(h→Ø, v→b)
    ("hielo", "ˈʝe.lo"),                   # hie- inicial → /ʝ/ + AFI(h→ʝ)
    ("hierba", "ˈʝeɾ.ba"),                 # hie- inicial → /ʝ/ + coda + AFI(h→ʝ, v→b)
    ("hierro", "ˈʝe.ro"),                  # hie- inicial → /ʝ/ + AFI(h→ʝ, rr→r)
    ("hiena", "ˈʝe.na"),                   # hie- inicial → /ʝ/ + AFI(h→ʝ)
    ("huérfano", "ˈueɾ.fa.no"),            # diptongo + coda + AFI(h→Ø)
    ("viernes", "ˈbieɾ.nes"),              # diptongo + 2 codas + AFI(v→b)
    ("aunque", "ˈaun.ke"),                 # diptongo + coda + AFI(qu→k)
    ("siguiente", "si.'gien.te"),          # diptongo + coda + AFI(gu→g)

    # Esdrújulas complejas
    ("helicóptero", "e.li.'kop.te.ɾo"),   # coda + AFI(h→Ø)
    ("crepúsculo", "kɾe.'pus.ku.lo"),      # at.complejo + coda
    ("espectáculo", "es.pek.'ta.ku.lo"),   # 2 codas

    # Combinaciones extremas
    ("transcripción", "tɾans.kɾip.'θion"), # 3 codas + 2 at.complejos + diptongo + AFI(c→θ)
    ("extranjero", "es.tɾan.'xe.ɾo"),     # 2 codas + at.complejo + AFI(x→ks, j→x)
    ("estrechez", "es.tɾe.'θeθ"),          # coda + at.complejo + AFI(z→θ)
    ("quirófano", "ki.'ɾo.fa.no"),         # AFI(qu→k)
    ("vergüenza", "beɾ.'guen.θa"),         # coda + diptongo + AFI(v→b, g→g, z→θ)

    # ── Diptongos adicionales ──────────────────────────────────────────
    ("tiene", "ˈtie.ne"),
    ("bueno", "ˈbue.no"),
    ("fuego", "ˈfue.go"),
    ("siete", "ˈsie.te"),
    ("nuevo", "ˈnue.bo"),
    ("cielo", "ˈθie.lo"),
    ("puerta", "ˈpueɾ.ta"),
    ("piedra", "ˈpie.dɾa"),

    # ═══════════════════════════════════════════════════════════════════
    # CAMPOS SEMÁNTICOS
    # ═══════════════════════════════════════════════════════════════════

    # ── Profesiones y ciencias ────────────────────────────────────────
    ("logopedia", "lo.go.'pe.dia"),
    ("cirugía", "θi.ɾu.'xi.a"),
    ("cirujano", "θi.ɾu.'xa.no"),
    ("oftalmología", "of.tal.mo.lo.'xi.a"),
    ("otorrino", "o.to.'ri.no"),
    ("otorrinolaringología", "o.to.ri.no.la.ɾin.go.lo.'xi.a"),
    ("psiquiatra", "si.'kia.tɾa"),
    ("psicólogo", "si.'ko.lo.go"),
    ("psiquiatría", "si.kia.'tɾi.a"),

    # ── Colores ───────────────────────────────────────────────────────
    ("verde", "ˈbeɾ.de"),
    ("negro", "ˈne.gɾo"),
    ("blanco", "ˈblan.ko"),
    ("amarillo", "a.ma.'ɾi.ʝo"),
    ("rojo", "ˈro.xo"),
    ("fucsia", "ˈfuk.sia"),
    ("gris", "ˈgɾis"),

    # ── Partes del cuerpo ─────────────────────────────────────────────
    ("cabeza", "ka.'be.θa"),
    ("manos", "ˈma.nos"),
    ("pies", "ˈpies"),
    ("labios", "ˈla.bios"),
    ("nariz", "na.'ɾiθ"),
    ("ojos", "ˈo.xos"),
    ("pelo", "ˈpe.lo"),
    ("muslo", "ˈmus.lo"),
    ("rodilla", "ro.'di.ʝa"),

    # ── Partes de la casa ─────────────────────────────────────────────
    ("cocina", "ko.'θi.na"),
    ("dormitorio", "doɾ.mi.'to.ɾio"),
    ("salón", "sa.'lon"),

    # ── Utensilios de cocina ──────────────────────────────────────────
    ("cuchillo", "ku.'tʃi.ʝo"),
    ("tenedor", "te.ne.'doɾ"),
    ("cuchara", "ku.'tʃa.ɾa"),
    ("vaso", "ˈba.so"),
    ("plato", "ˈpla.to"),
    ("horno", "ˈoɾ.no"),
    ("tostadora", "tos.ta.'do.ɾa"),
    ("cafetera", "ka.fe.'te.ɾa"),

    # ── Electrodomésticos ─────────────────────────────────────────────
    ("lavavajillas", "la.ba.ba.'xi.ʝas"),
    ("lavaplatos", "la.ba.'pla.tos"),
    ("lavadora", "la.ba.'do.ɾa"),
    ("batidora", "ba.ti.'do.ɾa"),

    # ── Ciudades de Andalucía ─────────────────────────────────────────
    ("málaga", "ˈma.la.ga"),
    ("sevilla", "se.'bi.ʝa"),
    ("cádiz", "ˈka.diθ"),
    ("granada", "gɾa.'na.da"),
    ("jaén", "xa.'en"),
    ("huelva", "ˈuel.ba"),
    ("almería", "al.me.'ɾi.a"),

    # ── Provincia de Málaga ───────────────────────────────────────────
    ("ronda", "ˈron.da"),
    ("marbella", "maɾ.'be.ʝa"),
    ("antequera", "an.te.'ke.ɾa"),
    ("alhaurín", "a.lau.'ɾin"),
    ("benahavís", "be.na.a.'bis"),
    ("canillas", "ka.'ni.ʝas"),

    # ── Ríos de España ────────────────────────────────────────────────
    ("guadalquivir", "gua.dal.ki.'biɾ"),
    ("guadiaro", "gua.'dia.ɾo"),
    ("guadalmedina", "gua.dal.me.'di.na"),
    ("tajo", "ˈta.xo"),
    ("ebro", "ˈe.bɾo"),
    ("miño", "ˈmi.ɲo"),
    ("sil", "ˈsil"),

    # ── Cordilleras y montañas ────────────────────────────────────────
    ("pirineos", "pi.ɾi.'ne.os"),
    ("andes", "ˈan.des"),
    ("himalaya", "i.ma.'la.ʝa"),
    ("aneto", "a.'ne.to"),
    ("mulhacén", "mu.la.'θen"),

    # ── Patologías del habla ──────────────────────────────────────────
    ("afasia", "a.'fa.sia"),
    ("dislalia", "dis.'la.lia"),
    ("disfemia", "dis.'fe.mia"),
    ("disartria", "di.'saɾ.tɾia"),

    # ═══════════════════════════════════════════════════════════════════
    # CAMPOS SEMÁNTICOS (ampliación)
    # ═══════════════════════════════════════════════════════════════════

    # ── Frutas y alimentos ────────────────────────────────────────────
    ("manzana", "man.'θa.na"),
    ("naranja", "na.'ɾan.xa"),
    ("plátano", "ˈpla.ta.no"),
    ("limón", "li.'mon"),
    ("sandía", "san.'di.a"),
    ("melón", "me.'lon"),
    ("cereza", "θe.'ɾe.θa"),
    ("uva", "ˈu.ba"),
    ("pera", "ˈpe.ɾa"),
    ("piña", "ˈpi.ɲa"),
    ("ciruela", "θi.'ɾue.la"),
    ("higo", "ˈi.go"),
    ("frambuesa", "fɾam.'bue.sa"),
    ("mora", "ˈmo.ɾa"),
    ("aguacate", "a.gua.'ka.te"),
    ("mango", "ˈman.go"),
    ("tomate", "to.'ma.te"),
    ("lechuga", "le.'tʃu.ga"),
    ("cebolla", "θe.'bo.ʝa"),
    ("ajo", "ˈa.xo"),
    ("patata", "pa.'ta.ta"),
    ("zanahoria", "θa.na.'o.ɾia"),
    ("pepino", "pe.'pi.no"),
    ("pimiento", "pi.'mien.to"),
    ("calabaza", "ka.la.'ba.θa"),
    ("apio", "ˈa.pio"),
    ("berenjena", "be.ɾen.'xe.na"),
    ("alcachofa", "al.ka.'tʃo.fa"),
    ("guisante", "gi.'san.te"),
    ("lenteja", "len.'te.xa"),
    ("garbanzo", "gaɾ.'ban.θo"),
    ("arroz", "a.'roθ"),
    ("pasta", "ˈpas.ta"),
    ("leche", "ˈle.tʃe"),
    ("queso", "ˈke.so"),
    ("mantequilla", "man.te.'ki.ʝa"),
    ("huevo", "ˈue.bo"),
    ("ternera", "teɾ.'ne.ɾa"),
    ("pescado", "pes.'ka.do"),
    ("merluza", "meɾ.'lu.θa"),
    ("galleta", "ga.'ʝe.ta"),
    ("tarta", "ˈtaɾ.ta"),
    ("bizcocho", "biθ.'ko.tʃo"),
    ("churro", "ˈtʃu.ro"),
    ("aceite", "a.'θei.te"),
    ("vinagre", "bi.'na.gɾe"),
    ("azúcar", "a.'θu.kaɾ"),
    ("harina", "a.'ɾi.na"),

    # ── Nombres de persona ────────────────────────────────────────────
    ("pedro", "ˈpe.dɾo"),
    ("maría", "ma.'ɾi.a"),
    ("antonio", "an.'to.nio"),
    ("carmen", "ˈkaɾ.men"),
    ("francisco", "fɾan.'θis.ko"),
    ("manuel", "ma.'nuel"),
    ("josé", "xo.'se"),
    ("teresa", "te.'ɾe.sa"),
    ("juan", "ˈxuan"),
    ("miguel", "mi.'gel"),
    ("lucía", "lu.'θi.a"),
    ("ángel", "ˈan.xel"),
    ("isabel", "i.sa.'bel"),
    ("pablo", "ˈpa.blo"),
    ("laura", "ˈlau.ɾa"),
    ("sergio", "ˈseɾ.xio"),
    ("alejandro", "a.le.'xan.dɾo"),
    ("patricia", "pa.'tɾi.θia"),
    ("carlos", "ˈkaɾ.los"),
    ("silvia", "ˈsil.bia"),
    ("daniel", "da.'niel"),
    ("natalia", "na.'ta.lia"),
    ("david", "da.'bid"),
    ("andrea", "an.'dɾe.a"),
    ("jorge", "ˈxoɾ.xe"),
    ("paula", "ˈpau.la"),
    ("diego", "ˈdie.go"),
    ("sofía", "so.'fi.a"),
    ("enrique", "en.'ri.ke"),
    ("beatriz", "be.a.'tɾiθ"),
    ("mónica", "ˈmo.ni.ka"),
    ("ignacio", "ig.'na.θio"),
    ("raquel", "ra.'kel"),
    ("guillermo", "gi.'ʝeɾ.mo"),
    ("verónica", "be.'ɾo.ni.ka"),

    # ── Países de América ─────────────────────────────────────────────
    ("argentina", "aɾ.xen.'ti.na"),
    ("bolivia", "bo.'li.bia"),
    ("brasil", "bɾa.'sil"),
    ("chile", "ˈtʃi.le"),
    ("colombia", "ko.'lom.bia"),
    ("cuba", "ˈku.ba"),
    ("ecuador", "e.kua.'doɾ"),
    ("guatemala", "gua.te.'ma.la"),
    ("honduras", "on.'du.ɾas"),
    ("nicaragua", "ni.ka.'ɾa.gua"),
    ("panamá", "pa.na.'ma"),
    ("paraguay", "pa.'ɾa.guai"),
    ("perú", "pe.'ɾu"),
    ("uruguay", "u.'ɾu.guai"),
    ("venezuela", "be.ne.'θue.la"),
    ("méxico", "ˈme.xi.ko"),
    ("canadá", "ka.na.'da"),
    ("salvador", "sal.ba.'doɾ"),

    # ── Nombres de categorías semánticas ──────────────────────────────
    ("país", "pa.'is"),
    ("países", "pa.'i.ses"),
    ("profesión", "pɾo.fe.'sion"),
    ("montaña", "mon.'ta.ɲa"),
    ("color", "ko.'loɾ"),
    ("fruta", "ˈfɾu.ta"),
    ("alimento", "a.li.'men.to"),
    ("ciudad", "θiu.'dad"),
    ("río", "ˈri.o"),
    ("cordillera", "koɾ.di.'ʝe.ɾa"),
    ("nombre", "ˈnom.bɾe"),
    ("persona", "peɾ.'so.na"),
    ("patología", "pa.to.lo.'xi.a"),
    ("electrodoméstico", "e.lek.tɾo.do.'mes.ti.ko"),
    ("utensilio", "u.ten.'si.lio"),
    ("ciencia", "ˈθien.θia"),
    ("animal", "a.ni.'mal"),

    # ── Animales ──────────────────────────────────────────────────────
    ("perro", "ˈpe.ro"),
    ("caballo", "ka.'ba.ʝo"),
    ("vaca", "ˈba.ka"),
    ("oveja", "o.'be.xa"),
    ("conejo", "ko.'ne.xo"),
    ("pájaro", "ˈpa.xa.ɾo"),
    ("águila", "ˈa.gi.la"),
    ("león", "le.'on"),
    ("serpiente", "seɾ.'pien.te"),
    ("ballena", "ba.'ʝe.na"),
    ("tiburón", "ti.bu.'ɾon"),
    ("abeja", "a.'be.xa"),
    ("hormiga", "oɾ.'mi.ga"),
    ("araña", "a.'ɾa.ɲa"),
    ("lobo", "ˈlo.bo"),
    ("oso", "ˈo.so"),
    ("ciervo", "ˈθieɾ.bo"),
    ("búho", "ˈbu.o"),

    # ── Ropa y accesorios ─────────────────────────────────────────────
    ("pantalón", "pan.ta.'lon"),
    ("falda", "ˈfal.da"),
    ("vestido", "bes.'ti.do"),
    ("chaqueta", "tʃa.'ke.ta"),
    ("abrigo", "a.'bɾi.go"),
    ("bota", "ˈbo.ta"),
    ("bufanda", "bu.'fan.da"),
    ("guante", "ˈguan.te"),
    ("sombrero", "som.'bɾe.ɾo"),
    ("cinturón", "θin.tu.'ɾon"),
    ("jersey", "ˈxeɾ.sei"),
    ("calcetín", "kal.θe.'tin"),
    ("corbata", "koɾ.'ba.ta"),
    ("pijama", "pi.'xa.ma"),

    # ── Muebles y objetos de la casa ──────────────────────────────────
    ("silla", "ˈsi.ʝa"),
    ("sofá", "so.'fa"),
    ("armario", "aɾ.'ma.ɾio"),
    ("estantería", "es.tan.te.'ɾi.a"),
    ("lámpara", "ˈlam.pa.ɾa"),
    ("alfombra", "al.'fom.bɾa"),
    ("espejo", "es.'pe.xo"),
    ("cuadro", "ˈkua.dɾo"),
    ("reloj", "re.'lox"),
    ("ventana", "ben.'ta.na"),
    ("balcón", "bal.'kon"),
    ("terraza", "te.'ra.θa"),
    ("jardín", "xaɾ.'din"),
    ("tejado", "te.'xa.do"),
    ("chimenea", "tʃi.me.'ne.a"),

    # ── Partes del cuerpo (ampliación) ────────────────────────────────
    ("pierna", "ˈpieɾ.na"),
    ("hombro", "ˈom.bɾo"),
    ("espalda", "es.'pal.da"),
    ("pecho", "ˈpe.tʃo"),
    ("barriga", "ba.'ri.ga"),
    ("muñeca", "mu.'ɲe.ka"),
    ("cuello", "ˈkue.ʝo"),
    ("frente", "ˈfɾen.te"),
    ("mejilla", "me.'xi.ʝa"),
    ("barbilla", "baɾ.'bi.ʝa"),
    ("lengua", "ˈlen.gua"),
    ("diente", "ˈdien.te"),
    ("estómago", "es.'to.ma.go"),
    ("corazón", "ko.ɾa.'θon"),
    ("hueso", "ˈue.so"),
    ("músculo", "ˈmus.ku.lo"),

    # ── Naturaleza y geografía ────────────────────────────────────────
    ("bosque", "ˈbos.ke"),
    ("playa", "ˈpla.ʝa"),
    ("desierto", "de.'sieɾ.to"),
    ("selva", "ˈsel.ba"),
    ("volcán", "bol.'kan"),
    ("isla", "ˈis.la"),
    ("lago", "ˈla.go"),
    ("valle", "ˈba.ʝe"),
    ("llanura", "ʝa.'nu.ɾa"),
    ("cueva", "ˈkue.ba"),
    ("arroyo", "a.'ro.ʝo"),
    ("pantano", "pan.'ta.no"),
    ("glaciar", "gla.'θiaɾ"),
    ("pradera", "pɾa.'de.ɾa"),
    ("océano", "o.'θe.a.no"),
    ("estrecho", "es.'tɾe.tʃo"),
    ("península", "pe.'nin.su.la"),

    # ── Tiempo y clima ────────────────────────────────────────────────
    ("lluvia", "ˈʝu.bia"),
    ("nieve", "ˈnie.be"),
    ("viento", "ˈbien.to"),
    ("tormenta", "toɾ.'men.ta"),
    ("trueno", "ˈtɾue.no"),
    ("granizo", "gɾa.'ni.θo"),
    ("niebla", "ˈnie.bla"),
    ("helada", "e.'la.da"),
    ("sequía", "se.'ki.a"),
    ("arcoíris", "aɾ.ko.'i.ɾis"),
    ("brisa", "ˈbɾi.sa"),
    ("huracán", "u.ɾa.'kan"),

    # ── Profesiones (ampliación) ──────────────────────────────────────
    ("maestro", "ma.'es.tɾo"),
    ("abogado", "a.bo.'ga.do"),
    ("arquitecto", "aɾ.ki.'tek.to"),
    ("enfermero", "en.feɾ.'me.ɾo"),
    ("bombero", "bom.'be.ɾo"),
    ("policía", "po.li.'θi.a"),
    ("ingeniero", "in.xe.'nie.ɾo"),
    ("carpintero", "kaɾ.pin.'te.ɾo"),
    ("electricista", "e.lek.tɾi.'θis.ta"),
    ("peluquero", "pe.lu.'ke.ɾo"),
    ("cocinero", "ko.θi.'ne.ɾo"),
    ("camarero", "ka.ma.'ɾe.ɾo"),
    ("periodista", "pe.ɾio.'dis.ta"),
    ("músico", "ˈmu.si.ko"),
    ("pintor", "pin.'toɾ"),
    ("escritor", "es.kɾi.'toɾ"),
    ("dentista", "den.'tis.ta"),
    ("farmacéutico", "faɾ.ma.'θeu.ti.ko"),
    ("veterinario", "be.te.ɾi.'na.ɾio"),
    ("piloto", "pi.'lo.to"),

    # ── Divergencias simples (v, z, j, ñ) ─────────────────────────────
    ("jovial", "xo.'bial"),
    ("navaja", "na.'ba.xa"),
    ("joven", "ˈxo.ben"),
    ("juvenil", "xu.be.'nil"),
    ("juzgado", "xuθ.'ga.do"),
    ("jazmín", "xaθ.'min"),
    ("vegetal", "be.xe.'tal"),
    ("viñedo", "bi.'ɲe.do"),
    ("vivero", "bi.'be.ɾo"),
    ("vaivén", "bai.'ben"),
    ("añejo", "a.'ɲe.xo"),
    ("pañuelo", "pa.'ɲue.lo"),
    ("zapatero", "θa.pa.'te.ɾo"),
    ("zorro", "ˈθo.ro"),
    ("zumo", "ˈθu.mo"),
    ("zanja", "ˈθan.xa"),
    ("zarza", "ˈθaɾ.θa"),
    ("ceniza", "θe.'ni.θa"),
    ("ventaja", "ben.'ta.xa"),
    ("jovencito", "xo.ben.'θi.to"),
    ("vejez", "be.'xeθ"),

    # ── Dígrafos (ll, ch, rr, qu, gu+e/i) ────────────────────────────
    ("perchero", "peɾ.'tʃe.ɾo"),
    ("mochilero", "mo.tʃi.'le.ɾo"),
    ("torrecilla", "to.re.'θi.ʝa"),
    ("carroza", "ka.'ro.θa"),
    ("parrilla", "pa.'ri.ʝa"),
    ("mosquito", "mos.'ki.to"),
    ("raqueta", "ra.'ke.ta"),
    ("roquedal", "ro.ke.'dal"),
    ("parqué", "paɾ.'ke"),
    ("marqués", "maɾ.'kes"),
    ("guerrilla", "ge.'ri.ʝa"),
    ("guerrero", "ge.'re.ɾo"),
    ("coqueta", "ko.'ke.ta"),
    ("orquesta", "oɾ.'kes.ta"),

    # ── Contextuales (c+e/i, g+e/i) ──────────────────────────────────
    ("genocidio", "xe.no.'θi.dio"),
    ("geología", "xe.o.lo.'xi.a"),
    ("ciprés", "θi.'pɾes"),
    ("cimiento", "θi.'mien.to"),
    ("receta", "re.'θe.ta"),
    ("circulación", "θiɾ.ku.la.'θion"),
    ("civilización", "θi.bi.li.θa.'θion"),
    ("generación", "xe.ne.ɾa.'θion"),
    ("generoso", "xe.ne.'ɾo.so"),
    ("necesidad", "ne.θe.si.'dad"),
    ("capacidad", "ka.pa.θi.'dad"),
    ("felicidad", "fe.li.θi.'dad"),
    ("velocidad", "be.lo.θi.'dad"),

    # ── Combinaciones complejas (x, cc, múltiples) ────────────────────
    ("excelente", "es.θe.'len.te"),
    ("excursión", "es.kuɾ.'sion"),
    ("existencia", "ek.sis.'ten.θia"),
    ("experiencia", "es.pe.'ɾien.θia"),
    ("oxígeno", "ok.'si.xe.no"),
    ("saxofón", "sak.so.'fon"),
    ("taxista", "tak.'sis.ta"),
    ("reflexión", "re.flek.'sion"),
    ("accidente", "ak.θi.'den.te"),
    ("dirección", "di.ɾek.'θion"),
    ("protección", "pɾo.tek.'θion"),
    ("producción", "pɾo.duk.'θion"),
    ("infección", "in.fek.'θion"),
    ("inspección", "ins.pek.'θion"),
    ("corrección", "ko.rek.'θion"),
    ("selección", "se.lek.'θion"),
    ("conexión", "ko.nek.'sion"),
    ("complexión", "kom.plek.'sion"),
]

# Build the analyzed bank (deduplicated)
_seen = set()
BANCO_PALABRAS = []
for ort, trans in _PALABRAS_RAW:
    if ort not in _seen:
        _seen.add(ort)
        BANCO_PALABRAS.append(_analizar_palabra(ort, trans))


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES DE SELECCIÓN
# ═══════════════════════════════════════════════════════════════════════

def seleccionar_palabras(
    num_silabas_min: int = 1,
    num_silabas_max: int = 99,
    requiere_codas: bool = False,
    requiere_ataques_complejos: bool = False,
    requiere_afi_divergentes: bool = False,
    solo_estructurales: bool = False,
    solo_sistemicas: bool = False,
    max_resultados: int = None,
) -> list[dict]:
    """
    Selecciona palabras del banco según criterios.

    Args:
        num_silabas_min/max: rango de número de sílabas
        requiere_codas: solo palabras con al menos una coda
        requiere_ataques_complejos: solo palabras con al menos un ataque complejo
        requiere_afi_divergentes: solo palabras con grafías divergentes
        solo_estructurales: selecciona palabras buenas para errores estructurales
            (con codas, ataques complejos, o varias sílabas)
        solo_sistemicas: selecciona palabras buenas para errores sistémicos
            (con grafías divergentes — el alumno debe conocer el AFI)
        max_resultados: limitar número de resultados

    Returns:
        Lista de dicts con las propiedades de cada palabra.
    """
    resultado = []

    for p in BANCO_PALABRAS:
        if p['num_silabas'] < num_silabas_min or p['num_silabas'] > num_silabas_max:
            continue
        if requiere_codas and p['num_codas'] == 0:
            continue
        if requiere_ataques_complejos and p['num_ataques_complejos'] == 0:
            continue
        if requiere_afi_divergentes and p['num_afi_divergentes'] == 0:
            continue

        if solo_estructurales:
            # Buenas para errores de sílaba/palabra: tienen codas, ataques complejos, o 3+ sílabas
            if p['num_codas'] == 0 and p['num_ataques_complejos'] == 0 and p['num_silabas'] < 3:
                continue

        if solo_sistemicas:
            # Buenas para errores sistémicos: tienen consonantes con AFI divergente
            if p['num_afi_divergentes'] == 0:
                continue

        resultado.append(p)

    if max_resultados and len(resultado) > max_resultados:
        resultado = resultado[:max_resultados]

    return resultado


def resumen_banco() -> str:
    """Devuelve un resumen del banco de palabras en formato legible."""
    total = len(BANCO_PALABRAS)
    por_silabas = {}
    con_codas = 0
    con_ataques = 0
    con_afi = 0

    for p in BANCO_PALABRAS:
        n = p['num_silabas']
        por_silabas[n] = por_silabas.get(n, 0) + 1
        if p['num_codas'] > 0:
            con_codas += 1
        if p['num_ataques_complejos'] > 0:
            con_ataques += 1
        if p['num_afi_divergentes'] > 0:
            con_afi += 1

    lineas = [f"Banco de palabras: {total} palabras\n"]
    lineas.append("Por número de sílabas:")
    for n in sorted(por_silabas):
        lineas.append(f"  {n} sílabas: {por_silabas[n]}")
    lineas.append(f"\nCon codas: {con_codas}")
    lineas.append(f"Con ataques complejos: {con_ataques}")
    lineas.append(f"Con grafías AFI divergentes: {con_afi}")

    return '\n'.join(lineas)


def tabla_banco() -> str:
    """Devuelve el banco completo en formato tabla markdown."""
    lineas = ["| Palabra | Transcripción | Sílabas | Codas | At. complejos | AFI divergentes |",
              "|---|---|:---:|:---:|:---:|:---:|"]
    for p in BANCO_PALABRAS:
        lineas.append(
            f"| {p['ortografia']} | /{p['transcripcion']}/ | {p['num_silabas']} | "
            f"{p['num_codas']} | {p['num_ataques_complejos']} | {p['num_afi_divergentes']} |"
        )
    return '\n'.join(lineas)
