from typing import Optional, Union
import json
from typing import List, Optional
from pydantic import BaseModel, Field, validator, ValidationError
import re # Still needed for related cases

class GetFirRequest(BaseModel):
    police_station: str
    year: int
    district: str
    fir_number: str
    user_id: str

class DraftRequest(BaseModel):
    summary: str
    pdf_link: str

class DraftRequest(BaseModel):
    user_message: Union[str, None]
    session_id: str
    user_id: str
    draft_type: str
    court: str
    high_court: Union[str, None]

class SearchRequest(BaseModel):
    user_message: Union[str, None]
    session_id: str
    user_id: str

class UserDetailsRequest(BaseModel):
    user_id: str

class HistoryRequest(BaseModel):
    session_id: str
    user_id: str

class DownloadPdf(BaseModel):
    session_id: str
    user_id: str


class GetCasedetailsRequest(BaseModel):
    court: str
    case_type: str
    case_number: str
    year: str

class JudgmentResponse(BaseModel):
    order_date: str = Field(..., alias='order_date')
    order_and_case_id: str = Field(..., alias='order_and_case_id')
    bench: str = Field(..., alias='bench')
    judgment_link: str = Field(..., alias='view_order')

class CopyOfPetitionResponse(BaseModel):
    petition_type_no: str = Field(..., alias='petition_type_no')
    petition_date: str = Field(..., alias='petition_date')
    applied_by: str = Field(..., alias='applied_by')
    petition_status: str = Field(..., alias='petition_status')

class CaseListingResponse(BaseModel):
    cause_list_date: str = Field(..., alias='cause_list_date')
    list_type_sr_no: str = Field(..., alias='list_type_sr_no')
    bench: str = Field(..., alias='bench')

class CaseDetailsResponse(BaseModel):
    section_title: str = Field(..., alias='section_title')
    diary_number: str = Field(..., alias='diary_number')
    registration_date: str = Field(..., alias='registration_date')
    category: str = Field(..., alias='category')
    main_case_detail: str = Field(..., alias='main_case_detail')
    party_detail: str = Field(..., alias='party_detail')
    district: str = Field(..., alias='district')
    advocate_name: str = Field(..., alias='advocate_name')
    list_type: str = Field(..., alias='list_type')
    respondent_advocate_name: str = Field(..., alias='respondent_advocate_name')
    status: str = Field(..., alias='status')
    next_date: str = Field(..., alias='next_date')

class RelatedCasesResponse(BaseModel):
    case_number: str
    view_order: Optional[str] = None
    description: str

# --- Main Response Model (MODIFIED) ---
class GetCaseDetailsResponse(BaseModel):
    case_number: str # No validator needed anymore
    case_details: CaseDetailsResponse = Field(..., alias='case_details')
    related_cases: List[RelatedCasesResponse] = Field(..., alias='related_cases')
    case_listing: List[CaseListingResponse] = Field(..., alias='case_listing')
    copy_of_petition: List[CopyOfPetitionResponse] = Field(..., alias='copy_petitions')
    judgment_details: List[JudgmentResponse] = Field(..., alias='judgment_details')

class GetCaseFileRequest(BaseModel):
    case_number: str
    column_name: str
    row_value: str
    table_name: str
