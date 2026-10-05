# VouchPilot for normal Windows users

## Fastest path

The supported end-user package is **VouchPilot-Windows.zip** from a GitHub Release.

1. Download the ZIP.
2. Extract it to a folder such as \`C:\\Apps\\VouchPilot\`.
3. Double-click **VouchPilot.exe**.
4. VouchPilot opens its local workspace in your browser.
5. Upload an XLSX, XLSM, CSV, PDF, or bill image.

No Python, Node.js, npm, or source checkout is required for the standalone package.

## What is included

The standalone executable contains the Python runtime, VouchPilot backend, and built React UI. The default keyword classifier works without model weights.

Optional local AI can be added separately by placing a GGUF model in a \`models\` folder next to the executable and a compatible llama.cpp server at \`tools\\llama-server\\bin\\llama-server.exe\`.

Scanned documents need a local Tesseract installation. Regular spreadsheet/CSV classification does not.

## Troubleshooting

A failed startup writes **VouchPilot.log** next to the executable. Re-run VouchPilot after fixing the reported dependency or port issue.

Use \`VouchPilot.exe --no-browser\` when you want to start the local API without opening a browser automatically.
