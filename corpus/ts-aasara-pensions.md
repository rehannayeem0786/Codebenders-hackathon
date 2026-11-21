# Telangana Aasara pensions - source text (curated)

Source: https://pension.telangana.gov.in/ · Telangana Aasara pensions portal and
state budget orders · captured for the SchemeSetu corpus on 2026-11-05.

## Purpose

Social security pensions for the weakest households in Telangana, credited by
DBT on the first of every month.

## Categories

| Category | Age / condition |
|---|---|
| Old age | 57 years or above |
| Widow | 18 years or above, widow |
| Persons with disability | 18 years or above, disability 40% or more (SADAREM) |
| Beedi workers, single women, toddy tappers, weavers etc. | as per the state order |

## Amount

The pension amount has been revised several times at budget time. SchemeSetu
therefore tags the amount `AMBIGUOUS` and tells the citizen to confirm the
current rate at the MRO / Gram Panchayat office. The *eligibility rules* are
stable and are tagged `EXTRACTED`.

## Eligibility

- Resident of Telangana.
- Household income within the prescribed limit; a white (low-income) ration card
  is the usual proof.
- The person should not already be drawing another government pension.
- Government employees and retired government employees are excluded.

## How to apply

1. Collect the form from the Gram Panchayat / Ward office, or apply on the
   Aasara pensions portal.
2. Attach age proof, residence proof, ration card and the bank passbook.
3. The Gram Panchayat verifies and forwards the application to the MRO /
   Tahsildar.
4. After sanction, the pension is credited on the 1st of every month.
5. If the pension stops, it is usually a bank or Aadhaar re-verification issue -
   ask at MeeSeva or the MRO office.

## Notes for SchemeSetu

- The 57-year threshold is modelled as `hard`; the state has used 57 for the
  old-age category, while the central NSAP pension starts at 60. Both are shown
  to the citizen with their own sources.
- "Not already receiving another pension" is a hard rule, and it is exactly the
  kind of fact a family knows instantly - which is why it appears high in
  `next_questions`.
