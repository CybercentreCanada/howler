import datetime
import math
import os
import random
import time
from typing import Any as _Any
from typing import Optional as _Optional

from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.odm import (
    IP,
    MAC,
    MD5,
    SHA1,
    SHA256,
    URI,
    UUID,
    Any,
    Boolean,
    Classification,
    ClassificationString,
    Compound,
    Date,
    Domain,
    Email,
    EmptyableKeyword,
    Enum,
    Float,
    HowlerHash,
    Integer,
    Json,
    Keyword,
    List,
    LowerKeyword,
    Mapping,
    Model,
    Optional,
    PhoneNumber,
    Platform,
    Processor,
    SSDeepHash,
    Text,
    UpperKeyword,
    URIPath,
)
from howler.odm.base import _Field
from howler.utils.uid import get_random_id

ALPHA = "ABCDEFGHIJKLMNOPQRSTUPVXYZabcdefghijklmnopqrstuvwxyz"
HASH_ALPHA = "abcdef0123456789"
SSDEEP_ALPHA = f"{ALPHA}0123456789"
WORDS = """The Cyber Centre stays on the cutting edge of technology by working with commercial vendors of cyber security
technology to support their development of enhanced cyber defence tools To do this our experts survey the cyber
security market evaluate emerging technologies in order to determine their potential to improve cyber security
across the country The Cyber Centre supports innovation by collaborating with all levels of government private
industry academia to examine complex problems in cyber security We are constantly engaging partners to promote
an open innovative environment We invite partners to work with us but also promote other Government of Canada
innovation programs One of our key partnerships is with the Government of Canada Build in Canada Innovation Program
BCIP The BCIP helps Canadian companies of all sizes transition their state of the art goods services from the
laboratory to the marketplace For certain cyber security innovations the Cyber Centre performs the role of technical
authority We evaluate participating companies new technology provide feedback in order to assist them in bringing
their product to market To learn more about selling testing an innovation visit the BCIP website""".split()
WORDS = list(set(WORDS))


with open(os.path.join(os.path.dirname(__file__), "charter.txt"), "r") as f:
    SENTENCES = [line.strip() for line in f.readlines()]

MAPPING_KEYS = ["key_a", "key_b", "key_c", "key_d", "key_e", "key_f"]
EXT = [".jpg", ".doc", ".exe", ".pdf", ".xls", ".lnk", ".gif", ".ppt"]

DOM = [".com", ".ca", ".biz", ".edu"]

USERS = ["admin", "user", "shawnh"]

GROUPS = ["USERS", "ADMINS", "ANALYSTS"]

F_TYPES = [
    "image/png",
    "executable/windows",
    "document/pdf",
    "document/office",
    "document/xml",
    "code/javascript",
    "code/vb",
]

