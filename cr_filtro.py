"""Filtro de buenas noticias ticas (español de Costa Rica)."""
import re
import actualizar as A
import regiones as R
import deportes as D

def rx(*parts):
    return re.compile(r"(?<![a-z])(" + "|".join(parts) + r")", re.I)

# Todo se compara sin tildes y en minúscula (A.fold).
POS = {
    "logro": rx(r"gan(a|an|o|aron|ara|aran|ador[ae]?s?) (el |la |un |una )?(primer lugar|premio|medalla|concurso|competencia|olimpiada|reconocimiento|beca|torneo internacional)",
                r"primer lugar (en|de) (una |la )?(competencia|concurso|olimpiada|feria)",
                r"premio (nacional|internacional|a la excelencia|eunice odio|mario monteforte|aquileo)",
                r"reconocid[oa]s? (internacionalmente|por la (onu|fao|unesco|oms|ops))", r"galardon", r"medalla de (oro|plata|bronce)",
                r"(costa rica|tic[oa]s?|costarricenses?) hace historia", r"representara a costa rica en (la )?final",
                r"al primer lugar", r"primeros lugares", r"gan\w* (un |el |la )?(hackat|\$|¢|₡)", r"conquist\w* (\w+ )?primer", r"orgullo (costarricense|tico|nacional)", r"recib\w* (el |un )?premio", r"premia\b", r"romp\w* (el )?record", r"recib\w* (un )?(reconocimiento|premio) (de|del|internacional)", r"named among", r"wins? (an? )?(award|prize)"),
    "ambiente": rx(r"tortugas?", r"desove", r"liberan? (a )?(un|una|dos|tres|\d+)? ?(tortug|perezos|mono|lapa|jaguar|ave|felin|manati|delfin|ballena|tucan|oso)",
                   r"rescat(an|aron|e de) (a )?(un |una |dos |\d+ )?(perezos|mono|lapa|jaguar|tortug|felin|manati|delfin|ballena|tucan|oso|perro|cachorr|caball|venado|ave)",
                   r"nuev(a|os|as) (especies?|registros de especies)", r"reforest", r"arboles (sembrad|plantad)", r"siembran? \d", r"bandera azul",
                   r"carbono neutral", r"corredor biologico", r"area protegida", r"parque nacional (amplia|nuevo|crece)", r"recuperacion de (bosque|arrecife|manglar|coral)",
                   r"energia (solar|renovable|limpia)", r"reciclaj", r"nueva infraestructura para visitantes"),
    "salud": rx(r"nuev[oa] (cirugia|tratamiento|tecnica|terapia|vacuna|medicamento)", r"primer(a|o)? (trasplante|cirugia)", r"trasplante",
                r"esperanza (contra|para)", r"inaugur\w* (nuevo |nueva )?(ebais|hospital|clinica|centro de salud)", r"vacunacion gratuita"),
    "social": rx(r"don(an|aron|o|a|acion|aciones) (de )?", r"voluntari", r"banco de alimentos", r"recaud\w* fondos", r"becas?",
                 r"se graduan", r"nuevas carreras", r"graduad[oa]s", r"construy\w* (casas|viviendas|escuela|aula)", r"inaugur\w* (escuela|colegio|biblioteca|puente|parque|centro comunitario|cecudi|aulas?)",
                 r"solidaridad", r"ayudan a", r"brigada"),
    "ciencia": rx(r"(investigador|cientific|estudiantes?|universitari)\w* (de la |del )?(ucr|tec|una|uned)?\s*(descubr|desarroll|crean?|disen|identific|invent|ganan)",
                  r"descubr\w* (una |un )?(nueva|nuevo)", r"investigacion sobre", r"coheteria", r"satelite", r"patente de invencion"),
}
NEG = rx(
    # sucesos
    r"muer", r"murio", r"fallec", r"asesin", r"homicid", r"balacera", r"dispar", r"herid", r"accidente", r"choque", r"guindo",
    r"atropell", r"robo", r"asalt", r"narco", r"droga", r"detenid", r"detien", r"captur", r"prision", r"preventiva", r"fiscalia",
    r"oij", r"juzgado", r"separan?", r"ataque", r"brutal", r"denunci", r"estafa", r"fraude", r"irregularidad", r"crimen", r"criminal", r"violencia", r"abuso", r"cárcel", r"carcel",
    r"cacco", r"megacarcel", r"reos?", r"privados de libertad", r"desaparec", r"sismo", r"temblor", r"huracan", r"inundac", r"emergencia",
    r"alerta", r"incendio", r"rescatan a (un )?(hombre|mujer|persona|joven|nino|conductor|motociclista|turista)",
    # política y pleitos
    r"diputad", r"pln", r"ppso", r"frente amplio", r"veto", r"vetan", r"recorte", r"acusa", r"critica", r"rechaz", r"polemic",
    r"renunci", r"crisis", r"deuda", r"morosidad", r"advierte", r"preocupa", r"amenaza", r"cierre", r"cerrar",
    # suerte, farándula, consumo
    r"loteria", r"chances?", r"numeros ganadores", r"sorteo", r"jps", r"miss universo", r"mira quien baila", r"mqb", r"reality",
    r"concierto", r"farandula", r"receta", r"truco", r"horoscopo",
    # PR empresarial
    r"reputacion", r"sucursal", r"zona franca", r"reporte de sostenibilidad", r"marca un hito", r"bac\b", r"telecable", r"mcdonald", r"ficohsa", r"el nino", r"calentamiento",
)
SPORT = rx(r"saprissa", r"herediano", r"alajuelense", r"liga", r"cartagines", r"puntarenas fc", r"perez zeledon", r"medford",
           r"carevic", r"sele(ccion)?", r"gol(es|azo)?", r"partido", r"torneo", r"campeonato", r"futbol", r"keylor", r"verstappen", r"amarini", r"villatoro", r"amarini", r"villatoro",
           r"maraton", r"gimnas", r"atlet", r"nadador", r"natacion", r"boxe", r"ciclis", r"karate", r"taekwondo", r"ajedrez", r"f1", r"nba", r"mlb", r"dodgers", r"tenis", r"surf")
