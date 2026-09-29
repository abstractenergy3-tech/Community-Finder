# Run the live prototype locally

1. Put all files in the same directory.
2. Obtain the approved source data using the source connector.
3. Save normalized results as `harvested_resources.json`.
4. Run:
   `python pipeline.py`
5. Run:
   `python app_api.py`
6. Serve the frontend from a local web server (for example, a simple static server).
7. Open the frontend on the phone/browser.

For a real deployment, replace the local JSON files with the database and authenticated API described in the project files.

Important:
- Do not expose the development API directly to the public internet.
- Replace the placeholder bot contact information before any production crawling.
- Confirm source permissions and terms again before deploying automated jobs.