DEPARTMENTS = [
    ("Accessibility Standards Canada", "ASC"),
    ("Administrative Tribunals Support Service of Canada", "ATSSC"),
    ("Agriculture and Agri-Food Canada", "AAFC"),
    ("Atlantic Canada Opportunities Agency", "ACOA"),
    ("Atlantic Pilotage Authority Canada", "APA"),
    ("Atomic Energy of Canada Limited", "AECL"),
    ("Auditor General of Canada (Office of the)", "OAG"),
    ("Blue Water Bridge Canada", "BWB"),
    ("Business Development Bank of Canada", "BDC"),
    ("Canada Agricultural Review Tribunal", "CART"),
    ("Canada Border Services Agency", "CBSA"),
    ("Canada Deposit Insurance Corporation", "CDIC"),
    ("Canada Development Investment Corporation", "CDEV"),
    ("Canada Economic Development for Quebec Regions", "CED"),
    ("Canada Employment Insurance Commission", "CEIC"),
    ("Canada Energy Regulator", "CER"),
    ("Canada Firearms Centre", "CAFC"),
    ("Canada Industrial Relations Board", "CIRB"),
    ("Canada Infrastructure Bank", "CIB"),
    ("Canada Lands Company Limited", "CLC"),
    ("Canada Mortgage and Housing Corporation", "CMHC"),
    ("Canada Pension Plan Investment Board", "CPPIB"),
    ("Canada Post", "CPC"),
    ("Canada Revenue Agency", "CRA"),
    ("Canada School of Public Service", "CSPS"),
    ("Canadian Air Transport Security Authority", "CATSA"),
    ("Canadian Army", "CA"),
    ("Canadian Centre for Occupational Health and Safety", "CCOHS"),
    ("Canadian Coast Guard", "CCG"),
    ("Canadian Commercial Corporation", "CCC"),
    ("Canadian Conservation Institute", "CCI"),
    ("Canadian Dairy Commission", "CDC"),
    ("Canadian Food Inspection Agency", "CFIA"),
    ("Canadian Forces Housing Agency", "CFHA"),
    ("Canadian Grain Commission", "CGC"),
    ("Canadian Heritage", "PCH"),
    ("Canadian Heritage Information Network", "CHIN"),
    ("Canadian Human Rights Commission", "CHRC"),
    ("Canadian Institutes of Health Research", "CIHR"),
    ("Canadian Intellectual Property Office", "CIPO"),
    ("Canadian Intergovernmental Conference Secretariat", "CICS"),
    ("Canadian International Trade Tribunal", "CITT"),
    ("Canadian Judicial Council", "CJC"),
    ("Canadian Museum for Human Rights", "CMHR"),
    ("Canadian Museum of History", "CMH"),
    ("Canadian Museum of Immigration at Pier 21", "CMIP"),
    ("Canadian Museum of Nature", "CMN"),
    ("Canadian Northern Economic Development Agency", "CanNor"),
    ("Canadian Nuclear Safety Commission", "CNSC"),
    ("Canadian Pari-Mutuel Agency", "CPMA"),
    ("Canadian Police College", "CPC"),
    ("Canadian Race Relations Foundation", "CRRF"),
    ("Canadian Radio-Television and Telecommunications Commission", "CRTC"),
    ("Canadian Security Intelligence Service", "CSIS"),
    ("Canadian Space Agency", "CSA"),
    ("Canadian Special Operations Forces Command", "CANSOFCOM"),
    ("Canadian Trade Commissioner Service", "TCS"),
    ("Canadian Transportation Agency", "CTA"),
    ("CBC/Radio-Canada", "CBC"),
    ("Civilian Review and Complaints Commission for the RCMP", "CRCC"),
    ("Commissioner for Federal Judicial Affairs Canada (Office of the)", "FJA"),
    ("Commissioner of Lobbying of Canada (Office of the)", "OCL"),
    ("Commissioner of Official Languages (Office of the)", "OCOL"),
    ("Communications Research Centre Canada", "CRC"),
    ("Communications Security Establishment Canada", "CSEC"),
    ("Competition Bureau Canada", "COBU"),
    ("Conflict of Interest and Ethics Commissioner (Office of the)", "CIEC"),
    ("Copyright Board Canada", "CB"),
    ("Correctional Investigator Canada", "OCI"),
    ("Correctional Service Canada", "CSC"),
    ("Court Martial Appeal Court of Canada", "CMAC"),
    ("Courts Administration Service", "CAS"),
    ("Crown-Indigenous Relations and Northern Affairs Canada", "CIRNAC"),
    ("Defence Construction Canada", "DCC"),
    ("Defence Research and Development Canada", "DRDC"),
    ("Destination Canada", "DC"),
    ("Elections Canada", "Elections"),
    ("Employment and Social Development Canada", "ESDC"),
    ("Environment and Climate Change Canada", "ECCC"),
    ("Environmental Protection Review Canada", "EPRC"),
    ("Export Development Canada", "EDC"),
    ("Farm Credit Canada", "FCC"),
    ("Farm Products Council of Canada", "FPCC"),
    ("Federal Bridge Corporation", "FBCL"),
    ("Federal Court of Appeal", "FCA"),
    ("Federal Court of Canada", "FC"),
    ("Federal Economic Development Agency for Southern Ontario", "FedDev Ontario"),
    ("Federal Ombudsman for Victims Of Crime (Office of the)", "OFOVC"),
    ("Finance Canada (Department of)", "FIN"),
    ("Financial Consumer Agency of Canada", "FCAC"),
    ("Financial Transactions and Reports Analysis Centre of Canada", "FINTRAC"),
    ("Fisheries and Oceans Canada", "DFO"),
    ("Freshwater Fish Marketing Corporation", "FFMC"),
    ("Global Affairs Canada", "GAC"),
    ("Governor General of Canada", "OSGG"),
    ("Great Lakes Pilotage Authority Canada", "GLPA"),
    ("Health Canada", "HC"),
    ("Historic Sites and Monuments Board of Canada", "HSMBC"),
    ("Human Rights Tribunal of Canada", "HRTC"),
    ("Immigration and Refugee Board of Canada", "IRB"),
    ("Immigration, Refugees and Citizenship Canada", "IRCC"),
    ("Impact Assessment Agency of Canada", "IAAC"),
    ("Independent Review Panel for Defence Acquisition", "IRPDA"),
    ("Indigenous and Northern Affairs Canada", "INAC"),
    ("Indigenous Services Canada", "ISC"),
    ("Industrial Technologies Office", "ITO"),
    ("Information Commissioner (Office of the)", "OIC"),
    ("Infrastructure Canada", "INFC"),
    ("Innovation, Science and Economic Development Canada", "ISED"),
    ("Intergovernmental Affairs", "IGA"),
    ("International Development Research Centre", "IDRC"),
    ("Jacques Cartier and Champlain Bridges", "JCCBI"),
    ("Justice Canada (Department of)", "JUS"),
    ("Laurentian Pilotage Authority Canada", "LPA"),
    ("Library and Archives Canada", "LAC"),
    ("Marine Atlantic", "MarineAtlantic"),
    ("Measurement Canada", "MC"),
    ("Military Grievances External Review Committee", "MGERC"),
    ("Military Police Complaints Commission of Canada", "MPCC"),
    ("National Arts Centre", "NAC"),
    ("National Battlefields Commission", "NBC"),
    ("National Capital Commission", "NCC"),
    ("National Defence", "DND"),
    ("National Film Board", "NFB"),
    ("National Gallery of Canada", "NGC"),
    ("National Research Council Canada", "NRC"),
    ("National Security and Intelligence Review Agency", "NSIRA"),
    ("Natural Resources Canada", "NRCan"),
    ("Natural Sciences and Engineering Research Canada", "NSERC"),
    ("Northern Pipeline Agency Canada", "NPA"),
    ("Occupational Health and Safety Tribunal Canada", "OHSTC"),
    ("Office of the Chief Military Judge", "OCMJ"),
    ("Pacific Economic Development Canada", "PacifiCan"),
    ("Pacific Pilotage Authority Canada", "PPA"),
    ("Parks Canada", "PC"),
    ("Parole Board of Canada", "PBC"),
    ("Patented Medicine Prices Review Board Canada", "PMPRB"),
    ("Polar Knowledge Canada", "POLAR"),
    ("Prairies Economic Development Canada", "PrairiesCan"),
    ("Privacy Commissioner of Canada (Office of the)", "OPC"),
    ("Privy Council Office", "PCO"),
    ("Procurement Ombudsman (Office of the)", "OPO"),
    ("Public Health Agency of Canada", "PHAC"),
    ("Public Prosecution Service of Canada", "PPSC"),
    ("Public Safety Canada", "PS"),
    ("Public Sector Integrity Commissioner of Canada (Office of the)", "PSIC"),
    ("Public Sector Pension Investment Board", "PSP Investments"),
    ("Public Servants Disclosure Protection Tribunal Canada", "PSDPTC"),
    ("Public Service Commission of Canada", "PSC"),
    ("Public Service Labour Relations and Employment Board", "PSLREB"),
    ("Public Services and Procurement Canada", "PSPC"),
    ("Registry of the Specific Claims Tribunal of Canada", "SCT"),
    ("Royal Canadian Air Force", "RCAF"),
    ("Royal Canadian Mint", "Mint"),
    ("Royal Canadian Mounted Police", "RCMP"),
    ("Royal Canadian Mounted Police External Review Committee", "ERC"),
    ("Royal Canadian Navy", "RCN"),
    ("Royal Military College of Canada", "RMCC"),
    (
        "Secretariat of the National Security and Intelligence Committee of Parliamentarians",
        "NSICOP",
    ),
    ("Service Canada", "ServCan"),
    ("Shared Services Canada", "SSC"),
    ("Social Sciences and Humanities Research Council of Canada", "SSHRC"),
    ("Social Security Tribunal of Canada", "SST"),
    ("Standards Council of Canada", "SCC-CCN"),
    ("Statistics Canada", "StatCan"),
    ("Superintendent of Bankruptcy Canada (Office of the)", "OSB"),
    ("Superintendent of Financial Institutions Canada (Office of the)", "OSFI"),
    ("Supreme Court of Canada", "SCC"),
    ("Tax Court of Canada", "TCC"),
    ("Taxpayers' Ombudsperson (Office of the)", "OTO"),
    ("Transport Canada", "TC"),
    ("Transportation Appeal Tribunal of Canada", "TATC"),
    ("Transportation Safety Board of Canada", "TSB"),
    ("Treasury Board of Canada Secretariat", "TBS"),
    ("Veterans Affairs Canada", "VAC"),
    ("Veterans Review and Appeal Board", "VRAB"),
    ("VIA Rail Canada", "VIA Rail"),
    ("Virtual Museum of Canada", "VMC"),
    ("Windsor-Detroit Bridge Authority", "WDBA"),
    ("Women and Gender Equality Canada", "WAGE"),
    ("Youth", "YOUTH"),
]


