from app.schemas.course import AccreditationYear, StudyProgram
from app.schemas.study_program import StudyCycle, StudyProgramInfo
from app.utils.query_matcher import transliterate_and_normalize

_ENGLISH = "англиски"
_PROGRAM_URL = "https://finki.ukim.mk/program/"
_MASTER_URL = "https://finki.ukim.mk/master-program/"
_DOCTORAL_URL = "https://finki.ukim.mk/studii-2/vidovi-studii/doktorski-studii/"

type _Names = tuple[str, str]

_SEIS_NAME = "Software Engineering and Information Systems"

_KN: _Names = ("Компјутерски науки", "Computer Science")
_SIIS: _Names = ("Софтверско инженерство и информациски системи", _SEIS_NAME)
_SEIS: _Names = (_SEIS_NAME, _SEIS_NAME)
_IMB: _Names = ("Интернет, мрежи и безбедност", "Internet, Networks and Security")
_KI: _Names = ("Компјутерско инженерство", "Computer Engineering")
_PIT: _Names = (
    "Примена на информациски технологии",
    "Application of Information Technologies",
)
_IE: _Names = ("Информатичка едукација", "Informatics Education")
_SSP: _Names = ("Стручни студии за програмирање", "Vocational Studies in Programming")
_KE: _Names = ("Компјутерска едукација", "Computer Education")

_DS: _Names = (
    "Data Science in Computer Science and Engineering",
    "Data Science in Computer Science and Engineering",
)
_BKK: _Names = (
    "Безбедност, криптографија и кодирање",
    "Security, Cryptography and Coding",
)
_BI: _Names = ("Биоинформатика", "Bioinformatics")
_EDU: _Names = ("Едукација со ИКТ", "Education with ICT")
_IS: _Names = ("Интелигентни системи", "Intelligent Systems")
_ITCS: _Names = (
    "Интернет технологии и сајбер безбедност",
    "Internet Technologies and Cybersecurity",
)
_CC: _Names = ("Пресметување во облак", "Cloud Computing")
_SVS: _Names = ("Софтвер за вградливи системи", "Embedded Systems Software")
_SI: _Names = ("Софтверско инженерство", "Software Engineering")
_ITM: _Names = (
    "Управување во информатички технологии",
    "Information Technology Management",
)
_EI: _Names = ("Еко-информатика", "Ecoinformatics")
_SAP: _Names = ("Статистика и аналитика на податоци", "Statistics and Data Analytics")


def _accreditation(code: str) -> str:
    # FINKI codes embed the accreditation year: KN23, KN23_3, SIIS18.
    return f"20{code.split('_', maxsplit=1)[0][-2:]}"


def _first(
    code: str,
    abbreviation: StudyProgram | None,
    names: _Names,
    years: int,
    *,
    language: str | None = None,
) -> StudyProgramInfo:
    name, name_en = names
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


def _second(code: str, names: _Names, years: int) -> StudyProgramInfo:
    name, name_en = names
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
    _first("KN23", StudyProgram.KN, _KN, 4),
    _first("KN23_3", StudyProgram.KN, _KN, 3),
    _first("SIIS23", StudyProgram.SIIS, _SIIS, 4),
    _first("SIIS23_3", StudyProgram.SIIS, _SIIS, 3),
    _first("SEIS23", StudyProgram.SEIS, _SEIS, 4, language=_ENGLISH),
    _first("SEIS23_3", StudyProgram.SEIS, _SEIS, 3, language=_ENGLISH),
    _first("IMB23", StudyProgram.IMB, _IMB, 4),
    _first("IMB23_3", StudyProgram.IMB, _IMB, 3),
    _first("KI23", StudyProgram.KI, _KI, 4),
    _first("KI23_3", StudyProgram.KI, _KI, 3),
    _first("PIT23", StudyProgram.PIT, _PIT, 4),
    _first("PIT23_3", StudyProgram.PIT, _PIT, 3),
    _first("IE23", StudyProgram.IE, _IE, 4),
    _first("SSP23", StudyProgram.SSP, _SSP, 2),
    _first("SSP23_3", StudyProgram.SSP, _SSP, 3),
    _first("KN18", StudyProgram.KN, _KN, 4),
    _first("SIIS18", StudyProgram.SIIS, _SIIS, 4),
    _first("SEIS18", StudyProgram.SEIS, _SEIS, 4, language=_ENGLISH),
    _first("IMB18", StudyProgram.IMB, _IMB, 4),
    _first("KI18", StudyProgram.KI, _KI, 4),
    _first("PIT18", StudyProgram.PIT, _PIT, 4),
    _first("PET18", None, _PIT, 4),
    _first("KE18", StudyProgram.KE, _KE, 4),
    _second("DS23_1", _DS, 1),
    _second("BKK23_1", _BKK, 1),
    _second("BKK23_2", _BKK, 2),
    _second("BI23_1", _BI, 1),
    _second("BI23_2", _BI, 2),
    _second("EDU23_1", _EDU, 1),
    _second("IS23_1", _IS, 1),
    _second("ITCS23_1", _ITCS, 1),
    _second("KN23_1", _KN, 1),
    _second("CC23_1", _CC, 1),
    _second("CC23_2", _CC, 2),
    _second("SVS23_1", _SVS, 1),
    _second("SI23_1", _SI, 1),
    _second("SI23_2", _SI, 2),
    _second("ITM23_1", _ITM, 1),
    _second("ITM23_2", _ITM, 2),
    _second("EI23_1", _EI, 1),
    _second("SAP23_1", _SAP, 1),
    _second("SAP23_2", _SAP, 2),
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
