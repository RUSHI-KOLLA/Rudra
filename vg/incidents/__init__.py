"""VG incidents package — the Mini CID Investigator.

One job: turn a plain-language question into findings gathered across six
investigative lenses (money, power, secrecy, timing, network, counter_case),
each finding tagged with its provenance.

Public surface:
    investigate(question)  -> the full investigation result
    sources                -> the free data sources behind each lens
"""

from .investigation import investigate
from .sources import (
    extract_amounts,
    extract_dates,
    search_counter_case,
    search_money,
    search_network,
    search_power,
    search_secrecy,
    search_timing,
)

__all__ = [
    "investigate",
    "extract_amounts",
    "extract_dates",
    "search_counter_case",
    "search_money",
    "search_network",
    "search_power",
    "search_secrecy",
    "search_timing",
]