def get_random_file_type() -> str:
    """Get a random file type"""
    return random.choice(F_TYPES)


def get_random_word() -> str:
    """Get a random word"""
    return random.choice(WORDS)


def get_random_phrase() -> str:
    """Get a random phrase"""
    return random.choice(SENTENCES)


def get_random_hash(hash_len: int) -> str:
    """Get a random hash"""
    return "".join([random.choice(HASH_ALPHA) for _ in range(hash_len)])


def get_random_label() -> str:
    """Get a random label"""
    return get_random_word().upper()


def get_random_user() -> str:
    """Get a random user"""
    return random.choice(USERS)


def get_random_groups() -> str:
    """Get a random groups"""
    return random.choice(GROUPS)


def get_random_filename(smin: int = 1, smax: int = 3) -> str:
    """Get a random filename"""
    return "_".join([get_random_word().lower() for _ in range(random.randint(smin, smax))]) + random.choice(EXT)


def get_random_directory(smin: int = 2, smax: int = 6) -> str:
    """Get a random directory"""
    return "/".join([get_random_word().lower() for _ in range(random.randint(smin, smax))])


def get_random_string(smin: int = 4, smax: int = 24) -> str:
    """Get a random string"""
    return "".join([random.choice(ALPHA) for _ in range(random.randint(smin, smax))])


