# Address Normaliser - How It Works

## What This System Does

For each person (IC number), your database stores multiple addresses — sometimes up to 40 different versions of the same address. Previously, staff had to manually look through all of them and pick the best one for mailing.

This system does that automatically.

## How It Picks The Best Address

**Step 1: Read all addresses**
The system reads every address stored for each IC number.

**Step 2: Clean up the addresses**
It fixes common short forms used in Malaysian addresses:
- "Jln" becomes "Jalan"
- "Tmn" becomes "Taman"
- "Lrg" becomes "Lorong"
- "Kg" becomes "Kampung"
- And many more...

**Step 3: Group similar addresses**
Many of the addresses for one person are actually the same place, just written differently. For example:
- "NO 235 LRG 5 JLN KERETAPI, TMN SPRINGFIELD, 93250, KUCHING, SARAWAK"
- "NO 235 LORONG 5 TAMAN SPRINGFIELD JALAN KERETAPI 93250 KUCHING SARAWAK"

These are the same address — the system recognises that and groups them together.

**Step 4: Pick the most complete version**
From each group, the system picks the version that has:
- A full street address (house number, street name)
- A valid 5-digit postcode
- A city name
- A state name

The group with the most entries AND the most complete address wins — because if the same address appears many times, it's more likely to be correct.

**Step 5: Verify the postcode**
The system checks every postcode against the official Malaysian postcode database (2,932 postcodes covering all of Malaysia). If the postcode doesn't match the city or state, it corrects it automatically.

**Step 6: Format for mailing**
The final address is formatted in standard Malaysian mailing format:
```
NO 235 LORONG 5 JALAN KERETAPI
TAMAN SPRINGFIELD
93250 KUCHING
SARAWAK
```

## Confidence Score

Each address gets a confidence score from 0% to 100%:

- **80-100% (OK)** — High quality address, ready to use for mailing
- **60-79% (Medium)** — Decent address but may be missing some details
- **Below 60% (Low)** — Address may be incomplete, staff should check manually
- **0% (No Address)** — No valid address found in the system

## How To Use

1. Upload your Excel file to the **"Upload"** folder in Google Drive (under Falcon Field > Address Normaliser)
2. Wait a few minutes — the system processes it automatically
3. Find your results in the **"Completed > Output"** folder
4. A status report is also saved in **"Completed > Logs"**

The output file has 4 columns:
- **ICNO** — The IC number
- **NAME** — The person's name
- **MAILING_ADDRESS** — The selected and formatted address (ready for printing)
- **CONFIDENCE** — How confident the system is (0.0 to 1.0)

## Validation Report

For the first few batches, we also provide a validation report so your staff can verify the system is picking the right addresses. This report shows:
- The address the system selected
- ALL the original addresses side by side
- A flag telling staff which ones to review

Once you are satisfied the system is accurate, you can use the output directly without manual checking.

## What It Cannot Do

- If a person has NO addresses in the system, the system cannot create one
- If ALL addresses are incomplete (e.g., just "Kampung" with no details), the system will flag it for manual review
- The system does not verify whether a person actually lives at the address — it only picks the best available address from your records
