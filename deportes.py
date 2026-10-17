"""Triunfos deportivos como buena noticia (decisión de Alice: «cualquier triunfo deportivo»).
Cuenta: títulos, medallas, campeonatos, clasificaciones, récords, premios, primeros lugares.
No cuenta: resultados de partidos sin título, derrotas, empates, fichajes, lesiones, apuestas,
escándalos o violencia, ni previas/calendarios. Todo se compara sin tildes y en minúscula."""
import re

SPORT = re.compile(r"(?<![a-z])(futbol|liga|seleccion|sele|gol(es|eador)?|partido|torneo|campeonato|mundial|olimpi\w*|juegos (olimpicos|panamericanos|centroamericanos)|"
                   r"atlet\w*|marat\w*|nadador\w*|natacion|surf\w*|gimnas\w*|tenis\w*|ciclis\w*|boxe\w*|karate|taekwondo|judo|ajedrez|"
                   r"triatl\w*|beisbol|baloncesto|basquet|voleibol|f1|formula 1|gran premio|piloto|saprissa|herediano|alajuelense|cartagines|"
                   r"football|soccer|tennis|cyclist|cycling|olympic\w*|athlet\w*|swimm\w*|marathon|boxing|chess|rugby|cricket|golf|nba|nfl|mlb|"
                   r"grand prix|world cup|premier league|champions league|tour de france)(?![a-z])")
WIN = re.compile(r"(?<![a-z])((se (consagr|coron)\w*|sale|quedo|es|son|fue|fueron|proclam\w*) campeon\w*|campeon(a|as|es)? (del mundo|mundial|nacional|panamerican\w*|centroamerican\w*|olimpic\w*|de (la|el) )|representara (al pais|a costa rica)|por primera vez (al|a la|en (el|la|los|un|una)) (mundial|olimpi\w*|final|juegos)|titulo|se corona|coronad\w*|corona\w* campeon|medall\w*|(presea|medalla) de (oro|plata|bronce)|(oro|plata|bronce) (en|para|olimpic\w*|mundial|panamerican\w*)|podio|record|"
                 r"clasific\w*|hace historia|primer lugar|primeros lugares|conquist\w*|"
                 r"gan\w* (el |la |su |un |una |dos |tres )?(titulo|copa|torneo|campeonato|maraton|gran premio|gp|final|liga|mundial|oro|medalla|premio|balon|etapa|carrera|trofeo|serie)|"
                 r"(crowned|become|becomes|are|is) (the )?(world |national |european )?champions?|wins? (the )?(world |national )?title|gold|silver|bronze|podium|qualif\w*|crowned|record|first ever|"
                 r"wins? (the |a |an |his |her |their )?(title|cup|gold|medal|championship|final|grand prix|gp|marathon|race|award|trophy|tour|open|stage|series|pennant))(?![a-z])")
BAD = re.compile(r"(?<![a-z])(empat\w*|pierde\w*|perdi\w*|derrota\w*|cae ante|cayo|caen|eliminad\w*|fichaj\w*|ficha|traspaso|lesion\w*|baja|"
                 r"apuesta\w*|watch|video|caso|igual\w*|no podra|beat|beats|separacion|anillo|enfrent\w*|plantel|para luchar|luch\w* por|partidos de|complicad\w*|matematica|peor|apoya|vence|golea|remont\w*|sonroja|triunfo de|cifra|"
                 r"escandal\w*|agresi\w*|violencia|pelea|insult\w*|sancion\w*|expuls\w*|arbitr\w*|previa|vs|duelo|antes de|"
                 r"alineacion|convocatoria|donde ver|a que hora|cuando juega|en vivo|resumen|necesita|podria|puede|aspira|busca|a las puertas|"
                 r"despid\w*|destitu\w*|renuncia\w*|polemic\w*|denuncia\w*|crimen|detenid\w*|muer\w*|fallec\w*|"
                 r"loses?|lost|defeat\w*|draw|drawn|beaten|injur\w*|transfer\w*|signs?|preview|scandal|banned|ban|suspend\w*|racis\w*|"
                 r"ended|ends|crash\w*|sacked|fired|charged|arrest\w*|dies|died|could|would|hopes?|bid to|chasing|things to|what we learned|"
                 r"odds|betting|tips|live|as it happened|player ratings|predict\w*)(?![a-z])")


def is_sport(t):
    return bool(SPORT.search(t))


def sport_win(t):
    """t ya en minúscula y sin tildes. True si es un triunfo deportivo que cuenta como buena noticia."""
    return bool(WIN.search(t)) and not BAD.search(t)