def get_random_email() -> str:
    """Get a random email"""
    return f"{get_random_word()}@{get_random_word()}{random.choice(DOM)}"


def get_random_host() -> str:
    """Get a random host"""
    return get_random_word().lower() + random.choice(DOM)


def get_random_ip() -> str:
    """Get a random ip"""
    return ".".join([str(random.randint(1, 254)) for _ in range(4)])


def get_random_lat_lng():
    "Get a random lat/lng"
    pi = math.pi
    cf = 180.0 / pi  # radians to degrees Correction Factor

    # get a random Gaussian 3D vector:
    gx = random.gauss(0.0, 1.0)
    gy = random.gauss(0.0, 1.0)
    gz = random.gauss(0.0, 1.0)

    # normalize to an equidistributed (x,y,z) point on the unit sphere:
    norm2 = gx * gx + gy * gy + gz * gz
    norm1 = 1.0 / math.sqrt(norm2)
    x = gx * norm1
    y = gy * norm1
    z = gz * norm1

    rad_lat = math.asin(z)  # latitude  in radians
    rad_lon = math.atan2(y, x)  # longitude in radians

    return (round(cf * rad_lat, 5), round(cf * rad_lon, 5))


def get_random_iso_date(epoch: _Optional[float] = None) -> str:
    """Get a random ISO formatted date"""
    if epoch is None:
        epoch = time.time() + random.randint(-3000000, 0)

    return datetime.datetime.fromtimestamp(epoch).isoformat() + "Z"


