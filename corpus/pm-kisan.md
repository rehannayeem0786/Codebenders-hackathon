# PM-KISAN Samman Nidhi - source text (curated)

Source: https://pmkisan.gov.in/ · Scheme guidelines, Ministry of Agriculture and
Farmers' Welfare · captured for the SchemeSetu corpus on 2026-11-12.

## Purpose

An income support scheme for landholding farmer families, to supplement the
financial needs of farmers for inputs and household expenses related to
agriculture.

## Benefit

Rs 6,000 per year, released in three equal instalments of Rs 2,000, transferred
directly into the bank account of the beneficiary through DBT.

## Eligibility

- The applicant must be a landholding farmer family, with cultivable land in
  their name.
- The applicant must be 18 years of age or older.
- The land records must be updated in the state's land record system
  (in Telangana: Dharani / Pahani).

## Exclusion criteria

The following categories of families are NOT eligible:

- Institutional landholders.
- Farmer families where any member is a present or former holder of a
  constitutional post, or is a government employee (excluding Group D / Class IV
  and multi-tasking staff).
- Families where any member pays income tax.
- Professionals such as doctors, engineers, lawyers, chartered accountants and
  architects who are in practice.

## How to apply

1. New farmer registration on the PM-KISAN portal, or through a Common Service
   Centre.
2. e-KYC is mandatory and is completed through the portal's OTP flow.
3. Aadhaar seeding with the bank account is required for the instalment credit.
4. Status can be checked with "Know Your Status" using the registration number.

## Notes for SchemeSetu

- The three exclusion rules above are modelled as `hard` rules, because they
  come straight from the exclusion list.
- "Landholding" is modelled as `land_acres > 0`. A family that only works as
  farm labour (no land) should instead be pointed at MGNREGA / crop-insurance
  style benefits.
