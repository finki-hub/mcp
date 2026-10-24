from app.schemas.course import AccreditationYear, StudyProgram
from app.schemas.study_program import StudyCycle, StudyProgramInfo
from app.utils.query_matcher import transliterate_and_normalize

_ENGLISH = "англиски"
_PROGRAM_URL = "https://finki.ukim.mk/program/"
_MASTER_URL = "https://finki.ukim.mk/master-program/"
_DOCTORAL_URL = "https://finki.ukim.mk/studii-2/vidovi-studii/doktorski-studii/"


def _accreditation(code: str) -> str:
    # FINKI codes embed the accreditation year: KN23, KN23_3, SIIS18.
    return f"20{code.split('_', maxsplit=1)[0][-2:]}"


def _first(
    code: str,
    abbreviation: StudyProgram | None,
    name: str,
    name_en: str,
    years: int,
    *,
    language: str | None = None,
) -> StudyProgramInfo:
    return StudyProgramInfo(
        code=code,
        abbreviation=abbreviation,
        name=name,
        name_en=name_en if name_en != name else None,
        cycle=StudyCycle.FIRST,
        duration_years=years,
        accreditation=_accreditation(code),
        language=language,
        url=f"{_PROGRAM_URL}{code}",
    )


def _second(code: str, name: str, name_en: str, years: int) -> StudyProgramInfo:
    return StudyProgramInfo(
        code=code,
        name=name,
        name_en=name_en if name_en != name else None,
        cycle=StudyCycle.SECOND,
        duration_years=years,
        accreditation="2023",
        url=f"{_MASTER_URL}{code}",
    )


