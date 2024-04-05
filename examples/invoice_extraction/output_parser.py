from typing import Dict

from langchain.output_parsers import PydanticOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field


class Invoice(BaseModel):
    number: str = Field(description="invoice number, e.g. #25470322")
    date: str = Field(description="invoice date, e.g. 2024-01-01T08:29:56")
    company: str = Field(description="remit to company, e.g. Akamai Technologies, Inc.")
    company_address: str = Field(
        description="remit to address, e.g. 249 Arch St. Philadelphia, PA 19106 USA"
    )
    tax_id: str = Field(description="tax ID/EIN number, e.g. 04-3432319")
    customer: str = Field(description="invoice to customer, e.g. John Doe")
    customer_address: str = Field(
        description="invoice to address, e.g. 123 Main St. Springfield, IL 62701 USA"
    )
    amount: str = Field(description="total amount from this invoice, e.g. $5.00")

    def to_dict(self) -> Dict:
        return {
            "number": self.number,
            "date": self.date,
            "company": self.company,
            "company_address": self.company_address,
            "tax_id": self.tax_id,
            "customer": self.customer,
            "customer_address": self.customer_address,
            "amount": self.amount,
        }


invoice_parser = PydanticOutputParser(pydantic_object=Invoice)
