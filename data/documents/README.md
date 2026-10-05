# Drop real documents here

Put official PDFs / TXT / Markdown files in this folder (plus an optional `metadata.csv` manifest) and run:

    cd apps/api && python -m scripts.ingest --no-approve

Then approve them as an expert/admin in **Admin → Documents**. Use real `organization`, `publication_date`,
`source_url`, `authority_level=official|peer_reviewed|institutional` and `is_demo=false`; the UI then drops the DEMO badges.
Respect each publisher's licence: if redistribution of full text is not permitted, keep the file private and share only metadata + link.