# Current programs as listed on finki.ukim.mk (checked 2026-10-24):
# - first cycle: /studii-2/vidovi-studii/dodiplomski-studii/ (English names from /en/...)
# - second cycle: /studii-2/vidovi-studii/magisterski-studii-2/ (2023 programs only)
# - third cycle: /studii-2/vidovi-studii/doktorski-studii/
# Language of instruction: SEIS is taught in English (confirmed by the FINKI Hub
# team; the undergraduate listing also marks every SEIS variant "EN"). No official
# page states the language for any other program, so it is left unknown.
_PROGRAMS: tuple[StudyProgramInfo, ...] = (
    _first("KN23", StudyProgram.KN, "Компјутерски науки", "Computer Science", 4),
    _first("KN23_3", StudyProgram.KN, "Компјутерски науки", "Computer Science", 3),
    _first(
        "SIIS23",
        StudyProgram.SIIS,
        "Софтверско инженерство и информациски системи",
        "Software Engineering and Information Systems",
        4,
    ),
    _first(
        "SIIS23_3",
        StudyProgram.SIIS,
        "Софтверско инженерство и информациски системи",
        "Software Engineering and Information Systems",
        3,
    ),
    _first(
        "SEIS23",
        StudyProgram.SEIS,
        "Software Engineering and Information Systems",
        "Software Engineering and Information Systems",
        4,
        language=_ENGLISH,
    ),
    _first(
        "SEIS23_3",
        StudyProgram.SEIS,
        "Software Engineering and Information Systems",
        "Software Engineering and Information Systems",
        3,
        language=_ENGLISH,
    ),
    _first(
        "IMB23",
        StudyProgram.IMB,
        "Интернет, мрежи и безбедност",
        "Internet, Networks and Security",
        4,
    ),
    _first(
        "IMB23_3",
        StudyProgram.IMB,
        "Интернет, мрежи и безбедност",
        "Internet, Networks and Security",
        3,
    ),
    _first(
        "KI23", StudyProgram.KI, "Компјутерско инженерство", "Computer Engineering", 4
    ),
    _first(
        "KI23_3", StudyProgram.KI, "Компјутерско инженерство", "Computer Engineering", 3
    ),
    _first(
        "PIT23",
        StudyProgram.PIT,
        "Примена на информациски технологии",
        "Application of Information Technologies",
        4,
    ),
    _first(
        "PIT23_3",
        StudyProgram.PIT,
        "Примена на информациски технологии",
        "Application of Information Technologies",
        3,
    ),
    _first(
        "IE23", StudyProgram.IE, "Информатичка едукација", "Informatics Education", 4
    ),
    _first(
        "SSP23",
        StudyProgram.SSP,
        "Стручни студии за програмирање",
        "Vocational Studies in Programming",
        2,
    ),
    _first(
        "SSP23_3",
        StudyProgram.SSP,
        "Стручни студии за програмирање",
        "Vocational Studies in Programming",
        3,
    ),
    _first("KN18", StudyProgram.KN, "Компјутерски науки", "Computer Science", 4),
    _first(
        "SIIS18",
        StudyProgram.SIIS,
        "Софтверско инженерство и информациски системи",
        "Software Engineering and Information Systems",
        4,
    ),
    _first(
        "SEIS18",
        StudyProgram.SEIS,
        "Software Engineering and Information Systems",
        "Software Engineering and Information Systems",
        4,
        language=_ENGLISH,
    ),
    _first(
        "IMB18",
        StudyProgram.IMB,
        "Интернет, мрежи и безбедност",
        "Internet, Networks and Security",
        4,
    ),
    _first(
        "KI18", StudyProgram.KI, "Компјутерско инженерство", "Computer Engineering", 4
    ),
    _first(
        "PIT18",
        StudyProgram.PIT,
        "Примена на информациски технологии",
        "Application of Information Technologies",
        4,
    ),
    _first(
        "PET18",
        None,
        "Примена на информациски технологии",
        "Application of Information Technologies",
        4,
    ),
    _first("KE18", StudyProgram.KE, "Компјутерска едукација", "Computer Education", 4),
    _second(
        "DS23_1",
        "Data Science in Computer Science and Engineering",
        "Data Science in Computer Science and Engineering",
        1,
    ),
    _second(
        "BKK23_1",
        "Безбедност, криптографија и кодирање",
        "Security, Cryptography and Coding",
        1,
    ),
    _second(
        "BKK23_2",
        "Безбедност, криптографија и кодирање",
        "Security, Cryptography and Coding",
        2,
    ),
    _second("BI23_1", "Биоинформатика", "Bioinformatics", 1),
    _second("BI23_2", "Биоинформатика", "Bioinformatics", 2),
    _second("EDU23_1", "Едукација со ИКТ", "Education with ICT", 1),
    _second("IS23_1", "Интелигентни системи", "Intelligent Systems", 1),
    _second(
        "ITCS23_1",
        "Интернет технологии и сајбер безбедност",
        "Internet Technologies and Cybersecurity",
        1,
    ),
    _second("KN23_1", "Компјутерски науки", "Computer Science", 1),
    _second("CC23_1", "Пресметување во облак", "Cloud Computing", 1),
    _second("CC23_2", "Пресметување во облак", "Cloud Computing", 2),
    _second("SVS23_1", "Софтвер за вградливи системи", "Embedded Systems Software", 1),
    _second("SI23_1", "Софтверско инженерство", "Software Engineering", 1),
    _second("SI23_2", "Софтверско инженерство", "Software Engineering", 2),
    _second(
        "ITM23_1",
        "Управување во информатички технологии",
        "Information Technology Management",
        1,
    ),
    _second(
        "ITM23_2",
        "Управување во информатички технологии",
        "Information Technology Management",
        2,
    ),
    _second("EI23_1", "Еко-информатика", "Ecoinformatics", 1),
    _second(
        "SAP23_1",
        "Статистика и аналитика на податоци",
        "Statistics and Data Analytics",
        1,
    ),
    _second(
        "SAP23_2",
        "Статистика и аналитика на податоци",
        "Statistics and Data Analytics",
        2,
    ),
    StudyProgramInfo(
        code="ID",
        name="Информатика",
        cycle=StudyCycle.THIRD,
        url=f"{_DOCTORAL_URL}id/",
    ),
    StudyProgramInfo(
        code="KNID",
        name="Компјутерски науки и инженерство",
        cycle=StudyCycle.THIRD,
        url=f"{_DOCTORAL_URL}knid/",
    ),
)


def _matches_query(program: StudyProgramInfo, query: str) -> bool:
    fields = (program.code, program.abbreviation, program.name, program.name_en)
    return any(query in transliterate_and_normalize(field) for field in fields if field)


def list_study_programs(
    *,
    cycle: StudyCycle | None = None,
    accreditation: AccreditationYear | None = None,
    query: str | None = None,
) -> list[StudyProgramInfo]:
    normalized_query = transliterate_and_normalize(query) if query else ""
    return [
        program
        for program in _PROGRAMS
        if (cycle is None or program.cycle == cycle)
        and (accreditation is None or program.accreditation == accreditation)
        and (not normalized_query or _matches_query(program, normalized_query))
    ]
