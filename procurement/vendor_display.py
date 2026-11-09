"""Fictional company aliases for display; model IDs never change."""
from functools import lru_cache
import hashlib,json,re
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
MARL_ALIASES={'A':'PT. Aruna Niaga Nusantara','B':'PT. Bina Sumber Sejahtera','C':'PT. Cakra Mitra Utama'}
FIRST=['Adikara','Adinata','Adiprana','Adiwangsa','Angkasa','Anugerah','Arunika','Aryasatya',
 'Bahana','Bahari','Baskara','Bayutama','Bimasena','Brahma','Buana','Cakrawala','Candrakanta',
 'Cendana','Citra','Danadyaksa','Darma','Dewantara','Dinamika','Dirgantara','Dwipantara',
 'Ekakarya','Elang','Gandawira','Garuda','Gempita','Gemilang','Girimukti','Graha','Griya',
 'Indraprasta','Intan','Jagad','Jayakarta','Jenggala','Kartika','Kencana','Kirana','Krisna',
 'Kusuma','Langgeng','Lentera','Lintang','Mahakarya','Mahardika','Maheswara','Mandala',
 'Manggala','Matra','Mega','Mentari','Merapi','Mutiara','Nawasena','Nirmala','Pancakarya',
 'Paramita','Pertiwi','Pradana','Prakarsa']
LAST=['Abadi','Andalan','Bersama','Cemerlang','Dinamika','Gemilang','Harmoni','Indonesia',
 'Jaya','Kencana','Lestari','Mandiri','Nusantara','Perkasa','Pratama','Prima',
 'Sejahtera','Sentosa','Terpadu','Utama','Wisesa','Makmur','Niaga','Persada',
 'Sukses','Unggul','Berkah','Cipta','Karya','Mulya','Sarana','Sembada']


@lru_cache(maxsize=1)
def aliases():
    path=ROOT/'runs'/'bpi_offers'/'vendor_aliases.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def vendor_name(vendor):
    if vendor in MARL_ALIASES:return MARL_ALIASES[vendor]
    if vendor in aliases():return aliases()[vendor]
    digest=int.from_bytes(hashlib.sha256(str(vendor).encode()).digest()[:8],'big')
    return f'PT. {FIRST[digest%len(FIRST)]} {LAST[(digest//len(FIRST))%len(LAST)]}'


def display_text(value):
    if not isinstance(value,str):return value
    if value in MARL_ALIASES:return MARL_ALIASES[value]
    if value in aliases():return aliases()[value]
    value=re.sub(r'\bvendor_\d+\s*[·•]\s*(vendorID_\d+)\b',lambda m:vendor_name(m[1]),value)
    value=re.sub(r'\bvendorID_\d+\b',lambda m:vendor_name(m[0]),value)
    value=re.sub(r'\bvendor_([ABC])\b',lambda m:vendor_name(m[1]),value)
    value=re.sub(r'\b(?:Vendor|vendor)\s+([ABC])\b',lambda m:vendor_name(m[1]),value)
    return re.sub(r'\b[ABC]\b',lambda m:vendor_name(m[0]),value)


def display_value(value):
    if isinstance(value,str):return display_text(value)
    if isinstance(value,pd.DataFrame):
        result=value.copy()
        for col in result:
            if result[col].dtype==object or pd.api.types.is_string_dtype(result[col]):
                result[col]=result[col].map(display_text)
        result.columns=[display_text(c) for c in result.columns]
        return result
    if isinstance(value,list):return [display_value(v) for v in value]
    if isinstance(value,dict):return {display_text(k):display_value(v) for k,v in value.items()}
    return value


class NamedStreamlit:
    """Local presentation adapter for the legacy page, without patching Streamlit globally."""
    def __init__(self,streamlit):self.original=streamlit
    def __getattr__(self,name):
        target=getattr(self.original,name)
        if name=='data_editor':
            def editor(data,*args,**kwargs):
                result=target(display_value(data),*args,**kwargs)
                if isinstance(result,pd.DataFrame) and 'name' in result:
                    result=result.copy();reverse={v:k for k,v in MARL_ALIASES.items()}
                    result['name']=result['name'].map(lambda v:reverse.get(v,v))
                return result
            return editor
        if name in ['write','markdown','caption','info','success','warning','error','title','subheader','dataframe','header']:
            return lambda *args,**kwargs:target(*[display_value(v) for v in args],**kwargs)
        return target
