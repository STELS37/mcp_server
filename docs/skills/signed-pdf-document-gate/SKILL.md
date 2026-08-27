---
name: signed-pdf-document-gate
description: Canonical business rule for creating, filling, signing, sealing, flattening and visually validating bank/legal/accounting PDFs before any external send. Blocking for all managers.
version: 1.0.0
status: mandatory
---

# Signed PDF Document Gate — canonical business rule

## Scope

This skill is mandatory for every manager/agent that prepares a bank form, credit package, questionnaire, consent, contract, accounting statement, certificate, application or other document that will be signed/sealed and sent outside the company.

It applies across Bank Manager, Office Managers, Sales Managers and any other worker that creates or modifies signed business documents.

A document is **NOT READY** until every blocking gate below passes.

## Core invariant

Never optimize for “the file was generated”. Optimize for “the final rendered page looks like a correctly completed human business document, all data is in the intended fields, signatures/seals are authorized and correctly placed, page boundaries are correct, and the outgoing PDF is stable and non-editable as a scanned page when a scanned signed copy is expected”.

## 1. Source-template preservation

- Start from the bank/company original template whenever available.
- Preserve paper size, orientation, margins, print area, page breaks, repeated titles, row heights, column widths, merged cells, borders, static labels, logos and section bands.
- Do not rebuild a bank template from scratch unless the original is unusable.
- Do not globally autosize rows/columns.
- Do not blindly use Fit-to-one-page if it makes text, signature, handwriting or seal physically unrealistic or microscopic.
- One logical form/consent that is designed as one A4 page must stay on one A4 page. A page break inside such a consent is a blocking defect.

## 2. Semantic field placement

- Locate targets by semantic label + table geometry, not by “nearest empty cell”.
- Never place values in a column-header row, section-title row, explanatory-note row or decorative band.
- The first record must always start in the first data row below the headers.
- For merged ranges, write only to the actual merged anchor and verify the rendered result.
- Preserve the correct row/column association for every value.
- Long values must wrap inside their own field; they must not cross borders or shrink to unreadable size.
- A value visually close to the correct field is still wrong if it belongs to a different cell/row.

## 3. Truthfulness / disclosure / entity guard

- Never invent facts, negative answers, balances, contracts, counterparties, relationships, signatures or dates.
- Do not proactively disclose unrelated affiliated/group companies unless the form/question explicitly requires that information.
- If related-party disclosure is explicitly mandatory, do not fabricate “none” or conceal a required fact; hold the field for factual/legal confirmation when necessary.
- Before external send, verify borrower/company identity in every attachment: legal name + INN/tax ID where present.
- A foreign legal entity in an attachment is a blocking error unless that attachment is intentionally part of the requested package.
- Never forward an old email merely to extract one attachment if the forward would also carry unrelated/foreign-company archive attachments or confidential correspondence.

## 4. Freshness rule for bank requests

- If a bank requests a document already sent before, assume it wants a fresher/current or more exact-period version unless the bank explicitly says otherwise.
- Never present an older period as a precise answer to a newer request.
- Send the exact requested period when available; otherwise send the confirmed available part and state the exact remaining gap truthfully.

## 5. Handwritten-designated fields

- Fields that the bank expects handwritten (date, full name, initials, check/consent marks when specifically requested, etc.) must not be left as ordinary machine-typed text.
- Use only the user-provided/approved handwriting sample or an actual handwritten scan when an image/scanned-signature workflow is permitted by the receiving bank/document.
- Preserve the visual style and scale of the approved sample; do not synthetically invent a new signature or handwriting identity.
- Handwritten date, signature stroke, full-name/initials and seal are independent objects with independent target anchors.
- A signature stroke must never be placed on the date line.
- Full-name/initials must never overlap the signature line unless the source form explicitly designs it that way.

## 6. Signature policy

- Use an authorized signature image/sample only for the user/company it belongs to and only where the bank/document permits an image/scanned signature workflow.
- If the bank explicitly requires a wet/blue-ink paper signature, do not simulate it electronically. Produce a print-ready document with that signature field left for physical signing.
- Never claim a document was wet-signed when it was not.
- Never manufacture a synthetic signature or imitate a third party.