def get_random_mapping(field: _Field) -> dict[str, _Any]:
    """Get a random mapping"""
    return {MAPPING_KEYS[i]: random_data_for_field(field, MAPPING_KEYS[i]) for i in range(random.randint(1, 5))}


def get_random_phone() -> str:
    """Get a random phone"""
    return (
        f'{random.choice(["", "+1 "])}{"-".join([str(random.randint(100, 999)) for _ in range(3)])}'
        f"{str(random.randint(0, 9))}"
    )


def get_random_mac() -> str:
    """Get a random mac"""
    return ":".join([get_random_hash(2) for _ in range(6)])


def get_random_uri_path() -> str:
    """Get a random uri_path"""
    return f"/{'/'.join([get_random_word() for _ in range(random.randint(2, 6))])}"


def get_random_uri() -> str:
    """Get a random uri"""
    return f"{random.choice(['http', 'https', 'ftp'])}://{get_random_host()}{get_random_uri_path()}"


def get_random_ssdeep() -> str:
    """Get a random ssdeep"""
    return (
        f"{str(random.randint(30, 99999))}"
        f":{''.join([random.choice(SSDEEP_ALPHA) for _ in range(random.randint(20, 64))])}"
        f":{''.join([random.choice(SSDEEP_ALPHA) for _ in range(random.randint(20, 64))])}"
    )


def get_random_platform() -> str:
    """Get a random platform"""
    return random.choice(["Windows", "Linux", "MacOS", "Android", "iOS"])


def get_random_processor() -> str:
    """Get a random processor"""
    return random.choice(["x86", "x64"])


def get_random_version() -> str:
    """Get a random version"""
    return f"{random.randint(4, 8)}.{random.randint(0, 5)}.{random.randint(0, 9)}"


def get_random_user_agent() -> str:
    """Get a random user_agent"""
    return random.choice(
        [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 "
            "Safari/537.36 Edg/108.0.1462.46",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 "
            "Safari/537.36",
            "Mozilla/5.0 (Linux; Android 10; SM-G980F Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like "
            "Gecko) Version/4.0 Chrome/78.0.3904.96 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone9,4; U; CPU iPhone OS 10_0_1 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) "
            "Version/10.0 Mobile/14A403 Safari/602.1",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 "
            "Safari/601.3.9",
        ]
    )


def random_department():
    """Generate a random department"""
    return random.choice(DEPARTMENTS)[1], random.randint(1, len(DEPARTMENTS))