SPORT_HISTORIC = rx(r"medalla de oro", r"campeon(a|es)? (mundial|del mundo|panamerican|centroamerican)", r"record mundial",
                    r"clasific\w* (al|a los) (mundial|juegos olimpicos)", r"hace historia", r"por primera vez")
AGENDA = rx(r"feria", r"charla", r"congreso", r"foro", r"taller", r"evento gratuito", r"exposicion", r"festival", r"semana de la", r"encuentro", r"sera sede", r"puede optar", r"^¿")
CR_PLACE = R.KW["costarica"]


CR_ANGLE = re.compile(R.KW["costarica"].pattern + "|" + r"(?<![a-z])(ucr|uned|utn|ccss|sinac|minae|inder|imas|conare|"
                      r"municipalidad|ebais|cen-cinai|ctp|colegio|escuela|cantonal|caribe sur|zona norte|zona sur|pacifico central|"
                      r"generaleno|josefino|herediano|alajuelense|cartagines|limonense|guanacasteco|nicoyano|saprissa|"
                      r"keylor|la sele|parque nacional|corredor biologico)(?![a-z])")


ACRONYMS = re.compile(r"\b(TEC|UNA|MEP|ICE|AyA|ICT|TSE|INA|CNE|BCR|INS)\b")  # con mayúsculas: «una» o «ice» no cuentan


def cr_angle(text, original=""):
    """La nota tiene que ver con Costa Rica (lugar, institución o gentilicio)."""
    return bool(CR_ANGLE.search(text) or ACRONYMS.search(original))


def foreign(t):
    """Nota sobre otro país, sin mención de Costa Rica (las buenas noticias globales ya vienen de otros feeds)."""
    if CR_PLACE.search(t):
        return False
    return any(rx_.search(t) for r, rx_ in R.KW.items() if r != "costarica") or R.US.search(t) or bool(
        re.search(r"(?<![a-z])(chilen|colombian|mexican|estadounidense|espanol|argentin|nobel|planeta|onu|oms)", t))


def judge(it, allow_agenda=False):
    """Devuelve (subtema, motivo_rechazo)."""
    t = A.fold(it["title"].lower())
    s = A.fold(it.get("summary", "")[:200].lower())
    # Notas de agencias sobre otros países que publican medios ticos: fuera si no tienen ángulo tico.
    if it.get("kind") != "inst" and not cr_angle(t + " " + s, it["title"] + " " + it.get("summary", "")[:200]):
        return None, "sin ángulo tico"
    if (SPORT.search(t) or D.is_sport(t)) and not POS["ciencia"].search(t) and "startup" not in t:
        if D.sport_win(t) and not NEG.search(t.replace("ganadores", "")):
            return "deportes", None
        return None, "deporte (no es triunfo)"
    if NEG.search(t):
        return None, "negativo"
    if AGENDA.search(t) and not allow_agenda:
        return None, "agenda/evento"
    hits = [k for k, r in POS.items() if r.search(t)]
    if not hits and NEG.search(s) is None:
        hits = [k for k, r in POS.items() if r.search(s) and k in ("ambiente", "ciencia")]
    if not hits:
        return None, "sin señal positiva"
    sub = {"logro": "acciones", "ambiente": "ambiente", "salud": "salud", "social": "comunidad", "ciencia": "ciencia"}[hits[0]]
    return sub, None