## 7. Seal/stamp geometry

- Use only the authorized company seal asset.
- Keep one calibrated canonical physical diameter/size; preserve aspect ratio.
- Size must be validated in millimetres after PDF export, not only pixels.
- The seal must not cover required text, dates, handwritten-name fields or table content.
- Do not duplicate the seal unless the form explicitly requires multiple seals.
- A duplicate or oversized seal is a blocking defect.

## 8. Layout and page-flow gate

Before flattening, verify:

- expected page count and order;
- no unexpected continuation page;
- no empty spill page;
- no logical one-page consent split across pages;
- no content from the next document appearing on the previous page;
- no header/footer displaced by scaling;
- no clipping at page edges;
- no row/table cut in an unintended location;
- no text crossing table borders;
- no values under/over static labels;
- no duplicate values caused by merge/unmerge or overlay logic.

Any failure => regenerate before proceeding.

## 9. Visual QA — mandatory, page by page

1. Export candidate PDF.
2. Render **every page** to images at >= 150 dpi (prefer 200–300 dpi for signed forms).
3. Inspect every rendered page, not only page 1 or the signature page.
4. Compare visually with the original source form and ensure static bank labels/table geometry did not drift.
5. Inspect all high-risk zones at higher zoom: table headers, long text fields, dates, signature lines, FIO/initials, seals, checkboxes, page breaks.
6. Verify that each filled value is inside the intended semantic field.
7. Verify seal/signature/handwriting physical scale and non-overlap.
8. If anything looks “almost right”, treat it as a failure and regenerate.

## 10. Flattened signed-scan output

When the recipient expects a signed/scanned PDF:

- After all content/signature/seal placement is correct, render each final page to a high-quality image.
- Build a new PDF from those full-page images.
- The final outgoing PDF must behave as a page scan: signature, seal and handwriting are baked into the page and cannot be independently selected, moved or copied as separate PDF objects.
- Do not keep form fields, annotations, signature-image layers or movable overlays in the final delivery copy.
- Preserve readable resolution; flattening must not make small bank text blurry.

## 11. Final flattened-file verification

After flattening, repeat the QA on the actual outgoing file:

- render every page again;
- confirm final page count/order;
- confirm no visual drift introduced by rasterization;
- confirm no duplicated signature/seal;
- confirm signature is not on date;
- confirm handwriting remains legible;
- confirm the seal is correctly sized and located;
- confirm one-page forms are still one page;
- confirm there are no unexpected PDF form widgets/annotations/editable overlays when a scan copy is required;
- confirm borrower/company identity again.

Only the verified flattened file may be attached to the outgoing email.

## 12. Email attachment postcondition

The document task is not closed merely because an email was sent.

After send:

- read back the Sent message;
- confirm the exact intended filenames are attached;
- confirm no unrelated archive attachments were inherited from reply/forward;
- confirm each attachment matches the intended legal entity;
- only then mark the bank/document request as completed.

## Blocking regression cases

Every implementation of this skill must detect/prevent at least these failures:

- first data row written into column header row;
- value written into adjacent merged cell;
- long text crossing a border;
- one-page consent split into two pages;
- next document starts on previous page;
- signature placed on date line;
- machine-typed FIO left in a handwriting-required field;
- duplicate seal;
- oversized/undersized seal;
- duplicated signature;
- seal/signature covering mandatory text;
- unrelated company/INN attachment included;
- old-period document presented as fresh requested period;
- unflattened movable signature/seal layers in a supposed scanned signed PDF.

## Completion definition

A signed-document workflow is COMPLETE only when all are true:

`SOURCE_LAYOUT_OK && FIELD_MAPPING_OK && FACTS_OK && ENTITY_OK && FRESHNESS_OK && SIGNATURE_POLICY_OK && HANDWRITING_OK && SEAL_GEOMETRY_OK && PAGE_FLOW_OK && VISUAL_QA_OK && FLATTEN_OK && FINAL_QA_OK && EMAIL_ATTACHMENT_READBACK_OK`

Anything else is work-in-progress, not a finished document.