# noinspection PyProtectedMember
def random_data_for_field(field: _Field, name: str, minimal: bool = False) -> _Any:
    """Get random data for any given field type"""
    if isinstance(field, Boolean):
        return random.choice([True, False])
    elif isinstance(field, Classification):
        if field.engine.enforce:
            possible_classifications = list(field.engine._classification_cache)
            possible_classifications.extend([field.engine.UNRESTRICTED, field.engine.RESTRICTED])
        else:
            possible_classifications = [field.engine.UNRESTRICTED]
        return random.choice(possible_classifications)
    elif isinstance(field, ClassificationString):
        possible_classifications = [field.engine.UNRESTRICTED]
        return random.choice(possible_classifications)
    elif isinstance(field, Enum):
        return random.choice([x for x in field.values if x is not None])
    elif isinstance(field, List):
        return [
            (
                random_data_for_field(field.child_type, name)
                if not isinstance(field.child_type, Model)
                else random_model_obj(field.child_type, as_json=True)
            )
            for _ in range(random.randint(1, 4))
        ]
    elif isinstance(field, Compound):
        if minimal:
            return random_minimal_obj(field.child_type, as_json=True)
        else:
            return random_model_obj(field.child_type, as_json=True)
    elif isinstance(field, Mapping):
        return get_random_mapping(field.child_type)
    elif isinstance(field, Optional):
        if not minimal:
            return random_data_for_field(field.child_type, name)
        else:
            return field.child_type.default
    elif isinstance(field, UUID):
        return get_random_id()
    elif isinstance(field, Date):
        return get_random_iso_date()
    elif isinstance(field, Integer):
        return random.randint(128, 4096)
    elif isinstance(field, Float):
        return random.randint(12800, 409600) / 100.0
    elif isinstance(field, MD5):
        return get_random_hash(32)
    elif isinstance(field, SHA1):
        return get_random_hash(40)
    elif isinstance(field, SHA256):
        return get_random_hash(64)
    elif isinstance(field, HowlerHash):
        return get_random_hash(random.randint(1, 64))
    elif isinstance(field, SSDeepHash):
        return get_random_ssdeep()
    elif isinstance(field, URI):
        return get_random_uri()
    elif isinstance(field, URIPath):
        return get_random_uri_path()
    elif isinstance(field, MAC):
        return get_random_mac()
    elif isinstance(field, PhoneNumber):
        return get_random_phone()
    elif isinstance(field, IP):
        return get_random_ip()
    elif isinstance(field, Domain):
        return get_random_host()
    elif isinstance(field, Email):
        return get_random_email()
    elif isinstance(field, Platform):
        return get_random_platform()
    elif isinstance(field, Processor):
        return get_random_processor()
    elif isinstance(field, Json):
        return random.choice(
            [
                get_random_word(),  # string
                random.choice([True, False]),  # boolean
                [get_random_word() for _ in range(random.randint(2, 4))],  # list
                random.randint(0, 100),
            ]  # number
        )
    elif isinstance(field, UpperKeyword):
        return get_random_word().upper()
    elif isinstance(field, LowerKeyword):
        return get_random_word().lower()
    elif isinstance(field, Keyword) or isinstance(field, EmptyableKeyword):
        if name:
            if "sha256" in name:
                return get_random_hash(64)
            elif "filetype" in name:
                return get_random_file_type()
            elif "label" in name:
                return get_random_label()
            elif "group" in name:
                return get_random_groups()
            elif "user" in name or "uname" in name or "username" in name:
                return get_random_user()
            elif name.startswith("id_") or name.endswith("_id"):
                return get_random_id()
            elif "mac" in name:
                return get_random_hash(12).upper()
            elif "sha1" in name:
                return get_random_hash(40)
            elif "sha384" in name:
                return get_random_hash(96)
            elif "sha512" in name:
                return get_random_hash(128)
            elif "md5" in name:
                return get_random_hash(32)
            elif "host" in name or "node" in name or "domain" in name:
                return get_random_host()
            elif name.endswith("ip") or name.startswith("ip_"):
                return get_random_ip()
            elif "file" in name:
                return get_random_filename()
            elif "name" in name:
                return get_random_filename()
            elif "directory" in name:
                return get_random_directory()
            elif "version" in name:
                return get_random_version()

        return get_random_word()
    elif isinstance(field, Text):
        return get_random_phrase()
    elif isinstance(field, Any):
        return get_random_word()
    else:
        raise HowlerValueError(f"Unknown field type {field.__class__}")


# noinspection PyProtectedMember
def random_model_obj(model: odm.Model, as_json: bool = False) -> _Any:
    """Create a random valid instance for the given model"""
    data = {}
    for f_name, f_value in model.fields().items():
        data[f_name] = random_data_for_field(f_value, f_name)

    if as_json:
        return data
    else:
        return model(data)  # type: ignore[operator]


# noinspection PyProtectedMember
def random_minimal_obj(model: odm.Model, as_json: bool = False) -> _Any:
    """Create a minimal valid instance for the given model"""
    data = {}
    for f_name, f_value in model.fields().items():
        if not f_value.default_set:
            data[f_name] = random_data_for_field(f_value, f_name, minimal=True)

    if as_json:
        return data
    else:
        return model(data)  # type: ignore[operator]
